from langchain_openai import ChatOpenAI
from config import settings
from pydantic import BaseModel, Field
from state import AgentState
llm_pro = ChatOpenAI(
    model=settings.llm_model_pro,
    api_key=settings.llm_api_key,
    base_url=settings.llm_base_url,
    temperature=0.7,
    extra_body={"thinking": {"type": "disabled"}},
)

llm_fast = ChatOpenAI(
    model=settings.llm_model_fast,
    api_key="ollama",
    base_url=settings.llm_base_url_fast,
    temperature=0.9,
    max_tokens=800,
)



