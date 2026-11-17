"""BE3 Word 文档适配工具。

只读源 .docx；生成操作写入全新文件。不导入 ToolRegistry。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from docx import Document
from pydantic import BaseModel, Field

from backend.app.office.common import (
    CODE_FILE_NOT_FOUND,
    CODE_INVALID_ARGUMENT,
    CODE_PROCESSING_ERROR,
    CODE_UNSUPPORTED_FORMAT,
    ToolMeta,
    fail,
    make_result,
)


class WordExtractTextParams(BaseModel):
    """Word 文本与表格提取参数。"""

    docx_path: str = Field(..., description="staging 中 .docx 文件的路径字符串")


class WordGenerateFromTextParams(BaseModel):
    """从标题和正文段落生成新 Word 的参数。"""

    output_path: str = Field(..., description="新 .docx 输出路径，不能与源文件相同")
    title: str = Field(..., min_length=1, description="文档标题")
    paragraphs: list[str] = Field(
        default_factory=list,
        description="正文段落列表，按顺序写入",
    )


WORD_EXTRACT_TEXT_META = ToolMeta(
    name="word_extract_text",
    description="提取 Word 文档的段落文本和表格内容，返回结构化 JSON。",
    parameters_schema=WordExtractTextParams.model_json_schema(),
)

WORD_GENERATE_FROM_TEXT_META = ToolMeta(
    name="word_generate_from_text",
    description="根据标题和段落列表生成新的 .docx 文件，源文件不被修改。",
    parameters_schema=WordGenerateFromTextParams.model_json_schema(),
)


def word_extract_text(docx_path: str) -> dict[str, Any]:
    """提取 Word 段落和表格。"""
    path = Path(docx_path)
    if not path.exists():
        return fail(CODE_FILE_NOT_FOUND, f"Word 文件不存在: {docx_path}")
    if path.suffix.lower() != ".docx":
        return fail(CODE_UNSUPPORTED_FORMAT, f"不是 .docx 文件: {docx_path}")

    try:
        doc = Document(str(path))

        paragraphs = [
            {"index": i, "text": p.text}
            for i, p in enumerate(doc.paragraphs)
            if p.text.strip()
        ]

        tables: list[dict[str, Any]] = []
        for t_idx, table in enumerate(doc.tables):
            rows: list[list[str]] = []
            for row in table.rows:
                rows.append([cell.text for cell in row.cells])
            tables.append({"table_index": t_idx, "rows": rows})

        return make_result(
            data={
                "paragraphs": paragraphs,
                "tables": tables,
                "paragraph_count": len(paragraphs),
                "table_count": len(tables),
            }
        )
    except Exception as exc:  # noqa: BLE001
        return fail(CODE_PROCESSING_ERROR, f"Word 读取失败: {exc}")


def word_generate_from_text(
    output_path: str,
    title: str,
    paragraphs: list[str] | None = None,
) -> dict[str, Any]:
    """生成新的 Word 文件。"""
    dst = Path(output_path)
    if dst.suffix.lower() != ".docx":
        return fail(CODE_INVALID_ARGUMENT, "输出路径必须为 .docx")

    paragraphs = paragraphs or []

    try:
        doc = Document()
        doc.add_heading(title, level=1)
        for text in paragraphs:
            doc.add_paragraph(text)

        dst.parent.mkdir(parents=True, exist_ok=True)
        doc.save(str(dst))

        return make_result(
            data={
                "output_path": str(dst),
                "title": title,
                "paragraph_count": len(paragraphs),
                "size_bytes": dst.stat().st_size,
            }
        )
    except Exception as exc:  # noqa: BLE001
        return fail(CODE_PROCESSING_ERROR, f"Word 生成失败: {exc}")


# ---------------------------------------------------------------------------
# 【待BE1/BE2骨架完成后取消注释接入】
# ---------------------------------------------------------------------------
# from backend.app.core.tool_registry import ToolRegistry  # noqa: ERA001
#
# def register_word_tools(registry: ToolRegistry) -> None:  # noqa: ERA001
#     registry.register(
#         name=WORD_EXTRACT_TEXT_META.name,
#         description=WORD_EXTRACT_TEXT_META.description,
#         parameters_schema=WORD_EXTRACT_TEXT_META.parameters_schema,
#         func=word_extract_text,
#     )  # noqa: ERA001
#     registry.register(
#         name=WORD_GENERATE_FROM_TEXT_META.name,
#         description=WORD_GENERATE_FROM_TEXT_META.description,
#         parameters_schema=WORD_GENERATE_FROM_TEXT_META.parameters_schema,
#         func=word_generate_from_text,
#     )  # noqa: ERA001