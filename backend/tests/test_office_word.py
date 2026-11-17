"""BE3 Word 工具单元测试。全部使用 tmp_path 自建临时 docx。"""

from __future__ import annotations

from pathlib import Path

import pytest
from docx import Document

from backend.app.office.word_tools import word_extract_text, word_generate_from_text


@pytest.fixture()
def docx_path(tmp_path: Path) -> Path:
    p = tmp_path / "sample.docx"
    doc = Document()
    doc.add_heading("测试标题", level=1)
    doc.add_paragraph("第一段正文")
    doc.add_paragraph("第二段正文")
    doc.save(str(p))
    return p


def test_extract_text_success(docx_path: Path) -> None:
    result = word_extract_text(str(docx_path))
    assert result["code"] == 0
    texts = [p["text"] for p in result["data"]["paragraphs"]]
    assert "第一段正文" in texts


def test_extract_text_missing_file(tmp_path: Path) -> None:
    result = word_extract_text(str(tmp_path / "missing.docx"))
    assert result["code"] != 0


def test_extract_text_wrong_suffix(tmp_path: Path) -> None:
    p = tmp_path / "not.docx.txt"
    p.write_text("x", encoding="utf-8")
    result = word_extract_text(str(p))
    assert result["code"] != 0


def test_generate_creates_new_file(tmp_path: Path) -> None:
    out = tmp_path / "generated.docx"
    result = word_generate_from_text(
        str(out),
        title="新文档",
        paragraphs=["段落 A", "段落 B"],
    )
    assert result["code"] == 0
    assert out.exists()
    doc = Document(str(out))
    all_text = "\n".join(p.text for p in doc.paragraphs)
    assert "新文档" in all_text
    assert "段落 A" in all_text


def test_generate_rejects_non_docx(tmp_path: Path) -> None:
    out = tmp_path / "generated.txt"
    result = word_generate_from_text(str(out), title="x")
    assert result["code"] != 0