from collections.abc import Sequence
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.user import User, UserCredential, UserRole
from app.repositories.base import CRUDRepository


class UserRepository(CRUDRepository[User]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, User)

    def _default_options(self) -> Sequence[Any]:
        """常に認証情報(credential)も同時にロードする。"""
        return (selectinload(User.credential),)

    async def get_by_email(self, email: str) -> User | None:
        """email(UserCredential側)でUserを取得する。認証情報(credential)も同時にロードする。"""
        result = await self._session.execute(
            self._select().join(User.credential).where(UserCredential.email == email)
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        *,
        email: str,
        hashed_password: str,
        display_name: str | None = None,
        role: UserRole = UserRole.USER,
    ) -> User:
        """UserとUserCredential(email・パスワード・role)を1組作成する。"""
        user = User(display_name=display_name)
        user.credential = UserCredential(email=email, hashed_password=hashed_password, role=role)
        self._session.add(user)
        await self._session.flush()
        return user
