from langchain_openai import ChatOpenAI
from config import settings
from pydantic import BaseModel, Field
from state import AgentState
llm = ChatOpenAI(
    model=settings.llm_model,
    api_key=settings.llm_api_key,
    base_url=settings.llm_base_url,
    temperature=0.7,
    extra_body={"thinking": {"type": "disabled"}}
)

class TopicList(BaseModel):
    topics: list[str] = Field(description="5 个小红书候选标题")


structured_llm = llm.with_structured_output(TopicList)

def plan_topics(state: AgentState):
    direction = state.get("topic_direction", "")
    result = structured_llm.invoke(f"为「{direction}」生成 5 个小红书爆款标题")
    return {"generated_topics": result.topics}

