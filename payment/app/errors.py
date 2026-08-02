import uuid

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class PaymentError(Exception):
    """业务错误,统一映射为主后端同构的错误体 {error_code, message, detail, trace_id}。"""

    def __init__(self, status: int, error_code: str, message: str, detail: object = None):
        super().__init__(message)
        self.status = status
        self.error_code = error_code
        self.message = message
        self.detail = detail


def _envelope(error_code: str, message: str, detail: object = None) -> dict:
    return {
        "error_code": error_code,
        "message": message,
        "detail": detail,
        "trace_id": uuid.uuid4().hex,
    }


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(PaymentError)
    async def payment_error_handler(_: Request, exc: PaymentError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status,
            content=_envelope(exc.error_code, exc.message, exc.detail),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=_envelope("request.invalid", "请求参数不合法", jsonable_encoder(exc.errors())),
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(_: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=500,
            content=_envelope("server.internal", "服务内部错误"),
        )
