from functools import lru_cache

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.ai.graph.nodes import (
    decide_after_validation,
    finalize,
    generate_answer,
    generate_question,
    search_answer,
    validate_quiz,
)
from app.ai.graph.state import GraphState


def build_quiz_workflow() -> CompiledStateGraph:
    """generate_question(Gemini) -> search_answer(Tavily) -> generate_answer(Gemini)
    -> validate_quiz -> (retry -> generate_answer | finalize)。
    """
    workflow = StateGraph(GraphState)

    workflow.add_node("generate_question", generate_question)
    workflow.add_node("search_answer", search_answer)
    workflow.add_node("generate_answer", generate_answer)
    workflow.add_node("validate_quiz", validate_quiz)
    workflow.add_node("finalize", finalize)

    workflow.add_edge(START, "generate_question")
    workflow.add_edge("generate_question", "search_answer")
    workflow.add_edge("search_answer", "generate_answer")
    workflow.add_edge("generate_answer", "validate_quiz")
    workflow.add_conditional_edges(
        "validate_quiz",
        decide_after_validation,
        {"retry": "generate_answer", "finalize": "finalize"},
    )
    workflow.add_edge("finalize", END)

    return workflow.compile()


@lru_cache
def get_quiz_workflow() -> CompiledStateGraph:
    """コンパイル済みグラフをプロセス内でキャッシュして返す(毎回コンパイルし直さないため)。"""
    return build_quiz_workflow()
