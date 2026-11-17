"""BE3 PPT 工具单元测试。全部使用 tmp_path 自建临时 pptx。"""

from __future__ import annotations

from pathlib import Path

import pytest
from pptx import Presentation

from backend.app.office.ppt_tools import ppt_extract_text, ppt_generate_from_outline


@pytest.fixture()
def pptx_path(tmp_path: Path) -> Path:
    p = tmp_path / "sample.pptx"
    prs = Presentation()
    cover = prs.slides.add_slide(prs.slide_layouts[0])
    cover.shapes.title.text = "封面标题"  # type: ignore
    
    content = prs.slides.add_slide(prs.slide_layouts[1])
    content.shapes.title.text = "内容页"  # type: ignore
    
    content.placeholders[1].text = "要点一"  # type: ignore
    prs.save(str(p))
    return p


def test_extract_text_success(pptx_path: Path) -> None:
    result = ppt_extract_text(str(pptx_path))
    assert result["code"] == 0
    assert result["data"]["slide_count"] == 2
    all_texts = [
        t
        for slide in result["data"]["slides"]
        for t in slide["texts"]
    ]
    assert "封面标题" in all_texts
    assert "要点一" in all_texts


def test_extract_text_missing_file(tmp_path: Path) -> None:
    result = ppt_extract_text(str(tmp_path / "nope.pptx"))
    assert result["code"] != 0


def test_generate_from_outline_creates_file(tmp_path: Path) -> None:
    out = tmp_path / "generated.pptx"
    result = ppt_generate_from_outline(
        str(out),
        title="自动生成封面",
        slides=[
            {"title": "第一页", "bullets": ["A", "B"]},
            {"title": "第二页", "bullets": ["C"]},
        ],
    )
    assert result["code"] == 0
    assert out.exists()
    prs = Presentation(str(out))
    assert len(prs.slides) == 3


def test_generate_rejects_non_pptx(tmp_path: Path) -> None:
    out = tmp_path / "generated.txt"
    result = ppt_generate_from_outline(str(out), title="x")
    assert result["code"] != 0