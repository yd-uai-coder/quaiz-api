from functools import lru_cache

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.ai.graph.nodes import (
    decide_to_search,
    draft_response,
    evaluate_search_results,
    finalize_without_search,
    generate_final_answer,
    web_search,
)
from app.ai.graph.state import GraphState


def build_chat_workflow() -> CompiledStateGraph:
    """User -> Gemini -> Tavily -> evaluate results -> Gemini -> final answer."""
    workflow = StateGraph(GraphState)

    workflow.add_node("draft_response", draft_response)
    workflow.add_node("web_search", web_search)
    workflow.add_node("evaluate_search_results", evaluate_search_results)
    workflow.add_node("generate_final_answer", generate_final_answer)
    workflow.add_node("finalize_without_search", finalize_without_search)

    workflow.add_edge(START, "draft_response")
    workflow.add_conditional_edges(
        "draft_response",
        decide_to_search,
        {"search": "web_search", "finalize": "finalize_without_search"},
    )
    workflow.add_edge("web_search", "evaluate_search_results")
    workflow.add_edge("evaluate_search_results", "generate_final_answer")
    workflow.add_edge("generate_final_answer", END)
    workflow.add_edge("finalize_without_search", END)

    return workflow.compile()


@lru_cache
def get_chat_workflow() -> CompiledStateGraph:
    return build_chat_workflow()
