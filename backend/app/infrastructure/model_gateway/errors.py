from __future__ import annotations

from enum import StrEnum


class ModelErrorCode(StrEnum):
    MODEL_TIMEOUT = "MODEL_TIMEOUT"
    MODEL_RATE_LIMITED = "MODEL_RATE_LIMITED"
    MODEL_SCHEMA_INVALID = "MODEL_SCHEMA_INVALID"
    MODEL_CONTENT_REJECTED = "MODEL_CONTENT_REJECTED"
    MODEL_CONTEXT_EXCEEDED = "MODEL_CONTEXT_EXCEEDED"
    MODEL_RESPONSE_UNAVAILABLE = "MODEL_RESPONSE_UNAVAILABLE"
    MODEL_REQUEST_FAILED = "MODEL_REQUEST_FAILED"


_DEFAULT_MESSAGES = {
    ModelErrorCode.MODEL_TIMEOUT: "模型请求超时",
    ModelErrorCode.MODEL_RATE_LIMITED: "模型服务请求过于频繁",
    ModelErrorCode.MODEL_SCHEMA_INVALID: "模型输出不符合要求的结构",
    ModelErrorCode.MODEL_CONTENT_REJECTED: "模型服务拒绝了请求内容",
    ModelErrorCode.MODEL_CONTEXT_EXCEEDED: "模型上下文超过限制",
    ModelErrorCode.MODEL_RESPONSE_UNAVAILABLE: "没有可用的模型响应",
    ModelErrorCode.MODEL_REQUEST_FAILED: "模型请求失败",
}

_RETRYABLE_CODES = {
    ModelErrorCode.MODEL_TIMEOUT,
    ModelErrorCode.MODEL_RATE_LIMITED,
    ModelErrorCode.MODEL_REQUEST_FAILED,
}


class ModelGatewayError(Exception):
    def __init__(
        self,
        code: ModelErrorCode,
        message: str | None = None,
        *,
        http_status: int | None = None,
        retryable: bool | None = None,
        details: tuple[str, ...] = (),
    ) -> None:
        self.code = code
        self.message = message or _DEFAULT_MESSAGES[code]
        self.http_status = (
            http_status
            if http_status is not None
            else 429
            if code is ModelErrorCode.MODEL_RATE_LIMITED
            else None
        )
        self.retryable = retryable if retryable is not None else code in _RETRYABLE_CODES
        self.details = details
        super().__init__(f"{code.value}: {self.message}")
