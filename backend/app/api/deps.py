import uuid
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import TokenType, decode_token
from app.infrastructure.redis import get_redis
from app.models.user import User, UserRole
from app.services.user import UserService

_bearer_scheme = HTTPBearer(auto_error=False)

SessionDep = Annotated[AsyncSession, Depends(get_db)]
RedisDep = Annotated[Redis, Depends(get_redis)]

_credentials_exception = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


async def get_current_user(
    session: SessionDep,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)],
) -> User:
    if credentials is None:
        raise _credentials_exception

    try:
        payload = decode_token(credentials.credentials)
    except jwt.PyJWTError as exc:
        raise _credentials_exception from exc

    if payload.get("type") != TokenType.ACCESS.value:
        raise _credentials_exception

    try:
        user_id = uuid.UUID(payload["sub"])
    except (KeyError, ValueError) as exc:
        raise _credentials_exception from exc

    user = await UserService(session).get_by_id(user_id)
    if user is None or not user.is_active:
        raise _credentials_exception
    return user


CurrentUserDep = Annotated[User, Depends(get_current_user)]


async def get_current_user_optional(
    session: SessionDep,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)],
) -> User | None:
    """未ログインならNoneを返す(トークン不正時も401にせずNone扱い)。一覧・詳細など認証任意のエンドポイント用。"""
    if credentials is None:
        return None
    try:
        return await get_current_user(session, credentials)
    except HTTPException:
        return None


OptionalCurrentUserDep = Annotated[User | None, Depends(get_current_user_optional)]


async def get_current_admin(current_user: CurrentUserDep) -> User:
    """ADMIN role以外は403にする(クイズ編集・削除など管理者専用エンドポイント用)。"""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Admin privileges required"
        )
    return current_user


CurrentAdminDep = Annotated[User, Depends(get_current_admin)]
