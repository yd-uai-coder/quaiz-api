import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.graph.workflow import get_chat_workflow
from app.models.conversation import Conversation, Message
from app.repositories.conversation import ConversationRepository


class ConversationNotFoundError(Exception):
    pass


class ChatService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._conversations = ConversationRepository(session)

    async def send_message(
        self, *, user_id: uuid.UUID, conversation_id: uuid.UUID | None, message: str
    ) -> tuple[Conversation, Message]:
        conversation = await self._get_or_create_conversation(
            user_id=user_id, conversation_id=conversation_id, first_message=message
        )
        await self._conversations.add_message(
            conversation_id=conversation.id, role="user", content=message
        )

        workflow = get_chat_workflow()
        result = await workflow.ainvoke(
            {
                "question": message,
                "messages": [],
                "needs_search": False,
                "search_query": "",
                "search_results": [],
                "evaluation": "",
                "answer": "",
            }
        )

        assistant_message = await self._conversations.add_message(
            conversation_id=conversation.id, role="assistant", content=result["answer"]
        )
        await self._session.commit()
        return conversation, assistant_message

    async def _get_or_create_conversation(
        self, *, user_id: uuid.UUID, conversation_id: uuid.UUID | None, first_message: str
    ) -> Conversation:
        if conversation_id is None:
            title = first_message[:80]
            return await self._conversations.create(user_id=user_id, title=title)

        conversation = await self._conversations.get_by_id(conversation_id, user_id=user_id)
        if conversation is None:
            raise ConversationNotFoundError(f"Conversation {conversation_id} not found")
        return conversation
