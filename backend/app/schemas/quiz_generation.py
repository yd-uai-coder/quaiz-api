from pydantic import BaseModel, Field


class GeneratedOption(BaseModel):
    content: str = Field(description="選択肢の文言(200文字以内)")
    is_correct: bool = Field(description="この選択肢が正解かどうか")


class GeneratedQuiz(BaseModel):
    """Gemini構造化出力のスキーマ。DBカラム長制約(title/question/commentary/option)に合わせて設計。"""

    title: str = Field(description="クイズのタイトル(40文字以内)")
    question: str = Field(description="クイズの問題文(1000文字以内)")
    options: list[GeneratedOption] = Field(description="選択肢。必ず4つ、正解は1つだけにする")
    commentary: str = Field(description="正解の解説(1000文字以内)")


class GeneratedQuestion(BaseModel):
    """1段階目のGemini構造化出力: タイトルと問題文のみ(選択肢・解説はTavily検索後に生成する)。"""

    title: str = Field(description="クイズのタイトル(40文字以内)")
    question: str = Field(description="クイズの問題文(1000文字以内)")


class GeneratedAnswer(BaseModel):
    """2段階目のGemini構造化出力: Web検索結果を根拠にした選択肢と解説。"""

    options: list[GeneratedOption] = Field(description="選択肢。必ず4つ、正解は1つだけにする")
    commentary: str = Field(description="正解の解説(1000文字以内)")
