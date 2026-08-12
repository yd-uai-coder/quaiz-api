from typing import Annotated, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class GraphState(TypedDict):
    """State threaded through the chat workflow graph.

    Flow: User -> Gemini -> Tavily -> evaluate results -> Gemini -> final answer.
    """

    messages: Annotated[list[BaseMessage], add_messages]
    question: str
    needs_search: bool
    search_query: str
    search_results: list[dict]
    evaluation: str
    answer: str
