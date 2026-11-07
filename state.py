from typing import TypedDict, List, Literal

class AgentState(TypedDict, total=False):
    topic_direction: str
    generated_topics: List[str]
    selected_topic: str
    article_content: str
    review_status: Literal["pending", "approved", "rejected"]
    review_feedback: str
    visual_points: List[str]
    image_urls: List[str]


