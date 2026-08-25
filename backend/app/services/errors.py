"""サービス層で共通に使う例外クラス。複数サービス間の循環importを避けるため、
定義をここに集約する。
"""

from app.core.errors import (
    BadGatewayError,
    BadRequestError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
    TooManyRequestsError,
    UnauthorizedError,
)


class UserAlreadyExistsError(ConflictError):
    pass


class InvalidCredentialsError(UnauthorizedError):
    pass


class InvalidTokenError(UnauthorizedError):
    pass


class CategoryNotFoundError(NotFoundError):
    pass


class DifficultyLevelNotFoundError(NotFoundError):
    pass


class QuizNotFoundError(NotFoundError):
    pass


class QuizGenerationFailedError(BadGatewayError):
    pass


class QuizGenerationRateLimitExceededError(TooManyRequestsError):
    pass


class QuizPermissionDeniedError(ForbiddenError):
    pass


class QuizValidationError(BadRequestError):
    pass


class UserPermissionDeniedError(ForbiddenError):
    pass


class InvalidCurrentPasswordError(BadRequestError):
    pass


class UserNotFoundError(NotFoundError):
    pass
