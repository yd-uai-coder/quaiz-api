from fastapi import APIRouter, HTTPException, status

from app.api.deps import RedisDep, SessionDep
from app.schemas.auth import AccessToken, LoginRequest, RefreshRequest, TokenPair
from app.schemas.user import UserCreate, UserRead
from app.services.auth import AuthService, InvalidCredentialsError, InvalidTokenError
from app.services.user import UserAlreadyExistsError, UserService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def register(payload: UserCreate, session: SessionDep) -> UserRead:
    try:
        user = await UserService(session).create_user(
            email=payload.email, password=payload.password, full_name=payload.full_name
        )
    except UserAlreadyExistsError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return UserRead.model_validate(user)


@router.post("/login", response_model=TokenPair)
async def login(payload: LoginRequest, session: SessionDep, redis: RedisDep) -> TokenPair:
    auth_service = AuthService(session, redis)
    try:
        user = await auth_service.authenticate(email=payload.email, password=payload.password)
    except InvalidCredentialsError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    access_token, refresh_token = await auth_service.issue_tokens(user)
    return TokenPair(access_token=access_token, refresh_token=refresh_token)


@router.post("/refresh", response_model=AccessToken)
async def refresh(payload: RefreshRequest, session: SessionDep, redis: RedisDep) -> AccessToken:
    auth_service = AuthService(session, redis)
    try:
        access_token = await auth_service.refresh_access_token(payload.refresh_token)
    except InvalidTokenError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    return AccessToken(access_token=access_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(payload: RefreshRequest, session: SessionDep, redis: RedisDep) -> None:
    await AuthService(session, redis).revoke_refresh_token(payload.refresh_token)
