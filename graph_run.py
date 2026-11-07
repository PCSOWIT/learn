from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import interrupt, Command
from langgraph.graph import StateGraph, START, END

from nodes import write_draft, plan_topics, review_node, route_after_review, extract_visuals, generate_images
from state import AgentState

from pydantic import BaseModel, Field




def select_node(state: AgentState):
    options = state.get("generated_topics", [])
    chosen = interrupt({"message": "请选一个选题", "options": options})
    return {"selected_topic": chosen}

builder = StateGraph(AgentState)
builder.add_node("plan", plan_topics)
builder.add_node("select", select_node)
builder.add_node("write", write_draft)
builder.add_node("review", review_node)
builder.add_edge(START, "plan")
builder.add_edge("plan", "select")
builder.add_edge("select", "write")
builder.add_edge("write", "review")
builder.add_conditional_edges("review", route_after_review, {"rewrite": "write", "done": "visuals"})
builder.add_node("visuals", extract_visuals)
builder.add_node("images", generate_images)
builder.add_edge("visuals", "images")
builder.add_edge("images", END)


# graph = builder.compile(checkpointer=MemorySaver())
#
# config = {"configurable": {"thread_id": "user-001"}}
#
# print("第一次调用：")
# result = graph.invoke({"topic_direction": "无畏契约新手攻略"}, config)
# print(result)
#
# print("暂停中的状态：", graph.get_state(config).values)
#
# print("恢复调用：")
# final = graph.invoke(Command(resume="标题B"), config)
# print(final)
