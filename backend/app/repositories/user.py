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

    async def get_by_display_name(self, display_name: str) -> User | None:
        """display_nameでUserを取得する。認証情報(credential)も同時にロードする。"""
        result = await self._session.execute(
            self._select().where(User.display_name == display_name)
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        *,
        display_name: str,
        hashed_password: str,
        role: UserRole = UserRole.USER,
    ) -> User:
        """UserとUserCredential(パスワード・role)を1組作成する。"""
        user = User(display_name=display_name)
        user.credential = UserCredential(hashed_password=hashed_password, role=role)
        self._session.add(user)
        await self._session.flush()
        return user

    async def update(
        self,
        user: User,
        *,
        display_name: str | None = None,
        role: UserRole | None = None,
        hashed_password: str | None = None,
    ) -> User:
        """取得済みのUserの一部フィールドを更新する。"""
        if display_name is not None:
            user.display_name = display_name
        if role is not None:
            user.credential.role = role
        if hashed_password is not None:
            user.credential.hashed_password = hashed_password
        await self._session.flush()
        return user
