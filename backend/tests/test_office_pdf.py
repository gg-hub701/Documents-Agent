# pyright: reportMissingTypeStubs=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""BE3 PDF 工具单元测试。全部使用 tmp_path 自建临时 PDF。"""

from __future__ import annotations

from pathlib import Path

import pypdfium2 as pdfium
import pytest

from backend.app.office.pdf_tools import pdf_extract_text, pdf_render_page


def _make_minimal_pdf(path: Path) -> None:
    """用 pypdfium2 新建一页空白 PDF 并保存。"""
    doc = pdfium.PdfDocument.new()
    try:
        doc.new_page(width=200, height=200)
        doc.save(str(path))
    finally:
        doc.close()


@pytest.fixture()
def pdf_path(tmp_path: Path) -> Path:
    p = tmp_path / "sample.pdf"
    _make_minimal_pdf(p)
    return p


def test_extract_text_returns_unified_contract(pdf_path: Path) -> None:
    result = pdf_extract_text(str(pdf_path))
    assert result["code"] == 0
    assert "pages" in result["data"]
    assert "full_text" in result["data"]
    assert isinstance(result["data"]["total_pages"], int)


def test_extract_text_missing_file(tmp_path: Path) -> None:
    result = pdf_extract_text(str(tmp_path / "nope.pdf"))
    assert result["code"] != 0
    assert "不存在" in result["msg"]


def test_extract_text_non_pdf(tmp_path: Path) -> None:
    p = tmp_path / "not.pdf.txt"
    p.write_text("x", encoding="utf-8")
    result = pdf_extract_text(str(p))
    assert result["code"] != 0


def test_extract_text_page_out_of_range(pdf_path: Path) -> None:
    result = pdf_extract_text(str(pdf_path), page_indices=[99])
    assert result["code"] != 0
    assert "越界" in result["msg"]


def test_render_page_writes_new_png(pdf_path: Path, tmp_path: Path) -> None:
    out = tmp_path / "page.png"
    result = pdf_render_page(str(pdf_path), 0, str(out))
    assert result["code"] == 0
    assert out.exists()
    assert out.suffix == ".png"
    assert result["data"]["output_path"] == str(out)


def test_render_page_rejects_same_output(pdf_path: Path) -> None:
    result = pdf_render_page(str(pdf_path), 0, str(pdf_path))
    assert result["code"] != 0
    assert "不能与源文件相同" in result["msg"]


def test_render_page_rejects_non_png_output(pdf_path: Path, tmp_path: Path) -> None:
    out = tmp_path / "page.jpg"
    result = pdf_render_page(str(pdf_path), 0, str(out))
    assert result["code"] != 0