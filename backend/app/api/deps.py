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

##HTTPBearer は FastAPI が提供するセキュリティクラス
##Authorizationヘッダーが無い場合に例外を投げない（Noneを返す）
_bearer_scheme = HTTPBearer(auto_error=False)

type SessionDep = Annotated[AsyncSession, Depends(get_db)]
type RedisDep = Annotated[Redis, Depends(get_redis)]

##認証失敗時に投げる例外
##失敗時にクライアントに渡るメッセージを統一することで、どの検証で失敗したかを隠蔽する
_credentials_exception = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="認証に失敗しました",
    headers={"WWW-Authenticate": "Bearer"},
)


async def get_current_user(
    session: SessionDep,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)],
) -> User:
    """JWT,TOKEN,UUIDの検証をし、DBからユーザーを取得する"""
    if credentials is None:
        raise _credentials_exception

    # JWTを検証・デコード。壊れたトークンならjwt.PyJWTError→401に変換。
    try:
        payload = decode_token(credentials.credentials)
    except jwt.PyJWTError as exc:
        raise _credentials_exception from exc

    # 渡されたのが本当にaccessトークンか確認(refreshトークンを誤って使われるのを防ぐ)。
    if payload.get("type") != TokenType.ACCESS.value:
        raise _credentials_exception

    # (ユーザーID)をUUIDに変換。壊れていれば401
    try:
        user_id = uuid.UUID(payload["sub"])
    except (KeyError, ValueError) as exc:
        raise _credentials_exception from exc

    # DBからユーザーを取得。存在しない、またはis_active=Falseなら401。
    user = await UserService(session).get_by_id(user_id)
    if user is None or not user.is_active:
        raise _credentials_exception
    return user


type CurrentUserDep = Annotated[User, Depends(get_current_user)]


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


type OptionalCurrentUserDep = Annotated[User | None, Depends(get_current_user_optional)]


async def get_current_admin(current_user: CurrentUserDep) -> User:
    """ADMIN role以外は403にする(クイズ編集・削除など管理者専用エンドポイント用)。"""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Admin privileges required"
        )
    return current_user


type CurrentAdminDep = Annotated[User, Depends(get_current_admin)]
