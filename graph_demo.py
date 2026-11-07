from langgraph.graph import StateGraph, START, END
from state import AgentState

def node_a(state: AgentState):
    print("[节点A] 收到方向:", state["topic_direction"])
    return {"topic_direction": state["topic_direction"] + "｜已确认"}

def node_b(state: AgentState):
    print("[节点B] 收到方向:", state["topic_direction"])
    return {"generated_topics": ["标题一", "标题二", "标题三"]}

builder = StateGraph(AgentState)
builder.add_node("a", node_a)
builder.add_node("b", node_b)
builder.add_edge(START, "a")
builder.add_edge("a", "b")
builder.add_edge("b", END)

graph = builder.compile()

result = graph.invoke({"topic_direction": "无畏契约新手攻略"})
print("最终状态:", result)
