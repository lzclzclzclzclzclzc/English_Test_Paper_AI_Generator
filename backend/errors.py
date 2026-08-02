from __future__ import annotations

import logging
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from ai_engine.errors import (
    AIEngineError,
    ParserError,
    RetrieverError,
    ReviserError,
    SolutionerError,
)
from shared.config import get_config
from backend.schemas import ErrorResponse

logger = logging.getLogger(__name__)


class BackendError(Exception):
    error_code = "server.internal"
    http_status = 500
    message = "服务器内部错误"

    def __init__(self, detail: object | None = None):
        super().__init__(str(detail) if detail is not None else self.message)
        self.detail = detail


class AuthenticationError(BackendError):
    error_code = "auth.unauthorized"
    http_status = 401
    message = "未登录或会话已过期"


class AuthorizationError(BackendError):
    error_code = "auth.forbidden"
    http_status = 403
    message = "无权访问"


class UsernameConflictError(BackendError):
    error_code = "auth.username_conflict"
    http_status = 409
    message = "用户名已被占用"


class InvalidCredentialsError(BackendError):
    error_code = "auth.invalid_credentials"
    http_status = 401
    message = "用户名或密码错误"


class ResourceNotFoundError(BackendError):
    error_code = "resource.not_found"
    http_status = 404
    message = "资源不存在"


class ValidationError(BackendError):
    error_code = "request.invalid"
    http_status = 422
    message = "请求参数错误"


class AdminOperationError(BackendError):
    error_code = "admin.invalid_operation"
    http_status = 400
    message = "非法的管理操作"


class RateLimitError(BackendError):
    error_code = "rate.exceeded"
    http_status = 429
    message = "请求过于频繁，请稍后再试"


class AIParserFailedError(BackendError):
    error_code = "ai.parser_failed"
    http_status = 400
    message = "AI 无法理解请求"


class AINoCandidateError(BackendError):
    error_code = "ai.no_candidate"
    http_status = 422
    message = "题库中找不到匹配的题"


class AIReviserFailedError(BackendError):
    error_code = "ai.reviser_failed"
    http_status = 500
    message = "AI 改题失败"


class AISolutionerFailedError(BackendError):
    error_code = "ai.solutioner_failed"
    http_status = 500
    message = "AI 解析生成失败"


class AILLMUpstreamError(BackendError):
    error_code = "ai.llm_upstream"
    http_status = 502
    message = "LLM 服务上游异常"


class AIInternalError(BackendError):
    error_code = "ai.internal"
    http_status = 500
    message = "AI Engine 内部异常"


class PaymentUpstreamError(BackendError):
    error_code = "payment.upstream"
    http_status = 502
    message = "支付服务不可用"


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(BackendError)
    async def handle_backend_error(request: Request, exc: BackendError) -> JSONResponse:
        return backend_error_response(exc, request)

    @app.exception_handler(AIEngineError)
    async def handle_ai_engine_error(request: Request, exc: AIEngineError) -> JSONResponse:
        return backend_error_response(map_ai_error(exc), request)

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        return backend_error_response(ValidationError(exc.errors()), request)

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled backend error")
        return backend_error_response(BackendError(str(exc)), request)


def backend_error_response(exc: BackendError, request: Request | None = None) -> JSONResponse:
    trace_id = _request_trace_id(request)
    logger.error("[%s] %s: %s", trace_id, type(exc).__name__, exc)
    detail = None if get_config().backend.env == "production" else exc.detail
    body = ErrorResponse(
        error_code=exc.error_code,
        message=exc.message,
        detail=detail,  # type: ignore[arg-type]
        trace_id=trace_id,
    )
    return JSONResponse(status_code=exc.http_status, content=body.model_dump(mode="json"))


def _request_trace_id(request: Request | None) -> str:
    if request is None:
        return uuid4().hex
    trace_id = getattr(request.state, "trace_id", None)
    if isinstance(trace_id, str) and trace_id:
        return trace_id
    trace_id = uuid4().hex
    request.state.trace_id = trace_id
    return trace_id


def map_ai_error(exc: AIEngineError) -> BackendError:
    if isinstance(exc, ParserError):
        return AIParserFailedError(str(exc))
    if isinstance(exc, RetrieverError):
        return AINoCandidateError(str(exc))
    if isinstance(exc, ReviserError):
        return AIReviserFailedError(str(exc))
    if isinstance(exc, SolutionerError):
        return AISolutionerFailedError(str(exc))
    return AIInternalError(str(exc))
