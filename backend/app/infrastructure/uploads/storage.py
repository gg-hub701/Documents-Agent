from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import BinaryIO

from app.infrastructure.paths import ensure_within


class UploadTooLargeError(ValueError):
    pass


def stage_stream(
    source: BinaryIO,
    staging_dir: Path,
    stored_name: str,
    max_bytes: int,
) -> tuple[Path, str, int]:
    final_path = ensure_within(staging_dir, staging_dir / stored_name)
    temporary_path = final_path.with_suffix(final_path.suffix + ".part")
    digest = hashlib.sha256()
    size_bytes = 0
    try:
        with temporary_path.open("wb") as destination:
            while chunk := source.read(1024 * 1024):
                size_bytes += len(chunk)
                if size_bytes > max_bytes:
                    raise UploadTooLargeError("文件超过上传大小限制")
                digest.update(chunk)
                destination.write(chunk)
        os.replace(temporary_path, final_path)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        final_path.unlink(missing_ok=True)
        raise
    return final_path, digest.hexdigest(), size_bytes
