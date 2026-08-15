from typing import ClassVar


class AppError(Exception):
    """サービス層で送出するドメイン例外の基底クラス。status_codeがHTTPレスポンスに変換される。"""

    status_code: ClassVar[int] = 400


class BadRequestError(AppError):
    status_code = 400


class UnauthorizedError(AppError):
    status_code = 401


class ForbiddenError(AppError):
    status_code = 403


class NotFoundError(AppError):
    status_code = 404


class ConflictError(AppError):
    status_code = 409


class BadGatewayError(AppError):
    status_code = 502


class TooManyRequestsError(AppError):
    status_code = 429
