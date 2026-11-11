import json

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.types import Command
from fastapi.responses import StreamingResponse
import uuid
import time

from config import settings
from graph_run import builder
from auth import get_current_user
from limiter import limiter
from nodes import TokenCounter

router = APIRouter()


def _log_metrics(stage: str, status: str, elapsed: float, tokens: int, note: str = ""):
    line = f"{stage}\t{status}\t{time.strftime('%Y-%m-%d %H:%M:%S')}\t{elapsed:.1f}\t{tokens}\t{note}\n"
    with open("metrics.log", "a", encoding="utf-8") as f:
        f.write(line)


class StartBody(BaseModel):
    topic: str


class ResumeBody(BaseModel):
    thread_id: str
    answer: str


@router.post("/start")
@limiter.limit("3/minute")
async def start(request: Request, body: StartBody, user_id: str = Depends(get_current_user)):
    async with AsyncPostgresSaver.from_conn_string(settings.postgres_uri) as checkpointer:
        await checkpointer.setup()
        graph = builder.compile(checkpointer=checkpointer)

        thread_id = str(uuid.uuid4())
        counter = TokenCounter()
        config = {
            "configurable": {"thread_id": thread_id},
            "callbacks": [counter],
        }

        t0 = time.time()
        try:
            await graph.ainvoke({"topic_direction": body.topic}, config)
        except Exception as e:
            _log_metrics("start", "fail", time.time() - t0, 0, repr(e))
            raise
        elapsed = time.time() - t0
        _log_metrics("start", "ok", elapsed, counter.summary()["total_tokens"])
        print(f"[metrics][start] 耗时 {elapsed:.1f}s，模型调用 {counter.calls} 次，token {counter.summary()}")

        state = await graph.aget_state(config)
        interrupt_data = state.tasks[0].interrupts[0].value
        return {"thread_id": thread_id, "data": interrupt_data}


@router.post("/resume")
async def resume(body: ResumeBody, user_id: str = Depends(get_current_user)):
    async with AsyncPostgresSaver.from_conn_string(settings.postgres_uri) as checkpointer:
        graph = builder.compile(checkpointer=checkpointer)

        counter = TokenCounter()
        config = {
            "configurable": {"thread_id": body.thread_id},
            "callbacks": [counter],
        }

        t0 = time.time()
        try:
            await graph.ainvoke(Command(resume=body.answer), config)
        except Exception as e:
            _log_metrics("resume", "fail", time.time() - t0, 0, repr(e))
            raise
        elapsed = time.time() - t0

        state = await graph.aget_state(config)

        if state.tasks and state.tasks[0].interrupts:
            _log_metrics("resume", "paused", elapsed, counter.summary()["total_tokens"], "wait next interrupt")
            return {"data": state.tasks[0].interrupts[0].value, "done": False}

        images = state.values.get("image_urls", []) or []
        points = state.values.get("visual_points", []) or []
        status = "ok" if len(images) == len(points) else "partial"
        note = f"images={len(images)}/{len(points)}"
        _log_metrics("resume", status, elapsed, counter.summary()["total_tokens"], note)
        print(f"[metrics][resume] 耗时 {elapsed:.1f}s，token {counter.summary()['total_tokens']}，{note}")

        return {"data": state.values, "done": True}


@router.post("/stream")
async def stream(body: StartBody, user_id: str = Depends(get_current_user)):
    async def generate():
        async with AsyncPostgresSaver.from_conn_string(settings.postgres_uri) as checkpointer:
            await checkpointer.setup()
            graph = builder.compile(checkpointer=checkpointer)
            thread_id = str(uuid.uuid4())
            counter = TokenCounter()
            config = {
                "configurable": {"thread_id": thread_id},
                "callbacks": [counter],
            }

            yield f"event: thread\ndata: {json.dumps({'thread_id': thread_id}, ensure_ascii=False)}\n\n"

            try:
                async for event in graph.astream_events(
                    {"topic_direction": body.topic}, config, version="v2"
                ):
                    if event["event"] == "on_chat_model_stream":
                        chunk = event["data"]["chunk"].content
                        if chunk:
                            text = json.dumps({"text": chunk}, ensure_ascii=False)
                            yield f"event: token\ndata: {text}\n\n"
            except Exception as e:
                err = json.dumps({"error": repr(e)}, ensure_ascii=False)
                yield f"event: error\ndata: {err}\n\n"
                return

            state = await graph.aget_state(config)

            if state.tasks and state.tasks[0].interrupts:
                payload = {
                    "thread_id": thread_id,
                    "interrupt": state.tasks[0].interrupts[0].value,
                }
                data = json.dumps(payload, ensure_ascii=False)
                yield f"event: interrupt\ndata: {data}\n\n"
            else:
                data = json.dumps({"state": state.values}, ensure_ascii=False, default=str)
                yield f"event: done\ndata: {data}\n\n"

            yield "event: end\ndata: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")

@router.post("/resume/stream")
async def resume_stream(body: ResumeBody, user_id: str = Depends(get_current_user)):
    async def generate():
        async with AsyncPostgresSaver.from_conn_string(settings.postgres_uri) as checkpointer:
            graph = builder.compile(checkpointer=checkpointer)

            counter = TokenCounter()
            config = {
                "configurable": {"thread_id": body.thread_id},
                "callbacks": [counter],
            }

            yield f"event: thread\ndata: {json.dumps({'thread_id': body.thread_id}, ensure_ascii=False)}\n\n"

            t0 = time.time()
            try:
                async for event in graph.astream_events(
                    Command(resume=body.answer), config, version="v2"
                ):
                    if event["event"] == "on_chat_model_stream":
                        chunk = event["data"]["chunk"].content
                        if chunk:
                            text = json.dumps({"text": chunk}, ensure_ascii=False)
                            yield f"event: token\ndata: {text}\n\n"
            except Exception as e:
                _log_metrics("resume", "fail", time.time() - t0, 0, repr(e))
                err = json.dumps({"error": repr(e)}, ensure_ascii=False)
                yield f"event: error\ndata: {err}\n\n"
                return

            elapsed = time.time() - t0
            state = await graph.aget_state(config)

            if state.tasks and state.tasks[0].interrupts:
                _log_metrics("resume", "paused", elapsed, counter.summary()["total_tokens"], "wait next interrupt")
                payload = {"thread_id": body.thread_id, "interrupt": state.tasks[0].interrupts[0].value}
                data = json.dumps(payload, ensure_ascii=False)
                yield f"event: interrupt\ndata: {data}\n\n"
            else:
                images = state.values.get("image_urls", []) or []
                points = state.values.get("visual_points", []) or []
                status = "ok" if len(images) == len(points) else "partial"
                _log_metrics("resume", status, elapsed, counter.summary()["total_tokens"], f"images={len(images)}/{len(points)}")
                data = json.dumps({"state": state.values}, ensure_ascii=False, default=str)
                yield f"event: done\ndata: {data}\n\n"

            yield "event: end\ndata: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")
