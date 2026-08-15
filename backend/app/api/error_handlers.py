from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.errors import AppError


async def handle_app_error(_request: Request, exc: AppError) -> JSONResponse:
    """AppErrorとそのサブクラスをexc.status_codeのJSONレスポンス({"detail": ...})に変換する。"""
    return JSONResponse(status_code=exc.status_code, content={"detail": str(exc)})


def register_error_handlers(app: FastAPI) -> None:
    """サービス層のドメイン例外(AppError系)をHTTPレスポンスへ変換するハンドラをまとめて登録する。"""
    app.add_exception_handler(AppError, handle_app_error)
