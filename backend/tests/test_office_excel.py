
"""BE3 Excel 工具单元测试。全部使用 tmp_path 自建临时 xlsx。"""

from __future__ import annotations

from pathlib import Path

import openpyxl
import pytest

from backend.app.office.excel_tools import excel_read_summary, excel_write_cell


@pytest.fixture()
def xlsx_path(tmp_path: Path) -> Path:
    p = tmp_path / "sample.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    assert ws is not None 
    ws.title = "Sheet1"
    ws["A1"] = "姓名"
    ws["B1"] = "分数"
    ws["A2"] = "张三"
    ws["B2"] = 90
    wb.save(str(p))
    wb.close()
    return p


def test_read_summary_success(xlsx_path: Path) -> None:
    result = excel_read_summary(str(xlsx_path))
    assert result["code"] == 0
    sheets = result["data"]["sheets"]
    assert sheets[0]["name"] == "Sheet1"
    assert sheets[0]["max_row"] >= 2


def test_read_summary_missing_file(tmp_path: Path) -> None:
    result = excel_read_summary(str(tmp_path / "nope.xlsx"))
    assert result["code"] != 0


def test_write_cell_keeps_source_unchanged(
    xlsx_path: Path, tmp_path: Path
) -> None:
    out = tmp_path / "modified.xlsx"
    result = excel_write_cell(
        str(xlsx_path),
        str(out),
        "Sheet1",
        "C3",
        "新增",
    )
    assert result["code"] == 0
    assert out.exists()

    src_wb = openpyxl.load_workbook(str(xlsx_path), read_only=True)
    assert src_wb["Sheet1"]["C3"].value is None
    src_wb.close()

    out_wb = openpyxl.load_workbook(str(out), read_only=True)
    assert out_wb["Sheet1"]["C3"].value == "新增"
    out_wb.close()


def test_write_cell_rejects_same_path(xlsx_path: Path) -> None:
    result = excel_write_cell(
        str(xlsx_path),
        str(xlsx_path),
        "Sheet1",
        "A1",
        "x",
    )
    assert result["code"] != 0


def test_write_cell_rejects_unknown_sheet(
    xlsx_path: Path, tmp_path: Path
) -> None:
    out = tmp_path / "modified.xlsx"
    result = excel_write_cell(
        str(xlsx_path),
        str(out),
        "NoSuchSheet",
        "A1",
        "x",
    )
    assert result["code"] != 0