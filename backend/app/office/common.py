"""BE3 共享契约：统一返回格式、异常包装、工具元信息基类。

本模块不导入任何 BE1/BE2 骨架代码（ToolRegistry 等）。
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

# 统一返回码
CODE_OK = 0
CODE_INVALID_ARGUMENT = 1001
CODE_FILE_NOT_FOUND = 1002
CODE_UNSUPPORTED_FORMAT = 1003
CODE_PROCESSING_ERROR = 1004


def make_result(
    code: int = CODE_OK,
    data: Any = None,
    msg: str = "ok",
) -> dict[str, Any]:
    """构造项目统一返回 JSON。"""
    return {"code": code, "data": data, "msg": msg}


def fail(
    code: int,
    msg: str,
    data: Any = None,
) -> dict[str, Any]:
    """构造失败返回。"""
    return {"code": code, "data": data, "msg": msg}


class ToolMeta(BaseModel):
    """工具元信息容器。

    工具名称、功能描述、参数 JSON Schema 全部放在这里，
    与业务函数解耦，后续 BE1/BE2 的 ToolRegistry 可直接消费。
    """

    name: str
    description: str
    parameters_schema: dict[str, Any]