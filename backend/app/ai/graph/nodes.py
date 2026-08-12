from langchain_core.messages import HumanMessage

from app.ai.graph.state import GraphState
from app.ai.llm.gemini import get_gemini_llm
from app.ai.tools.tavily import get_tavily_search_tool


def draft_response(state: GraphState) -> dict:
    llm = get_gemini_llm()
    response = llm.invoke([HumanMessage(content=state["question"])])
    return {
        "messages": [response],
        "needs_search": True,
        "search_query": state["question"],
    }


def web_search(state: GraphState) -> dict:
    tool = get_tavily_search_tool()
    raw_results = tool.invoke({"query": state["search_query"]})
    results = raw_results.get("results", []) if isinstance(raw_results, dict) else raw_results
    return {"search_results": results}


def evaluate_search_results(state: GraphState) -> dict:
    llm = get_gemini_llm(temperature=0)
    prompt = (
        f"Question: {state['question']}\n"
        f"Search results: {state['search_results']}\n\n"
        "Briefly evaluate whether these results are relevant and sufficient "
        "to answer the question."
    )
    response = llm.invoke([HumanMessage(content=prompt)])
    return {"evaluation": response.content}


def generate_final_answer(state: GraphState) -> dict:
    llm = get_gemini_llm()
    prompt = (
        f"Question: {state['question']}\n"
        f"Search results: {state['search_results']}\n"
        f"Evaluation: {state['evaluation']}\n\n"
        "Using the above, write the final answer for the user."
    )
    response = llm.invoke([HumanMessage(content=prompt)])
    return {"answer": response.content, "messages": [response]}


def finalize_without_search(state: GraphState) -> dict:
    last_message = state["messages"][-1]
    return {"answer": last_message.content}


def decide_to_search(state: GraphState) -> str:
    return "search" if state.get("needs_search") else "finalize"
