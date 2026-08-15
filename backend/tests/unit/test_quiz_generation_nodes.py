import itertools
from collections.abc import Iterator

from app.ai.graph import nodes
from app.ai.graph.workflow import build_quiz_workflow
from app.schemas.quiz_generation import (
    GeneratedAnswer,
    GeneratedOption,
    GeneratedQuestion,
    GeneratedQuiz,
)


class FakeStructuredLLM:
    def __init__(self, result) -> None:
        self._result = result

    def invoke(self, _prompt):
        return self._result


class FakeLLM:
    """スキーマごとに異なる応答を返すfake。generate_answerは再試行のたびに呼ばれるため、
    answersはイテレータで渡し、呼び出すたびに次の値を返す。
    """

    def __init__(self, *, question: GeneratedQuestion, answers: Iterator[GeneratedAnswer]) -> None:
        self._question = question
        self._answers = answers

    def with_structured_output(self, schema):
        if schema is GeneratedQuestion:
            return FakeStructuredLLM(self._question)
        if schema is GeneratedAnswer:
            return FakeStructuredLLM(next(self._answers))
        raise ValueError(f"unexpected schema: {schema}")


class FakeTavilyTool:
    def __init__(self, results: list[dict] | None = None) -> None:
        self._results = results if results is not None else []

    def invoke(self, _query: dict) -> dict:
        return {"results": self._results}


def _valid_question() -> GeneratedQuestion:
    return GeneratedQuestion(title="日本の首都", question="日本の首都はどこでしょう?")


def _valid_answer() -> GeneratedAnswer:
    return GeneratedAnswer(
        options=[
            GeneratedOption(content="東京", is_correct=True),
            GeneratedOption(content="大阪", is_correct=False),
            GeneratedOption(content="京都", is_correct=False),
            GeneratedOption(content="札幌", is_correct=False),
        ],
        commentary="日本の首都は東京です。",
    )


def _valid_quiz() -> GeneratedQuiz:
    question = _valid_question()
    answer = _valid_answer()
    return GeneratedQuiz(
        title=question.title,
        question=question.question,
        options=answer.options,
        commentary=answer.commentary,
    )


def _initial_state(**overrides) -> dict:
    state = {
        "category": "地理",
        "keywords": [],
        "question_data": None,
        "search_results": [],
        "quiz_data": None,
        "validation_errors": [],
        "attempt": 0,
    }
    state.update(overrides)
    return state


def test_generate_question_invokes_structured_llm(monkeypatch) -> None:
    question = _valid_question()
    monkeypatch.setattr(
        nodes,
        "get_gemini_llm",
        lambda **_: FakeLLM(question=question, answers=iter([_valid_answer()])),
    )

    result = nodes.generate_question(_initial_state(keywords=["日本"]))

    assert result["question_data"] == question


def test_search_answer_invokes_tavily_tool(monkeypatch) -> None:
    monkeypatch.setattr(
        nodes, "get_tavily_search_tool", lambda: FakeTavilyTool([{"title": "首都"}])
    )

    result = nodes.search_answer(_initial_state(question_data=_valid_question()))

    assert result["search_results"] == [{"title": "首都"}]


def test_generate_answer_combines_question_and_answer_and_increments_attempt(monkeypatch) -> None:
    question = _valid_question()
    answer = _valid_answer()
    monkeypatch.setattr(
        nodes, "get_gemini_llm", lambda **_: FakeLLM(question=question, answers=iter([answer]))
    )

    result = nodes.generate_answer(_initial_state(question_data=question, attempt=0))

    quiz_data = result["quiz_data"]
    assert quiz_data.title == question.title
    assert quiz_data.question == question.question
    assert quiz_data.options == answer.options
    assert quiz_data.commentary == answer.commentary
    assert result["attempt"] == 1


def test_validate_quiz_passes_for_valid_quiz() -> None:
    result = nodes.validate_quiz({"quiz_data": _valid_quiz()})

    assert result["validation_errors"] == []


def test_validate_quiz_handles_missing_quiz_data() -> None:
    result = nodes.validate_quiz({"quiz_data": None})

    assert result["validation_errors"]


def test_validate_quiz_rejects_wrong_option_count() -> None:
    quiz = _valid_quiz()
    quiz.options = quiz.options[:3]

    result = nodes.validate_quiz({"quiz_data": quiz})

    assert result["validation_errors"]


def test_validate_quiz_rejects_multiple_correct_options() -> None:
    quiz = _valid_quiz()
    quiz.options[1].is_correct = True

    result = nodes.validate_quiz({"quiz_data": quiz})

    assert result["validation_errors"]


def test_validate_quiz_rejects_oversized_title() -> None:
    quiz = _valid_quiz()
    quiz.title = "あ" * (nodes.TITLE_MAX_LENGTH + 1)

    result = nodes.validate_quiz({"quiz_data": quiz})

    assert result["validation_errors"]


def test_decide_after_validation_finalizes_when_no_errors() -> None:
    assert nodes.decide_after_validation({"validation_errors": [], "attempt": 1}) == "finalize"


def test_decide_after_validation_retries_when_attempts_remain() -> None:
    assert nodes.decide_after_validation({"validation_errors": ["bad"], "attempt": 1}) == "retry"


def test_decide_after_validation_finalizes_after_max_attempts() -> None:
    state = {"validation_errors": ["bad"], "attempt": nodes.MAX_GENERATION_ATTEMPTS}

    assert nodes.decide_after_validation(state) == "finalize"


def test_workflow_retries_until_valid_quiz(monkeypatch) -> None:
    question = _valid_question()
    invalid_answer = _valid_answer()
    invalid_answer.options = invalid_answer.options[:3]
    valid_answer = _valid_answer()

    answers = iter([invalid_answer, valid_answer])
    monkeypatch.setattr(
        nodes, "get_gemini_llm", lambda **_: FakeLLM(question=question, answers=answers)
    )
    monkeypatch.setattr(nodes, "get_tavily_search_tool", lambda: FakeTavilyTool())

    workflow = build_quiz_workflow()
    result = workflow.invoke(_initial_state())

    assert result["validation_errors"] == []
    assert result["attempt"] == 2


def test_workflow_gives_up_after_max_attempts(monkeypatch) -> None:
    question = _valid_question()
    invalid_answer = _valid_answer()
    invalid_answer.options = invalid_answer.options[:3]

    answers = itertools.repeat(invalid_answer)
    monkeypatch.setattr(
        nodes, "get_gemini_llm", lambda **_: FakeLLM(question=question, answers=answers)
    )
    monkeypatch.setattr(nodes, "get_tavily_search_tool", lambda: FakeTavilyTool())

    workflow = build_quiz_workflow()
    result = workflow.invoke(_initial_state())

    assert result["validation_errors"]
    assert result["attempt"] == nodes.MAX_GENERATION_ATTEMPTS
