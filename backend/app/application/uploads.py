from __future__ import annotations

import codecs
import csv
import io
import struct
import zipfile
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import BinaryIO
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from app.api.schemas.uploads import (
    CsvPreflight,
    ImagePreflight,
    SupportedFormat,
    TextEncodingPreflight,
    UploadPreflight,
    UploadRecord,
    UploadStatus,
)
from app.infrastructure.db.models.upload import Upload
from app.infrastructure.db.time import as_utc
from app.infrastructure.paths import ensure_within, resolve_relative_path
from app.infrastructure.uploads.storage import UploadTooLargeError, stage_stream
from app.settings import AppSettings


class UploadNotFoundError(LookupError):
    pass


class UploadConsumedError(ValueError):
    pass


class UploadRejectedError(ValueError):
    pass


class MacroUploadRejectedError(UploadRejectedError):
    pass


class MalformedUploadError(UploadRejectedError):
    pass


class TextFileTooLargeError(UploadRejectedError):
    pass


class FileTooLargeError(UploadRejectedError):
    pass


class ImageDimensionLimitError(UploadRejectedError):
    pass


class ImagePixelLimitError(UploadRejectedError):
    pass


class ImageDecodeError(UploadRejectedError):
    pass


class InvalidTextEncodingError(UploadRejectedError):
    pass


class RowLimitError(UploadRejectedError):
    pass


@dataclass(frozen=True, slots=True)
class IncomingUpload:
    original_name: str
    content_type: str | None
    stream: BinaryIO


_FORMAT_BY_SUFFIX = {
    ".docx": SupportedFormat.DOCX,
    ".xlsx": SupportedFormat.XLSX,
    ".pptx": SupportedFormat.PPTX,
    ".pdf": SupportedFormat.PDF,
    ".csv": SupportedFormat.CSV,
    ".md": SupportedFormat.MD,
    ".txt": SupportedFormat.TXT,
    ".png": SupportedFormat.PNG,
    ".jpg": SupportedFormat.JPEG,
    ".jpeg": SupportedFormat.JPEG,
    ".webp": SupportedFormat.WEBP,
}

_MACRO_SUFFIXES = {".docm", ".xlsm", ".pptm"}

