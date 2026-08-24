import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Table,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

# クイズ生成(app/ai/graph/nodes.py)とリクエストスキーマ(app/schemas/quiz.py)がここを
# 唯一の定義元としてimportする。DBカラム長を変える場合はここだけ直せばよい。
TITLE_MAX_LENGTH = 40
QUESTION_MAX_LENGTH = 1000
OPTION_CONTENT_MAX_LENGTH = 200
COMMENTARY_MAX_LENGTH = 1000
REVIEW_MAX_LENGTH = 400
REQUIRED_OPTION_COUNT = 4
DIFFICULTY_LEVEL_NAME_MAX_LENGTH = 20
DIFFICULTY_LEVEL_DESCRIPTION_MAX_LENGTH = 100

quiz_keywords = Table(
    "quiz_keywords",
    Base.metadata,
    Column(
        "quiz_id",
        Uuid(as_uuid=True),
        ForeignKey("quizzes.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "keyword_id",
        Uuid(as_uuid=True),
        ForeignKey("keywords.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    # 複合PK(quiz_id, keyword_id)の後方列だけではkeyword_id単体のGROUP BY/検索に使えないため、
    # キーワード人気ランキング集計(keyword.py: list_ranked_by_quiz_count)用に単独索引を用意する。
    Index("ix_quiz_keywords_keyword_id", "keyword_id"),
)


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    quizzes: Mapped[list["Quiz"]] = relationship(back_populates="category")


class Keyword(Base):
    __tablename__ = "keywords"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    keyword: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    quizzes: Mapped[list["Quiz"]] = relationship(secondary=quiz_keywords, back_populates="keywords")


class DifficultyLevel(Base):
    """クイズの難易度マスタ(level 1〜5固定、シード投入済み)。"""

    __tablename__ = "difficulty_levels"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    level: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(DIFFICULTY_LEVEL_NAME_MAX_LENGTH), nullable=False)
    description: Mapped[str] = mapped_column(
        String(DIFFICULTY_LEVEL_DESCRIPTION_MAX_LENGTH), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    quizzes: Mapped[list["Quiz"]] = relationship(back_populates="difficulty_level")


class Quiz(Base):
    __tablename__ = "quizzes"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(TITLE_MAX_LENGTH), nullable=False)
    question: Mapped[str] = mapped_column(String(QUESTION_MAX_LENGTH), nullable=False)
    category_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("categories.id"), index=True, nullable=False
    )
    created_by_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), index=True, nullable=False
    )
    difficulty_level_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("difficulty_levels.id"), index=True, nullable=False
    )
    commentary: Mapped[str] = mapped_column(String(COMMENTARY_MAX_LENGTH), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    category: Mapped["Category"] = relationship(back_populates="quizzes")
    difficulty_level: Mapped["DifficultyLevel"] = relationship(back_populates="quizzes")
    options: Mapped[list["QuizOption"]] = relationship(
        back_populates="quiz", cascade="all, delete-orphan", order_by="QuizOption.created_at"
    )
    keywords: Mapped[list["Keyword"]] = relationship(
        secondary=quiz_keywords, back_populates="quizzes"
    )
    attempts: Mapped[list["QuizAttempt"]] = relationship(
        back_populates="quiz", cascade="all, delete-orphan"
    )


class QuizOption(Base):
    __tablename__ = "quiz_options"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    quiz_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("quizzes.id", ondelete="CASCADE"), index=True, nullable=False
    )
    content: Mapped[str] = mapped_column(String(OPTION_CONTENT_MAX_LENGTH), nullable=False)
    is_correct: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    quiz: Mapped["Quiz"] = relationship(back_populates="options")


class QuizAttempt(Base):
    """(quiz_id, user_id)ごとに最新の回答状態を1行で保持するUPSERT対象テーブル。"""

    __tablename__ = "quiz_attempts"
    __table_args__ = (
        UniqueConstraint("quiz_id", "user_id", name="uq_quiz_attempts_quiz_id_user_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    quiz_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("quizzes.id", ondelete="CASCADE"), index=True, nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    corrected: Mapped[bool] = mapped_column(Boolean, nullable=False)
    is_favorite: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    review: Mapped[str | None] = mapped_column(String(REVIEW_MAX_LENGTH), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    quiz: Mapped["Quiz"] = relationship(back_populates="attempts")
