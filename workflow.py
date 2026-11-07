from fastapi import APIRouter, Depends
from pydantic import BaseModel
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.types import Command
import uuid
from config import settings
from graph_run import builder
from auth import get_current_user
from fastapi.responses import StreamingResponse
router = APIRouter()

class StartBody(BaseModel):
    topic: str

class ResumeBody(BaseModel):
    thread_id: str
    answer: str

@router.post("/start")
async def start(body: StartBody, user_id: str = Depends(get_current_user)):
    async with AsyncPostgresSaver.from_conn_string(settings.postgres_uri) as checkpointer:
        await checkpointer.setup()
        graph = builder.compile(checkpointer=checkpointer)

        thread_id = str(uuid.uuid4())
        config = {"configurable": {"thread_id": thread_id}}

        await graph.ainvoke({"topic_direction": body.topic}, config)

        state = await graph.aget_state(config)
        print("tasks:", state.tasks)
        print("values:", state.values)

        interrupt_data = state.tasks[0].interrupts[0].value
        return {"thread_id": thread_id, "data": interrupt_data}

@router.post("/resume")
async def resume(body: ResumeBody, user_id: str = Depends(get_current_user)):
    async with AsyncPostgresSaver.from_conn_string(settings.postgres_uri) as checkpointer:
        graph = builder.compile(checkpointer=checkpointer)
        config = {"configurable": {"thread_id": body.thread_id}}

        await graph.ainvoke(Command(resume=body.answer), config)
        state = await graph.aget_state(config)

        if state.tasks and state.tasks[0].interrupts:
            return {"data": state.tasks[0].interrupts[0].value, "done": False}

        print("最终状态:", state.values)
        return {"data": state.values, "done": True}

@router.post("/stream")
async def stream(body: StartBody, user_id: str = Depends(get_current_user)):
    async def generate():
        async with AsyncPostgresSaver.from_conn_string(settings.postgres_uri) as checkpointer:
            await checkpointer.setup()
            graph = builder.compile(checkpointer=checkpointer)
            thread_id = str(uuid.uuid4())
            config = {"configurable": {"thread_id": thread_id}}

            async for event in graph.astream_events(
                {"topic_direction": body.topic}, config, version="v2"
            ):
                if event["event"] == "on_chat_model_stream":
                    chunk = event["data"]["chunk"].content
                    if chunk:
                        yield f"data: {chunk}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")