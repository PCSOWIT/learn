from langgraph.types import interrupt
import asyncio
import httpx
from llm import llm_pro, llm_fast

from state import AgentState
from pydantic import BaseModel, Field
import asyncio
import base64
import uuid
import httpx
from pathlib import Path
from config import settings
import time
from langchain_core.callbacks import BaseCallbackHandler

WRITER_PROMPT = """你是小红书爆款笔记写手。请围绕标题「{topic}」写一篇笔记正文。

要求：
- 中文，100-200 字
- 开头一句话抓住眼球，中间分点讲干货，结尾引导互动
- 语气像真人在分享，不要像公文
- 不要重复标题，直接写正文
"""
class TokenCounter(BaseCallbackHandler):
    def __init__(self):
        self.input_tokens = 0
        self.output_tokens = 0
        self.calls = 0

    def on_llm_end(self, response, **kwargs):
        self.calls += 1
        try:
            msg = response.generations[0][0].message
            usage = getattr(msg, "usage_metadata", None)
            if usage:
                self.input_tokens += usage.get("input_tokens", 0)
                self.output_tokens += usage.get("output_tokens", 0)
        except Exception:
            pass

    def summary(self):
        return {
            "calls": self.calls,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.input_tokens + self.output_tokens,
        }

class TopicList(BaseModel):
    topics: list[str] = Field(description="5 个小红书候选标题")

structured_llm = llm_fast.with_structured_output(TopicList, method="json_mode")


def plan_topics(state: AgentState):
    direction = state.get("topic_direction", "")
    result = structured_llm.invoke(f"为「{direction}」生成 5 个小红书爆款标题")
    return {"generated_topics": result.topics}

def write_draft(state: AgentState):
    topic = state.get("selected_topic", "")
    feedback = state.get("review_feedback", "")
    prompt = WRITER_PROMPT.format(topic=topic)
    if feedback:
        prompt += f"\n\n上一版的问题是：{feedback}\n请针对性修改。"
    result = llm_pro.invoke(prompt)
    return {"article_content": result.content}



def review_node(state: AgentState):
    decision = interrupt({
        "message": "请审核这篇文章",
        "article": state.get("article_content", ""),
    })
    if decision == "approve":
        return {"review_status": "approved", "review_feedback": ""}
    else:
        return {"review_status": "rejected", "review_feedback": ""}


def route_after_review(state: AgentState):
    if state.get("review_status") == "rejected":
        return "rewrite"
    return "done"

class VisualPoints(BaseModel):
    points: list[str] = Field(description="3 条配图画面描述，每条一句话，具体到画面内容、风格、色调")

visual_llm = llm_pro.with_structured_output(VisualPoints)

def extract_visuals(state: AgentState):
    article = state.get("article_content", "")
    try:
        result = visual_llm.invoke(f"从下面这篇笔记里提取 3 个适合配图的画面描述：\n\n{article}")
        return {"visual_points": result.points}
    except Exception as e:
        print(f"提取配图点失败: {e}")
        return {"visual_points": []}




async def _gen_one(client, point, index, max_retries=3):
    t0 = time.time()
    for attempt in range(max_retries):                    # ① 重试循环就在这里
        try:                                              # ② 请求包进 try
            resp = await client.post(
                "https://ark.cn-beijing.volces.com/api/v3/images/generations",
                headers={"Authorization": f"Bearer {settings.llm_api_key}"},
                json={
                    "model": "doubao-seedream-5-0-pro-260628",
                    "prompt": point,
                    "size": "2K",
                    "response_format": "b64_json",
                    "watermark": False,
                },
            )
            resp.raise_for_status()
            b64 = resp.json()["data"][0]["b64_json"]

            filename = f"img_{index}_{uuid.uuid4().hex[:6]}.png"
            Path(filename).write_bytes(base64.b64decode(b64))
            print(f"第 {index} 张完成，耗时 {time.time() - t0:.1f}s")
            return filename                            # ③ 成功立刻返回，不再重试

        except Exception as e:                          # ④ 失败走这里
            if attempt == max_retries - 1:              # ⑤ 判断是不是最后一次
                print(f"第 {index} 张重试 {max_retries} 次仍失败: {e}")
                return None                             # ⑥ 就是这个 return None
            wait = 2 ** attempt                         # ⑦ 1秒 → 2秒 → 4秒
            print(f"第 {index} 张失败（{e}），{wait}s 后重试")
            await asyncio.sleep(wait)



async def generate_images(state: AgentState):
    t0 = time.time()
    print("开始生成图片...")
    points = state.get("visual_points", [])
    if not points:
        return {"image_urls": []}

    async with httpx.AsyncClient(timeout=120) as client:
        results = await asyncio.gather(
            *[_gen_one(client, point, i) for i, point in enumerate(points)]
        )

    image_urls = [r for r in results if r]
    print(f"图片生成完成: {image_urls}（成功 {len(image_urls)}/{len(points)} 张）")
    print(f"配图总耗时 {time.time() - t0:.1f}s")
    return {"image_urls": image_urls}




