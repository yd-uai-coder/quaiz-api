from app.ai.graph.state import GraphState
from app.ai.llm.gemini import get_gemini_llm
from app.ai.tools.tavily import get_tavily_search_tool
from app.models.quiz import (
    COMMENTARY_MAX_LENGTH,
    OPTION_CONTENT_MAX_LENGTH,
    QUESTION_MAX_LENGTH,
    REQUIRED_OPTION_COUNT,
    TITLE_MAX_LENGTH,
)
from app.schemas.quiz_generation import GeneratedAnswer, GeneratedQuestion, GeneratedQuiz

MAX_GENERATION_ATTEMPTS = 3

_QUESTION_PROMPT_TEMPLATE = """あなたはクイズ作成者です。以下の条件で四択クイズの
「タイトル」と「問題文」だけを作成してください。
選択肢や正解はまだ書かないでください(後の工程で作成します)。

カテゴリ: {category}
キーワード: {keywords}
難易度: {difficulty_name}({difficulty_description})

- タイトルは{title_max}文字以内にする
- 問題文は{question_max}文字以内にする
- 難易度に見合った問題文の難しさにする
"""

_ANSWER_PROMPT_TEMPLATE = """あなたはクイズ作成者です。以下の問題文に対する
四択クイズの選択肢と解説を作成してください。
Web検索結果を参考に、事実として正確な内容にしてください。

問題文: {question}
難易度: {difficulty_name}({difficulty_description})
Web検索結果: {search_results}

- 選択肢はちょうど4つ作成し、正解は1つだけにする
- 各選択肢は{option_max}文字以内にする
- 解説(commentary)には正解の理由を{commentary_max}文字以内で書く
- 誤答の選択肢は難易度に見合った紛らわしさにする
  (難易度が高いほど紛らわしく、低いほど明確に誤りとわかるようにする)
"""


def generate_question(state: GraphState) -> dict:
    """Geminiに構造化出力(GeneratedQuestion)でクイズの「タイトル」「問題文」だけを生成させる。"""
    llm = get_gemini_llm().with_structured_output(GeneratedQuestion)
    prompt = _QUESTION_PROMPT_TEMPLATE.format(
        category=state["category"],
        keywords="、".join(state["keywords"]) if state["keywords"] else "指定なし",
        difficulty_name=state["difficulty_name"],
        difficulty_description=state["difficulty_description"],
        title_max=TITLE_MAX_LENGTH,
        question_max=QUESTION_MAX_LENGTH,
    )
    question_data = llm.invoke(prompt)
    return {"question_data": question_data}


def search_answer(state: GraphState) -> dict:
    """Tavilyで問題文の答えをWeb検索し、次のGemini呼び出しの根拠情報にする。"""
    tool = get_tavily_search_tool()
    raw_results = tool.invoke({"query": state["question_data"].question})
    results = raw_results.get("results", []) if isinstance(raw_results, dict) else raw_results
    return {"search_results": results}


def generate_answer(state: GraphState) -> dict:
    """検索結果を根拠にGeminiへ構造化出力(GeneratedAnswer)で選択肢・解説を生成させ、
    質問文と組み合わせて完成したGeneratedQuizを作る。呼び出すたびattemptを1つ進める。
    """
    llm = get_gemini_llm().with_structured_output(GeneratedAnswer)
    question_data = state["question_data"]
    prompt = _ANSWER_PROMPT_TEMPLATE.format(
        question=question_data.question,
        difficulty_name=state["difficulty_name"],
        difficulty_description=state["difficulty_description"],
        search_results=state["search_results"],
        option_max=OPTION_CONTENT_MAX_LENGTH,
        commentary_max=COMMENTARY_MAX_LENGTH,
    )
    answer_data = llm.invoke(prompt)
    quiz_data = GeneratedQuiz(
        title=question_data.title,
        question=question_data.question,
        options=answer_data.options,
        commentary=answer_data.commentary,
    )
    return {"quiz_data": quiz_data, "attempt": state["attempt"] + 1}


def validate_quiz(state: GraphState) -> dict:
    """生成結果を検証する: 文字数がDBカラム長以内か、選択肢が4つで正解がちょうど1つか。"""
    quiz_data = state["quiz_data"]
    if quiz_data is None:
        return {"validation_errors": ["クイズが生成されませんでした"]}

    errors: list[str] = []
    if len(quiz_data.title) > TITLE_MAX_LENGTH:
        errors.append(f"タイトルが{TITLE_MAX_LENGTH}文字を超えています")
    if len(quiz_data.question) > QUESTION_MAX_LENGTH:
        errors.append(f"問題文が{QUESTION_MAX_LENGTH}文字を超えています")
    if len(quiz_data.commentary) > COMMENTARY_MAX_LENGTH:
        errors.append(f"解説が{COMMENTARY_MAX_LENGTH}文字を超えています")
    if len(quiz_data.options) != REQUIRED_OPTION_COUNT:
        errors.append(f"選択肢は{REQUIRED_OPTION_COUNT}つ必要です")
    if sum(1 for option in quiz_data.options if option.is_correct) != 1:
        errors.append("正解の選択肢はちょうど1つにしてください")
    if any(len(option.content) > OPTION_CONTENT_MAX_LENGTH for option in quiz_data.options):
        errors.append(f"選択肢は{OPTION_CONTENT_MAX_LENGTH}文字以内にしてください")

    return {"validation_errors": errors}


def decide_after_validation(state: GraphState) -> str:
    """バリデーションOKならfinalize、NGでも再試行回数が残っていればretry、それ以外はfinalize(諦める)。"""
    if not state["validation_errors"]:
        return "finalize"
    if state["attempt"] < MAX_GENERATION_ATTEMPTS:
        return "retry"
    return "finalize"


def finalize(state: GraphState) -> dict:
    """グラフの終端ノード。状態はそのままENDへ渡す(成功/失敗の判定は呼び出し元がvalidation_errorsで行う)。"""
    return {}