_MIME_TYPES = {
    SupportedFormat.DOCX: {
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    },
    SupportedFormat.XLSX: {
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    },
    SupportedFormat.PPTX: {
        "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    },
    SupportedFormat.PDF: {"application/pdf"},
    SupportedFormat.CSV: {"text/csv", "application/csv", "text/plain"},
    SupportedFormat.MD: {"text/markdown", "text/x-markdown", "text/plain"},
    SupportedFormat.TXT: {"text/plain"},
    SupportedFormat.PNG: {"image/png"},
    SupportedFormat.JPEG: {"image/jpeg"},
    SupportedFormat.WEBP: {"image/webp"},
}


def _format_from_name(original_name: str) -> SupportedFormat:
    suffix = Path(original_name).suffix.lower()
    if suffix in _MACRO_SUFFIXES:
        raise MacroUploadRejectedError("不支持包含宏的 Office 文件")
    try:
        return _FORMAT_BY_SUFFIX[suffix]
    except KeyError as exc:
        raise UploadRejectedError("不支持的文件类型") from exc


def _validate_content_type(
    file_format: SupportedFormat,
    content_type: str | None,
) -> None:
    if content_type is None or content_type in {"", "application/octet-stream"}:
        return
    normalized = content_type.split(";", 1)[0].strip().lower()
    if normalized not in _MIME_TYPES[file_format]:
        raise MalformedUploadError("文件扩展名与 MIME 类型不一致")


def _decode_text(content: bytes) -> tuple[str, TextEncodingPreflight]:
    bom_encodings = (
        (codecs.BOM_UTF8, "utf-8-sig"),
        (codecs.BOM_UTF16_LE, "utf-16-le"),
        (codecs.BOM_UTF16_BE, "utf-16-be"),
    )
    for bom, encoding_name in bom_encodings:
        if content.startswith(bom):
            try:
                decoded = content.decode(encoding_name)
            except UnicodeDecodeError as exc:
                raise InvalidTextEncodingError("文本 BOM 与内容编码不一致") from exc
            return decoded, TextEncodingPreflight(
                value=encoding_name,
                confidence=1.0,
                source="bom",
                requires_confirmation=False,
            )
    try:
        decoded = content.decode("utf-8")
        encoding = TextEncodingPreflight(
            value="utf-8",
            confidence=1.0,
            source="strict_decode",
            requires_confirmation=False,
        )
    except UnicodeDecodeError:
        try:
            decoded = content.decode("gb18030")
        except UnicodeDecodeError as exc:
            raise InvalidTextEncodingError("文本编码无法识别") from exc
        encoding = TextEncodingPreflight(
            value="gb18030",
            confidence=0.8,
            source="strict_decode",
            requires_confirmation=True,
        )
    return decoded, encoding


def _preflight_text(path: Path) -> UploadPreflight:
    _, encoding = _decode_text(path.read_bytes())
    return UploadPreflight(text_encoding=encoding)


def _preflight_csv(path: Path) -> UploadPreflight:
    decoded, encoding = _decode_text(path.read_bytes())
    sample = decoded[:16_384]
    try:
        dialect = csv.Sniffer().sniff(sample)
    except csv.Error:
        dialect = csv.excel
    rows = list(csv.reader(io.StringIO(decoded), dialect))
    data_row_count = max(0, len(rows) - 1)
    if data_row_count > 100_000:
        raise RowLimitError("CSV 超过 100,000 行限制")
    return UploadPreflight(
        row_count=data_row_count,
        text_encoding=encoding,
        csv=CsvPreflight(
            delimiter=dialect.delimiter,
            quotechar=dialect.quotechar or '"',
            has_header=True,
        ),
    )


def _png_dimensions(content: bytes) -> tuple[int, int, bool, str]:
    if len(content) < 29 or content[12:16] != b"IHDR":
        raise ImageDecodeError("PNG 缺少有效 IHDR")
    width, height, bit_depth, color_type = struct.unpack(">IIBB", content[16:26])
    has_alpha = color_type in {4, 6} or b"tRNS" in content
    color_mode = "RGBA" if color_type == 6 else "RGB"
    if color_type == 4:
        color_mode = "LA"
    elif color_type == 3:
        color_mode = "P"
    elif bit_depth == 1:
        color_mode = "1"
    return width, height, has_alpha, color_mode


def _jpeg_dimensions(content: bytes) -> tuple[int, int, bool, str]:
    if not content.startswith(b"\xff\xd8\xff"):
        raise ImageDecodeError("JPEG 文件头无效")
    offset = 2
    sof_markers = {
        0xC0,
        0xC1,
        0xC2,
        0xC3,
        0xC5,
        0xC6,
        0xC7,
        0xC9,
        0xCA,
        0xCB,
        0xCD,
        0xCE,
        0xCF,
    }
    while offset + 4 <= len(content):
        if content[offset] != 0xFF:
            offset += 1
            continue
        while offset < len(content) and content[offset] == 0xFF:
            offset += 1
        if offset >= len(content):
            break
        marker = content[offset]
        offset += 1
        if marker in {0xD8, 0xD9}:
            continue
        if offset + 2 > len(content):
            break
        segment_length = int.from_bytes(content[offset : offset + 2], "big")
        if segment_length < 2 or offset + segment_length > len(content):
            break
        if marker in sof_markers and segment_length >= 7:
            height = int.from_bytes(content[offset + 3 : offset + 5], "big")
            width = int.from_bytes(content[offset + 5 : offset + 7], "big")
            components = content[offset + 7] if segment_length >= 8 else 3
            return width, height, False, "RGB" if components >= 3 else "L"
        offset += segment_length
    raise ImageDecodeError("JPEG 缺少有效尺寸信息")


def _webp_dimensions(content: bytes) -> tuple[int, int, bool, str]:
    if not (content.startswith(b"RIFF") and content[8:12] == b"WEBP"):
        raise ImageDecodeError("WebP 文件头无效")
    offset = 12
    while offset + 8 <= len(content):
        fourcc = content[offset : offset + 4]
        chunk_size = int.from_bytes(content[offset + 4 : offset + 8], "little")
        payload_start = offset + 8
        payload_end = payload_start + chunk_size
        if payload_end > len(content):
            break
        payload = content[payload_start:payload_end]
        if fourcc == b"VP8X" and len(payload) >= 10:
            flags = payload[0]
            width = int.from_bytes(payload[4:7], "little") + 1
            height = int.from_bytes(payload[7:10], "little") + 1
            return width, height, bool(flags & 0x10), "RGBA"
        offset = payload_end + (chunk_size % 2)
    raise ImageDecodeError("WebP 缺少有效画布尺寸")


def _image_preflight(path: Path, file_format: SupportedFormat) -> UploadPreflight:
    content = path.read_bytes()
    if file_format is SupportedFormat.PNG:
        width, height, has_alpha, color_mode = _png_dimensions(content)
    elif file_format is SupportedFormat.JPEG:
        width, height, has_alpha, color_mode = _jpeg_dimensions(content)
    elif file_format is SupportedFormat.WEBP:
        width, height, has_alpha, color_mode = _webp_dimensions(content)
    else:
        raise ImageDecodeError("不支持的图片格式")
    if width > 20_000 or height > 20_000:
        raise ImageDimensionLimitError("图片边长超过 20,000 像素限制")
    if width * height > 40_000_000:
        raise ImagePixelLimitError("图片超过 4,000 万像素限制")
    return UploadPreflight(
        image=ImagePreflight(
            format=file_format,
            logical_width=width,
            logical_height=height,
            source_width=width,
            source_height=height,
            orientation=1,
            color_mode=color_mode,
            has_alpha=has_alpha,
        )
    )


def _validate_ooxml(path: Path) -> None:
    if not zipfile.is_zipfile(path):
        raise MalformedUploadError("Office 文件不是有效的 OOXML 压缩包")
    try:
        with zipfile.ZipFile(path) as archive:
            names = set(archive.namelist())
            if "[Content_Types].xml" not in names:
                raise MalformedUploadError("Office 文件缺少内容类型清单")
            if any(name.lower().endswith("vbaproject.bin") for name in names):
                raise MacroUploadRejectedError("Office 文件包含 VBA 宏")
    except zipfile.BadZipFile as exc:
        raise MalformedUploadError("Office 文件压缩结构损坏") from exc


def _validate_shallow_content(path: Path, file_format: SupportedFormat) -> None:
    if file_format in {
        SupportedFormat.DOCX,
        SupportedFormat.XLSX,
        SupportedFormat.PPTX,
    }:
        _validate_ooxml(path)
        return
    content = path.read_bytes()
    if file_format is SupportedFormat.PDF and not content.startswith(b"%PDF-"):
        raise MalformedUploadError("PDF 文件头无效")
    if file_format is SupportedFormat.PNG and not content.startswith(
        b"\x89PNG\r\n\x1a\n"
    ):
        raise MalformedUploadError("PNG 文件头无效")
    if file_format is SupportedFormat.JPEG and not content.startswith(b"\xff\xd8\xff"):
        raise MalformedUploadError("JPEG 文件头无效")
    if file_format is SupportedFormat.WEBP and not (
        content.startswith(b"RIFF") and content[8:12] == b"WEBP"
    ):
        raise MalformedUploadError("WebP 文件头无效")
    if file_format in {SupportedFormat.CSV, SupportedFormat.MD, SupportedFormat.TXT}:
        binary_prefixes = (
            b"PK\x03\x04",
            b"%PDF-",
            b"\x89PNG\r\n\x1a\n",
            b"\xff\xd8\xff",
            b"\xd0\xcf\x11\xe0",
        )
        if content.startswith(binary_prefixes):
            raise MalformedUploadError("文本文件包含二进制内容")


class UploadService:
    def __init__(self, session: Session, settings: AppSettings) -> None:
        self._session = session
        self._settings = settings

    def create(self, incoming: IncomingUpload) -> UploadRecord:
        file_format = _format_from_name(incoming.original_name)
        _validate_content_type(file_format, incoming.content_type)
        max_bytes = 2 * 1024 * 1024 if file_format in {
            SupportedFormat.TXT,
            SupportedFormat.MD,
        } else 50 * 1024 * 1024
        upload_id = uuid4()
        stored_name = f"{upload_id}.bin"
        try:
            staged_path, sha256, size_bytes = stage_stream(
                incoming.stream,
                self._settings.data_dir / "staging",
                stored_name,
                max_bytes,
            )
        except UploadTooLargeError as exc:
            if file_format in {SupportedFormat.TXT, SupportedFormat.MD}:
                raise TextFileTooLargeError("文本文件超过 2 MB 限制") from exc
            raise FileTooLargeError("文件超过 50 MB 限制") from exc
        try:
            _validate_shallow_content(staged_path, file_format)
            preflight = (
                _preflight_text(staged_path)
                if file_format in {SupportedFormat.TXT, SupportedFormat.MD}
                else _preflight_csv(staged_path)
                if file_format is SupportedFormat.CSV
                else _image_preflight(staged_path, file_format)
                if file_format
                in {SupportedFormat.PNG, SupportedFormat.JPEG, SupportedFormat.WEBP}
                else UploadPreflight(
                    template_candidate=file_format
                    in {
                        SupportedFormat.DOCX,
                        SupportedFormat.XLSX,
                        SupportedFormat.PPTX,
                    }
                )
            )
        except Exception:
            staged_path.unlink(missing_ok=True)
            raise
        now = datetime.now(UTC)
        record = Upload(
            id=str(upload_id),
            original_name=incoming.original_name,
            stored_name=stored_name,
            sha256=sha256,
            format=file_format.value,
            size_bytes=size_bytes,
            status=UploadStatus.VALIDATED.value,
            preflight_json=preflight.model_dump(mode="json"),
            expires_at=now
            + timedelta(hours=self._settings.upload_staging_ttl_hours),
            created_at=now,
        )
        self._session.add(record)
        self._session.commit()
        return UploadRecord(
            upload_id=upload_id,
            original_name=record.original_name,
            format=file_format,
            size_bytes=size_bytes,
            sha256=sha256,
            status=UploadStatus.VALIDATED,
            preflight=preflight,
            expires_at=as_utc(record.expires_at),
        )

    def get(self, upload_id: UUID) -> UploadRecord:
        record = self._session.get(Upload, str(upload_id))
        if record is None:
            raise UploadNotFoundError(str(upload_id))
        expires_at = as_utc(record.expires_at)
        if (
            record.status != UploadStatus.CONSUMED.value
            and expires_at is not None
            and expires_at <= datetime.now(UTC)
        ):
            record.status = UploadStatus.EXPIRED.value
            stored_path = resolve_relative_path(
                self._settings.data_dir / "staging",
                record.stored_name,
            )
            stored_path.unlink(missing_ok=True)
            self._session.commit()
        preflight = UploadPreflight.model_validate(record.preflight_json)
        return UploadRecord(
            upload_id=UUID(record.id),
            original_name=record.original_name,
            format=SupportedFormat(record.format),
            size_bytes=record.size_bytes,
            sha256=record.sha256,
            status=UploadStatus(record.status),
            preflight=preflight,
            expires_at=as_utc(record.expires_at),
        )

    def delete(self, upload_id: UUID) -> None:
        record = self._session.get(Upload, str(upload_id))
        if record is None:
            raise UploadNotFoundError(str(upload_id))
        if record.status == UploadStatus.CONSUMED.value:
            raise UploadConsumedError(str(upload_id))
        stored_path = ensure_within(
            self._settings.data_dir / "staging",
            self._settings.data_dir / "staging" / record.stored_name,
        )
        stored_path.unlink(missing_ok=True)
        self._session.delete(record)
        self._session.commit()
