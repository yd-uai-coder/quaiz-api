from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUserDep, SessionDep
from app.schemas.chat import ChatRequest, ChatResponse, MessageRead
from app.services.chat import ChatService, ConversationNotFoundError

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
async def send_message(
    payload: ChatRequest, session: SessionDep, current_user: CurrentUserDep
) -> ChatResponse:
    try:
        conversation, message = await ChatService(session).send_message(
            user_id=current_user.id,
            conversation_id=payload.conversation_id,
            message=payload.message,
        )
    except ConversationNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return ChatResponse(
        conversation_id=conversation.id, message=MessageRead.model_validate(message)
    )
