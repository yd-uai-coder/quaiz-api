import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password, verify_password
from app.models.user import User, UserRole
from app.repositories.user import UserRepository
from app.schemas.user import UserUpdateRequest
from app.services.errors import (
    InvalidCurrentPasswordError,
    UserAlreadyExistsError,
    UserNotFoundError,
    UserPermissionDeniedError,
)


class UserService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = UserRepository(session)

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        """IDでユーザーを取得する。"""
        return await self._repo.get_by_id(user_id)

    async def list_users(self) -> list[User]:
        """全ユーザーをdisplay_name昇順で返す(ADMIN専用、呼び出し元ルートで権限を保証する)。"""
        return await self._repo.list_all(order_by=User.display_name)

    async def get_by_display_name(self, display_name: str) -> User | None:
        """display_nameでユーザーを取得する。"""
        return await self._repo.get_by_display_name(display_name)

    async def create_user(self, *, display_name: str, password: str) -> User:
        """新規登録。display_nameの重複チェック後、パスワードをハッシュ化しrole=USERで作成する。"""
        existing = await self._repo.get_by_display_name(display_name)
        if existing is not None:
            raise UserAlreadyExistsError(f"{display_name} は既に使用されています。")

        user = await self._repo.create(
            display_name=display_name,
            hashed_password=hash_password(password),
            role=UserRole.USER,
        )
        await self._session.commit()
        return user

    async def update_user(
        self, *, actor: User, target_user_id: uuid.UUID, data: UserUpdateRequest
    ) -> User:
        """本人またはADMINによるユーザー情報変更。roleの変更はADMINのみ許可する。
        本人が自分のパスワードを変更する場合はcurrent_passwordでの再認証を必須にする。
        """
        is_self = actor.id == target_user_id
        is_admin = actor.role == UserRole.ADMIN
        if not is_self and not is_admin:
            raise UserPermissionDeniedError("この操作を行う権限がありません。")

        target = actor if is_self else await self._repo.get_by_id(target_user_id)
        if target is None:
            raise UserNotFoundError(f"User {target_user_id} not found")

        if data.role is not None and not is_admin:
            raise UserPermissionDeniedError("ロールの変更は管理者のみ行えます。")

        hashed_password = None
        if data.password is not None:
            if is_self and (
                data.current_password is None
                or not verify_password(data.current_password, target.credential.hashed_password)
            ):
                raise InvalidCurrentPasswordError("現在のパスワードが正しくありません。")
            hashed_password = hash_password(data.password)

        if data.display_name is not None and data.display_name != target.display_name:
            existing = await self._repo.get_by_display_name(data.display_name)
            if existing is not None and existing.id != target.id:
                raise UserAlreadyExistsError(f"{data.display_name} は既に使用されています。")

        updated = await self._repo.update(
            target,
            display_name=data.display_name,
            role=data.role,
            hashed_password=hashed_password,
        )
        await self._session.commit()
        return updated

    async def delete_user(self, *, actor: User, target_user_id: uuid.UUID) -> None:
        """本人またはADMINによるユーザー削除。"""
        is_self = actor.id == target_user_id
        if not is_self and actor.role != UserRole.ADMIN:
            raise UserPermissionDeniedError("この操作を行う権限がありません。")

        target = actor if is_self else await self._repo.get_by_id(target_user_id)
        if target is None:
            raise UserNotFoundError(f"User {target_user_id} not found")

        await self._repo.delete(target)
        await self._session.commit()

    async def bulk_delete_users(self, *, user_ids: list[uuid.UUID]) -> None:
        """ADMIN専用の一括削除(呼び出し元ルートでADMINであることを保証する)。"""
        for user_id in user_ids:
            target = await self._repo.get_by_id(user_id)
            if target is not None:
                await self._repo.delete(target)
        await self._session.commit()
