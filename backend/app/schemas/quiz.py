import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.quiz import OPTION_CONTENT_MAX_LENGTH, REVIEW_MAX_LENGTH
from app.schemas.base import ORMReadModel
from app.schemas.category import CategoryRead
from app.schemas.difficulty_level import DifficultyLevelRead
from app.schemas.keyword import KeywordRead


class QuizOptionRead(ORMReadModel):
    id: uuid.UUID
    content: str
    is_correct: bool


class QuizAttemptRead(ORMReadModel):
    corrected: bool
    is_favorite: bool
    review: str | None
    updated_at: datetime


class QuizListItem(ORMReadModel):
    id: uuid.UUID
    title: str
    category: CategoryRead
    difficulty_level: DifficultyLevelRead
    keywords: list[KeywordRead]
    created_by_id: uuid.UUID | None
    created_at: datetime
    my_attempt: QuizAttemptRead | None = None


class QuizDetail(BaseModel):
    id: uuid.UUID
    title: str
    question: str
    commentary: str
    difficulty_level: DifficultyLevelRead
    options: list[QuizOptionRead]


class QuizRead(QuizDetail):
    category: CategoryRead
    keywords: list[KeywordRead]
    created_at: datetime
    updated_at: datetime
    my_attempt: QuizAttemptRead | None = None


class QuizListResponse(BaseModel):
    items: list[QuizListItem]
    total: int
    page: int
    limit: int


class QuizGenerateRequest(BaseModel):
    category_id: uuid.UUID
    difficulty_level_id: uuid.UUID | None = None
    keywords: list[str] = Field(default_factory=list, max_length=10)


class QuizUpdateOption(BaseModel):
    # 指定時、対象クイズの既存選択肢のidと一致するかをサービス層で検証する
    # (GET取得時点と送信時点でのID不整合を検知するため)。省略可能なのは、
    # 既存の「id無しで丸ごと入れ替え」契約(件数変更も含む)を壊さないため。
    id: uuid.UUID | None = None
    content: str = Field(max_length=OPTION_CONTENT_MAX_LENGTH)
    is_correct: bool


class QuizUpdateRequest(BaseModel):
    options: list[QuizUpdateOption]


class QuizAttemptRequest(BaseModel):
    corrected: bool
    favorite: bool | None = None
    review: str | None = Field(default=None, max_length=REVIEW_MAX_LENGTH)


class QuizAttemptResult(BaseModel):
    corrected: bool
    is_favorite: bool
