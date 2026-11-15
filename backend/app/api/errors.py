from __future__ import annotations

import logging
import time
from enum import StrEnum
from uuid import UUID, uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ConfigDict
from starlette.middleware.base import RequestResponseEndpoint
from starlette.responses import Response

from app.api.schemas.common import ContractModel
from app.infrastructure.observability import log_context, log_event


class ErrorCode(StrEnum):
    UNSUPPORTED_FILE_TYPE = "UNSUPPORTED_FILE_TYPE"
    FILE_TOO_LARGE = "FILE_TOO_LARGE"
    FILE_COUNT_EXCEEDED = "FILE_COUNT_EXCEEDED"
    ENCRYPTED_FILE = "ENCRYPTED_FILE"
    MACRO_FILE_REJECTED = "MACRO_FILE_REJECTED"
    MALFORMED_FILE = "MALFORMED_FILE"
    PAGE_LIMIT_EXCEEDED = "PAGE_LIMIT_EXCEEDED"
    ROW_LIMIT_EXCEEDED = "ROW_LIMIT_EXCEEDED"
    TEXT_FILE_TOO_LARGE = "TEXT_FILE_TOO_LARGE"
    TEXT_ENCODING_UNCERTAIN = "TEXT_ENCODING_UNCERTAIN"
    INVALID_TEXT_ENCODING = "INVALID_TEXT_ENCODING"
    CSV_DIALECT_UNCERTAIN = "CSV_DIALECT_UNCERTAIN"
    IMAGE_PIXEL_LIMIT_EXCEEDED = "IMAGE_PIXEL_LIMIT_EXCEEDED"
    IMAGE_DIMENSION_LIMIT_EXCEEDED = "IMAGE_DIMENSION_LIMIT_EXCEEDED"
    IMAGE_DECODE_FAILED = "IMAGE_DECODE_FAILED"
    UNSUPPORTED_CONVERSION = "UNSUPPORTED_CONVERSION"
    CONVERSION_VALIDATION_FAILED = "CONVERSION_VALIDATION_FAILED"
    JOB_LIMIT_EXCEEDED = "JOB_LIMIT_EXCEEDED"
    JOB_DEPENDENCY_DEPTH_EXCEEDED = "JOB_DEPENDENCY_DEPTH_EXCEEDED"
    JOB_DEPENDENCY_CYCLE = "JOB_DEPENDENCY_CYCLE"
    JOB_INPUT_UNAVAILABLE = "JOB_INPUT_UNAVAILABLE"
    TEMPLATE_DIAGNOSTIC_BLOCKED = "TEMPLATE_DIAGNOSTIC_BLOCKED"
    TEMPLATE_MAPPING_REQUIRED = "TEMPLATE_MAPPING_REQUIRED"
    GENERATION_SPEC_INVALID = "GENERATION_SPEC_INVALID"
    QUEUE_FULL = "QUEUE_FULL"
    MODEL_UNAVAILABLE = "MODEL_UNAVAILABLE"
    MODEL_OUTPUT_INVALID = "MODEL_OUTPUT_INVALID"
    TOOL_TIMEOUT = "TOOL_TIMEOUT"
    TOOL_FAILED = "TOOL_FAILED"
    VALIDATION_FAILED = "VALIDATION_FAILED"
    PATH_FORBIDDEN = "PATH_FORBIDDEN"
    TASK_NOT_READY = "TASK_NOT_READY"
    ARTIFACT_NOT_AVAILABLE = "ARTIFACT_NOT_AVAILABLE"
    RESULT_GROUP_UNAVAILABLE = "RESULT_GROUP_UNAVAILABLE"
    EVENT_CURSOR_INVALID = "EVENT_CURSOR_INVALID"
    IDEMPOTENCY_CONFLICT = "IDEMPOTENCY_CONFLICT"
    UPLOAD_NOT_FOUND = "UPLOAD_NOT_FOUND"
    UPLOAD_ALREADY_CONSUMED = "UPLOAD_ALREADY_CONSUMED"
    TASK_NOT_FOUND = "TASK_NOT_FOUND"
    CURSOR_INVALID = "CURSOR_INVALID"


class ErrorResponse(ContractModel):
    model_config = ConfigDict(extra="forbid")

    code: ErrorCode
    message: str
    details: dict[str, object]
    request_id: UUID


class AppError(Exception):
    def __init__(
        self,
        code: ErrorCode,
        message: str,
        *,
        status_code: int = 400,
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}


def _request_id(request: Request) -> UUID:
    value = getattr(request.state, "request_id", None)
    if isinstance(value, UUID):
        return value
    request_id = uuid4()
    request.state.request_id = request_id
    return request_id


def _error_response(
    request: Request,
    *,
    status_code: int,
    code: ErrorCode,
    message: str,
    details: dict[str, object] | None = None,
) -> JSONResponse:
    request_id = _request_id(request)
    payload = ErrorResponse(
        code=code,
        message=message,
        details=details or {},
        request_id=request_id,
    )
    return JSONResponse(
        status_code=status_code,
        content=payload.model_dump(mode="json"),
        headers={"X-Request-ID": str(request_id)},
    )


async def _handle_app_error(request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, AppError):
        raise exc
    return _error_response(
        request,
        status_code=exc.status_code,
        code=exc.code,
        message=exc.message,
        details=exc.details,
    )


async def _handle_validation_error(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    if not isinstance(exc, RequestValidationError):
        raise exc
    return _error_response(
        request,
        status_code=422,
        code=ErrorCode.VALIDATION_FAILED,
        message="请求参数不符合接口契约",
        details={"errors": exc.errors()},
    )


async def _request_id_middleware(
    request: Request,
    call_next: RequestResponseEndpoint,
) -> Response:
    started = time.perf_counter()
    incoming = request.headers.get("X-Request-ID")
    try:
        request_id = UUID(incoming) if incoming is not None else uuid4()
    except ValueError:
        request_id = uuid4()
    request.state.request_id = request_id
    with log_context(request_id=str(request_id)):
        try:
            response = await call_next(request)
        except Exception as exc:
            route = getattr(request.scope.get("route"), "path", request.url.path)
            log_event(
                "http.request.failed",
                level=logging.ERROR,
                logger_name="doc_agent.request",
                method=request.method,
                route=route,
                duration_ms=round((time.perf_counter() - started) * 1000),
                error_type=type(exc).__name__,
            )
            raise
        response.headers["X-Request-ID"] = str(request_id)
        route = getattr(request.scope.get("route"), "path", request.url.path)
        log_event(
            "http.request.completed",
            logger_name="doc_agent.request",
            method=request.method,
            route=route,
            status_code=response.status_code,
            duration_ms=round((time.perf_counter() - started) * 1000),
        )
        return response


def install_exception_handlers(app: FastAPI) -> None:
    app.middleware("http")(_request_id_middleware)
    app.add_exception_handler(AppError, _handle_app_error)
    app.add_exception_handler(RequestValidationError, _handle_validation_error)
