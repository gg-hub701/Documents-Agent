# pyright: basic

import io
from pathlib import Path

import pytest
from app.infrastructure.uploads.storage import UploadTooLargeError, stage_stream


def test_stage_stream_removes_partial_files_when_limit_is_exceeded(
    tmp_path: Path,
) -> None:
    with pytest.raises(UploadTooLargeError):
        stage_stream(
            io.BytesIO(b"12345"),
            tmp_path,
            "upload.bin",
            max_bytes=4,
        )

    assert not list(tmp_path.glob("*"))
