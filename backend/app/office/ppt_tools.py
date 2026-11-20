# pyright: reportGeneralTypeIssues=false, reportAttributeAccessIssue=false, reportOptionalMemberAccess=false, reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportUnknownArgumentType=false
"""BE3 PPT 文档适配工具。

读取源 .pptx；生成写入全新文件。不导入 ToolRegistry。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pptx import Presentation
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


class PptExtractTextParams(BaseModel):
    """PPT 文本提取参数。"""

    pptx_path: str = Field(..., description="staging 中 .pptx 文件的路径字符串")


class PptGenerateFromOutlineParams(BaseModel):
    """从大纲生成新 PPT 的参数。"""

    output_path: str = Field(..., description="新 .pptx 输出路径")
    title: str = Field(..., min_length=1, description="封面标题")
    slides: list[dict[str, Any]] = Field(
        default_factory=list,
        description=(
            "内容页列表；每页形如 "
            '{"title": "...", "bullets": ["...", "..."]}'
        ),
    )


PPT_EXTRACT_TEXT_META = ToolMeta(
    name="ppt_extract_text",
    description="提取 PPT 每页的文本和表格内容，返回结构化 JSON。",
    parameters_schema=PptExtractTextParams.model_json_schema(),
)

PPT_GENERATE_FROM_OUTLINE_META = ToolMeta(
    name="ppt_generate_from_outline",
    description="根据标题和内容页大纲生成新的 .pptx 文件。",
    parameters_schema=PptGenerateFromOutlineParams.model_json_schema(),
)


def ppt_extract_text(pptx_path: str) -> dict[str, Any]:
    """提取 PPT 文本和表格。"""
    path = Path(pptx_path)
    if not path.exists():
        return fail(CODE_FILE_NOT_FOUND, f"PPT 文件不存在: {pptx_path}")
    if path.suffix.lower() != ".pptx":
        return fail(CODE_UNSUPPORTED_FORMAT, f"不是 .pptx 文件: {pptx_path}")

    try:
        prs = Presentation(str(path))
        slides_data: list[dict[str, Any]] = []

        for s_idx, slide in enumerate(prs.slides):
            texts: list[str] = []
            tables: list[list[list[str]]] = []

            for shape in slide.shapes:
                if getattr(shape, "has_text_frame", False):
                    for para in shape.text_frame.paragraphs:
                        text = para.text.strip()
                        if text:
                            texts.append(text)
                if getattr(shape, "has_table", False):
                    table = shape.table
                    rows: list[list[str]] = []
                    for row in table.rows:
                        rows.append([cell.text.strip() for cell in row.cells])
                    tables.append(rows)

            slides_data.append(
                {
                    "slide_index": s_idx,
                    "texts": texts,
                    "tables": tables,
                }
            )

        return make_result(
            data={
                "slide_count": len(slides_data),
                "slides": slides_data,
            }
        )
    except Exception as exc:  # noqa: BLE001
        return fail(CODE_PROCESSING_ERROR, f"PPT 读取失败: {exc}")


def ppt_generate_from_outline(
    output_path: str,
    title: str,
    slides: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """从大纲生成新 PPT。"""
    dst = Path(output_path)
    if dst.suffix.lower() != ".pptx":
        return fail(CODE_INVALID_ARGUMENT, "输出路径必须为 .pptx")

    slides = slides or []

    try:
        prs = Presentation()

        # 封面：layout 0 通常是 Title Slide
        cover_layout = prs.slide_layouts[0]
        cover = prs.slides.add_slide(cover_layout)
        if cover.shapes.title:
            cover.shapes.title.text = title

        # 内容页：layout 1 通常是 Title and Content
        content_layout = prs.slide_layouts[1]
        for item in slides:
            s_title = str(item.get("title", ""))
            bullets = item.get("bullets", [])
            if not isinstance(bullets, list):
                bullets = [str(bullets)]

            slide = prs.slides.add_slide(content_layout)
            if slide.shapes.title:
                slide.shapes.title.text = s_title

            if len(slide.placeholders) > 1:
                body = slide.placeholders[1]
                if body.has_text_frame:
                    tf = body.text_frame
                    tf.clear()
                    first = True
                    for bullet in bullets:
                        p = tf.paragraphs[0] if first else tf.add_paragraph()
                        p.text = str(bullet)
                        p.level = 0
                        first = False

        dst.parent.mkdir(parents=True, exist_ok=True)
        prs.save(str(dst))

        return make_result(
            data={
                "output_path": str(dst),
                "title": title,
                "slide_count": 1 + len(slides),
                "size_bytes": dst.stat().st_size,
            }
        )
    except Exception as exc:  # noqa: BLE001
        return fail(CODE_PROCESSING_ERROR, f"PPT 生成失败: {exc}")


# ---------------------------------------------------------------------------
# 【待BE1/BE2骨架完成后取消注释接入】
# ---------------------------------------------------------------------------
# from backend.app.core.tool_registry import ToolRegistry  # noqa: ERA001
#
# def register_ppt_tools(registry: ToolRegistry) -> None:  # noqa: ERA001
#     registry.register(
#         name=PPT_EXTRACT_TEXT_META.name,
#         description=PPT_EXTRACT_TEXT_META.description,
#         parameters_schema=PPT_EXTRACT_TEXT_META.parameters_schema,
#         func=ppt_extract_text,
#     )  # noqa: ERA001
#     registry.register(
#         name=PPT_GENERATE_FROM_OUTLINE_META.name,
#         description=PPT_GENERATE_FROM_OUTLINE_META.description,
#         parameters_schema=PPT_GENERATE_FROM_OUTLINE_META.parameters_schema,
#         func=ppt_generate_from_outline,
#     )  # noqa: ERA001