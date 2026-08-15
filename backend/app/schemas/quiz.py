import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.quiz import (
    COMMENTARY_MAX_LENGTH,
    OPTION_CONTENT_MAX_LENGTH,
    QUESTION_MAX_LENGTH,
    REVIEW_MAX_LENGTH,
    TITLE_MAX_LENGTH,
)
from app.schemas.base import ORMReadModel
from app.schemas.category import CategoryRead
from app.schemas.difficulty_level import DifficultyLevelRead
from app.schemas.keyword import KeywordRead


class QuizOptionRead(ORMReadModel):
    id: uuid.UUID
    content: str
    is_correct: bool


class QuizAttemptRead(ORMReadModel):
    is_correct: bool
    is_favorite: bool
    review: str | None
    updated_at: datetime


class QuizListItem(ORMReadModel):
    id: uuid.UUID
    title: str
    category: CategoryRead
    difficulty_level: DifficultyLevelRead
    created_at: datetime


class QuizRead(BaseModel):
    id: uuid.UUID
    title: str
    question: str
    commentary: str
    category: CategoryRead
    difficulty_level: DifficultyLevelRead
    keywords: list[KeywordRead]
    options: list[QuizOptionRead]
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
    difficulty_level_id: int
    keywords: list[str] = Field(default_factory=list, max_length=10)


class QuizUpdateOption(BaseModel):
    content: str = Field(max_length=OPTION_CONTENT_MAX_LENGTH)
    is_correct: bool


class QuizUpdateRequest(BaseModel):
    title: str = Field(max_length=TITLE_MAX_LENGTH)
    question: str = Field(max_length=QUESTION_MAX_LENGTH)
    commentary: str = Field(max_length=COMMENTARY_MAX_LENGTH)
    options: list[QuizUpdateOption]


class QuizAttemptRequest(BaseModel):
    selected_option_id: uuid.UUID
    favorite: bool | None = None
    review: str | None = Field(default=None, max_length=REVIEW_MAX_LENGTH)


class QuizAttemptResult(BaseModel):
    is_correct: bool
    correct_option_id: uuid.UUID
    commentary: str
    is_favorite: bool
