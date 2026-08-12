import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

MessageRole = Literal["user", "assistant", "system", "tool"]


class MessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    role: MessageRole
    content: str
    created_at: datetime


class ConversationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str | None
    created_at: datetime
    updated_at: datetime


class ConversationDetail(ConversationRead):
    messages: list[MessageRead] = []


class ChatRequest(BaseModel):
    conversation_id: uuid.UUID | None = None
    message: str


class ChatResponse(BaseModel):
    conversation_id: uuid.UUID
    message: MessageRead
