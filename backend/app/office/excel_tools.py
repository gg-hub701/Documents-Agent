"""BE3 Excel 文档适配工具。

读取用只读模式；写入操作先复制源文件到新路径，再在新副本上修改，
保证原始 staging 文件不可变。不导入 ToolRegistry。
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

import openpyxl
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


class ExcelReadSummaryParams(BaseModel):
    """Excel 工作簿摘要读取参数。"""

    xlsx_path: str = Field(..., description="staging 中 .xlsx 文件的路径字符串")


class ExcelWriteCellParams(BaseModel):
    """向 Excel 新副本写入单元格的参数。"""

    xlsx_path: str = Field(..., description="源 .xlsx 路径字符串（只读）")
    output_path: str = Field(..., description="新 .xlsx 输出路径，不能与源文件相同")
    sheet_name: str = Field(..., min_length=1, description="工作表名称")
    cell: str = Field(..., description="单元格坐标，如 A1、B3")
    value: Any = Field(..., description="要写入的值")


EXCEL_READ_SUMMARY_META = ToolMeta(
    name="excel_read_summary",
    description="读取 Excel 工作簿的 sheet 名称、维度和各 sheet 前几行预览。",
    parameters_schema=ExcelReadSummaryParams.model_json_schema(),
)

EXCEL_WRITE_CELL_META = ToolMeta(
    name="excel_write_cell",
    description="复制源 .xlsx 到新路径，并在新副本的指定单元格写入值；源文件不变。",
    parameters_schema=ExcelWriteCellParams.model_json_schema(),
)


def excel_read_summary(
    xlsx_path: str,
    max_preview_rows: int = 5,
) -> dict[str, Any]:
    """只读读取工作簿摘要。"""
    path = Path(xlsx_path)
    if not path.exists():
        return fail(CODE_FILE_NOT_FOUND, f"Excel 文件不存在: {xlsx_path}")
    if path.suffix.lower() != ".xlsx":
        return fail(CODE_UNSUPPORTED_FORMAT, f"不是 .xlsx 文件: {xlsx_path}")

    wb: openpyxl.Workbook | None = None
    try:
        wb = openpyxl.load_workbook(
            str(path),
            read_only=True,
            data_only=True,
        )
        sheets_info: list[dict[str, Any]] = []
        for name in wb.sheetnames:
            ws = wb[name]
            preview: list[list[Any]] = []
            for row in ws.iter_rows(
                min_row=1,
                max_row=max_preview_rows,
                values_only=True,
            ):
                preview.append(list(row))
            sheets_info.append(
                {
                    "name": name,
                    "max_row": ws.max_row,
                    "max_column": ws.max_column,
                    "preview": preview,
                }
            )
        return make_result(data={"sheets": sheets_info})
    except Exception as exc:  # noqa: BLE001
        return fail(CODE_PROCESSING_ERROR, f"Excel 读取失败: {exc}")
    finally:
        if wb is not None:
            wb.close()


def excel_write_cell(
    xlsx_path: str,
    output_path: str,
    sheet_name: str,
    cell: str,
    value: Any,
) -> dict[str, Any]:
    """复制源文件后在新副本写入单元格。"""
    src = Path(xlsx_path)
    dst = Path(output_path)

    if not src.exists():
        return fail(CODE_FILE_NOT_FOUND, f"源 Excel 不存在: {xlsx_path}")
    if src.suffix.lower() != ".xlsx":
        return fail(CODE_UNSUPPORTED_FORMAT, f"源不是 .xlsx: {xlsx_path}")
    if dst.suffix.lower() != ".xlsx":
        return fail(CODE_INVALID_ARGUMENT, "输出路径必须为 .xlsx")
    if src.resolve() == dst.resolve():
        return fail(CODE_INVALID_ARGUMENT, "输出路径不能与源文件相同")

    wb: openpyxl.Workbook | None = None
    try:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)

        wb = openpyxl.load_workbook(str(dst))
        if sheet_name not in wb.sheetnames:
            return fail(
                CODE_INVALID_ARGUMENT,
                f"sheet 不存在: {sheet_name}；可用: {wb.sheetnames}",
            )

        ws = wb[sheet_name]
        ws[cell] = value
        wb.save(str(dst))

        return make_result(
            data={
                "output_path": str(dst),
                "sheet_name": sheet_name,
                "cell": cell,
                "size_bytes": dst.stat().st_size,
            }
        )
    except Exception as exc:  # noqa: BLE001
        return fail(CODE_PROCESSING_ERROR, f"Excel 写入失败: {exc}")
    finally:
        if wb is not None:
            wb.close()


# ---------------------------------------------------------------------------
# 【待BE1/BE2骨架完成后取消注释接入】
# ---------------------------------------------------------------------------
# from backend.app.core.tool_registry import ToolRegistry  # noqa: ERA001
#
# def register_excel_tools(registry: ToolRegistry) -> None:  # noqa: ERA001
#     registry.register(
#         name=EXCEL_READ_SUMMARY_META.name,
#         description=EXCEL_READ_SUMMARY_META.description,
#         parameters_schema=EXCEL_READ_SUMMARY_META.parameters_schema,
#         func=excel_read_summary,
#     )  # noqa: ERA001
#     registry.register(
#         name=EXCEL_WRITE_CELL_META.name,
#         description=EXCEL_WRITE_CELL_META.description,
#         parameters_schema=EXCEL_WRITE_CELL_META.parameters_schema,
#         func=excel_write_cell,
#     )  # noqa: ERA001