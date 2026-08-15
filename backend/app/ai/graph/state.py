from typing import TypedDict

from app.schemas.quiz_generation import GeneratedQuestion, GeneratedQuiz


class GraphState(TypedDict):
    """State threaded through the quiz-generation workflow graph.

    Flow: generate_question(Gemini) -> search_answer(Tavily)
          -> generate_answer(Gemini、検索結果が根拠) -> validate_quiz
          -> (retry -> generate_answer | finalize)
    """

    category: str
    keywords: list[str]
    question_data: GeneratedQuestion | None
    search_results: list[dict]
    quiz_data: GeneratedQuiz | None
    validation_errors: list[str]
    attempt: int
