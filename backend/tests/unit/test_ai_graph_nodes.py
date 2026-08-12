from langchain_core.messages import AIMessage

from app.ai.graph import nodes


class FakeLLM:
    def __init__(self, content: str) -> None:
        self._content = content

    def invoke(self, _messages):
        return AIMessage(content=self._content)


class FakeSearchTool:
    def __init__(self, results):
        self._results = results

    def invoke(self, _args):
        return {"results": self._results}


def test_decide_to_search_returns_search_when_needed() -> None:
    assert nodes.decide_to_search({"needs_search": True}) == "search"


def test_decide_to_search_returns_finalize_when_not_needed() -> None:
    assert nodes.decide_to_search({"needs_search": False}) == "finalize"


def test_finalize_without_search_uses_last_message_content() -> None:
    state = {"messages": [AIMessage(content="direct answer")]}

    result = nodes.finalize_without_search(state)

    assert result == {"answer": "direct answer"}


def test_draft_response_invokes_llm_and_flags_search(monkeypatch) -> None:
    monkeypatch.setattr(nodes, "get_gemini_llm", lambda **_: FakeLLM("draft"))

    result = nodes.draft_response({"question": "What is LangGraph?"})

    assert result["needs_search"] is True
    assert result["search_query"] == "What is LangGraph?"
    assert result["messages"][0].content == "draft"


def test_web_search_extracts_results_from_tool_response(monkeypatch) -> None:
    monkeypatch.setattr(
        nodes, "get_tavily_search_tool", lambda **_: FakeSearchTool([{"url": "https://x"}])
    )

    result = nodes.web_search({"search_query": "langgraph"})

    assert result["search_results"] == [{"url": "https://x"}]


def test_evaluate_search_results_returns_llm_content(monkeypatch) -> None:
    monkeypatch.setattr(nodes, "get_gemini_llm", lambda **_: FakeLLM("looks relevant"))

    result = nodes.evaluate_search_results(
        {"question": "q", "search_results": [{"url": "https://x"}]}
    )

    assert result == {"evaluation": "looks relevant"}


def test_generate_final_answer_returns_llm_content(monkeypatch) -> None:
    monkeypatch.setattr(nodes, "get_gemini_llm", lambda **_: FakeLLM("final answer"))

    result = nodes.generate_final_answer(
        {"question": "q", "search_results": [], "evaluation": "ok"}
    )

    assert result["answer"] == "final answer"
    assert result["messages"][0].content == "final answer"
