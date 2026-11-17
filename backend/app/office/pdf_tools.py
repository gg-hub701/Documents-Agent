# pyright: reportMissingTypeStubs=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportGeneralTypeIssues=false, reportAttributeAccessIssue=false, reportOptionalMemberAccess=false
"""BE3 PDF 文档适配工具。

只读源 PDF，所有产出写入新路径；返回统一 JSON 契约。
不导入 ToolRegistry。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pypdfium2 as pdfium
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


# ---------------------------------------------------------------------------
# 参数模型（Pydantic，用于生成 JSON Schema）
# ---------------------------------------------------------------------------


class PdfTextExtractParams(BaseModel):
    """PDF 全文/分页文本提取参数。"""

    pdf_path: str = Field(..., description="staging 中 PDF 文件的路径字符串")
    page_indices: list[int] | None = Field(
        default=None,
        description="要提取的页索引列表（0-based）。不传则提取全部页。",
    )


class PdfRenderPageParams(BaseModel):
    """PDF 指定页渲染为 PNG 的参数。"""

    pdf_path: str = Field(..., description="staging 中 PDF 文件的路径字符串")
    page_index: int = Field(..., ge=0, description="要渲染的页索引，0-based")
    output_path: str = Field(
        ...,
        description="渲染图片输出路径（PNG）。必须与源文件不同。",
    )
    scale: float = Field(
        default=2.0,
        gt=0,
        le=10,
        description="渲染缩放倍数，2.0 约等于 144 DPI。",
    )


# ---------------------------------------------------------------------------
# 工具元信息（与业务逻辑解耦）
# ---------------------------------------------------------------------------

PDF_EXTRACT_TEXT_META = ToolMeta(
    name="pdf_extract_text",
    description="提取 PDF 文件的文本内容，可指定页范围；返回每页文本和全文。",
    parameters_schema=PdfTextExtractParams.model_json_schema(),
)

PDF_RENDER_PAGE_META = ToolMeta(
    name="pdf_render_page",
    description="将 PDF 的指定页渲染为 PNG 图片，写入新路径，源文件不变。",
    parameters_schema=PdfRenderPageParams.model_json_schema(),
)


# ---------------------------------------------------------------------------
# 业务函数
# ---------------------------------------------------------------------------


def pdf_extract_text(
    pdf_path: str,
    page_indices: list[int] | None = None,
) -> dict[str, Any]:
    """提取 PDF 文本。

    Args:
        pdf_path: staging PDF 路径字符串。
        page_indices: 可选，0-based 页索引列表；None 表示全部页。

    Returns:
        统一 JSON：data 包含 pages（每页文本）和 full_text。
    """
    path = Path(pdf_path)
    if not path.exists():
        return fail(CODE_FILE_NOT_FOUND, f"PDF 文件不存在: {pdf_path}")
    if path.suffix.lower() != ".pdf":
        return fail(CODE_UNSUPPORTED_FORMAT, f"不是 PDF 文件: {pdf_path}")

    doc: pdfium.PdfDocument | None = None
    try:
        doc = pdfium.PdfDocument(str(path))
        total = len(doc)

        if page_indices is not None:
            if any(i < 0 or i >= total for i in page_indices):
                return fail(
                    CODE_INVALID_ARGUMENT,
                    f"page_indices 越界；总页数={total}，"
                    f"收到={page_indices}",
                )
            indices = page_indices
        else:
            indices = list(range(total))

        pages: list[dict[str, Any]] = []
        for idx in indices:
            page = doc[idx]
            text_page = page.get_textpage()
            try:
                text = text_page.get_text_range()
            finally:
                text_page.close()
                page.close()
            pages.append({"page_index": idx, "text": text})

        full_text = "\n".join(p["text"] for p in pages)
        return make_result(
            data={
                "total_pages": total,
                "pages": pages,
                "full_text": full_text,
            }
        )
    except Exception as exc:  # noqa: BLE001
        return fail(CODE_PROCESSING_ERROR, f"PDF 文本提取失败: {exc}")
    finally:
        if doc is not None:
            doc.close()


def pdf_render_page(
    pdf_path: str,
    page_index: int,
    output_path: str,
    scale: float = 2.0,
) -> dict[str, Any]:
    """将 PDF 指定页渲染为 PNG。

    源文件只读；输出路径必须不同于源路径。
    """
    src = Path(pdf_path)
    dst = Path(output_path)

    if not src.exists():
        return fail(CODE_FILE_NOT_FOUND, f"PDF 文件不存在: {pdf_path}")
    if src.suffix.lower() != ".pdf":
        return fail(CODE_UNSUPPORTED_FORMAT, f"不是 PDF 文件: {pdf_path}")
    if src.resolve() == dst.resolve():
        return fail(CODE_INVALID_ARGUMENT, "输出路径不能与源文件相同")
    if dst.suffix.lower() != ".png":
        return fail(CODE_INVALID_ARGUMENT, "输出路径必须为 .png")

    doc: pdfium.PdfDocument | None = None
    try:
        doc = pdfium.PdfDocument(str(src))
        total = len(doc)
        if page_index < 0 or page_index >= total:
            return fail(
                CODE_INVALID_ARGUMENT,
                f"page_index 越界；总页数={total}，收到={page_index}",
            )

        page = doc[page_index]
        try:
            bitmap = page.render(scale=scale)  # type: ignore
            pil_image = bitmap.to_pil()
            dst.parent.mkdir(parents=True, exist_ok=True)
            pil_image.save(str(dst), "PNG")
        finally:
            page.close()

        return make_result(
            data={
                "output_path": str(dst),
                "page_index": page_index,
                "scale": scale,
                "size_bytes": dst.stat().st_size,
            }
        )
    except Exception as exc:  # noqa: BLE001
        return fail(CODE_PROCESSING_ERROR, f"PDF 渲染失败: {exc}")
    finally:
        if doc is not None:
            doc.close()


# ---------------------------------------------------------------------------
# 【待BE1/BE2骨架完成后取消注释接入】
# 模拟注册片段，当前不导入 ToolRegistry。
# ---------------------------------------------------------------------------
# from backend.app.core.tool_registry import ToolRegistry  # noqa: ERA001
#
# def register_pdf_tools(registry: ToolRegistry) -> None:  # noqa: ERA001
#     registry.register(
#         name=PDF_EXTRACT_TEXT_META.name,
#         description=PDF_EXTRACT_TEXT_META.description,
#         parameters_schema=PDF_EXTRACT_TEXT_META.parameters_schema,
#         func=pdf_extract_text,
#     )  # noqa: ERA001
#     registry.register(
#         name=PDF_RENDER_PAGE_META.name,
#         description=PDF_RENDER_PAGE_META.description,
#         parameters_schema=PDF_RENDER_PAGE_META.parameters_schema,
#         func=pdf_render_page,
#     )  # noqa: ERA001