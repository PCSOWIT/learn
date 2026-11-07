from langgraph.types import interrupt

from llm import llm
from state import AgentState
from pydantic import BaseModel, Field

import httpx, base64, uuid
from pathlib import Path
from config import settings
WRITER_PROMPT = """你是小红书爆款笔记写手。请围绕标题「{topic}」写一篇笔记正文。

要求：
- 中文，100-200 字
- 开头一句话抓住眼球，中间分点讲干货，结尾引导互动
- 语气像真人在分享，不要像公文
- 不要重复标题，直接写正文
"""
class TopicList(BaseModel):
    topics: list[str] = Field(description="5 个小红书候选标题")

structured_llm = llm.with_structured_output(TopicList)

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
    result = llm.invoke(prompt)
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

visual_llm = llm.with_structured_output(VisualPoints)

def extract_visuals(state: AgentState):
    article = state.get("article_content", "")
    try:
        result = visual_llm.invoke(f"从下面这篇笔记里提取 3 个适合配图的画面描述：\n\n{article}")
        return {"visual_points": result.points}
    except Exception as e:
        print(f"提取配图点失败: {e}")
        return {"visual_points": []}




def generate_images(state: AgentState):
    print("开始生成图片...")
    points = state.get("visual_points", [])
    image_urls = []

    for i, point in enumerate(points):
        resp = httpx.post(
            "https://ark.cn-beijing.volces.com/api/v3/images/generations",
            headers={"Authorization": f"Bearer {settings.llm_api_key}"},
            json={
                "model": "doubao-seedream-5-0-pro-260628",
                "prompt": point,
                "size": "2K",
                "response_format": "b64_json",
                "watermark": False,
            },
            timeout=120,
        )
        resp.raise_for_status()
        b64 = resp.json()["data"][0]["b64_json"]

        filename = f"img_{i}_{uuid.uuid4().hex[:6]}.png"
        Path(filename).write_bytes(base64.b64decode(b64))
        image_urls.append(filename)

    return {"image_urls": image_urls}



