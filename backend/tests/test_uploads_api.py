# pyright: basic

import codecs
import hashlib
import io
import sqlite3
import struct
import zipfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

from alembic import command
from alembic.config import Config
from app.api.main import create_app
from app.api.schemas.common import OfficeHealth
from app.settings import AppSettings
from fastapi.testclient import TestClient


def upload_test_app(tmp_path: Path):
    settings = AppSettings.from_env(
        env={
            "DOC_AGENT_DATA_DIR": str(tmp_path),
            "UPLOAD_STAGING_TTL_HOURS": "24",
        },
        cwd=tmp_path,
    )
    config = Config("alembic.ini")
    config.set_main_option("script_location", "backend/migrations")
    config.set_main_option(
        "sqlalchemy.url",
        f"sqlite+pysqlite:///{settings.database_path.as_posix()}",
    )
    command.upgrade(config, "head")
    return create_app(
        settings=settings,
        office_probe=lambda: OfficeHealth(status="unavailable", detail=None),
    )


def docx_bytes() -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>',
        )
    return buffer.getvalue()


def png_header(width: int, height: int, color_type: int = 6) -> bytes:
    ihdr = struct.pack(">IIBBBBB", width, height, 8, color_type, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + struct.pack(">I", 13)
        + b"IHDR"
        + ihdr
        + b"\x00\x00\x00\x00"
    )


def jpeg_header(width: int, height: int) -> bytes:
    sof = (
        b"\xff\xc0"
        + struct.pack(">H", 17)
        + b"\x08"
        + struct.pack(">HH", height, width)
        + b"\x03\x01\x11\x00\x02\x11\x01\x03\x11\x01"
    )
    return b"\xff\xd8" + sof + b"\xff\xd9"


def webp_header(width: int, height: int, has_alpha: bool = True) -> bytes:
    flags = b"\x10" if has_alpha else b"\x00"
    payload = (
        flags
        + b"\x00\x00\x00"
        + (width - 1).to_bytes(3, "little")
        + (height - 1).to_bytes(3, "little")
    )
    chunk = b"VP8X" + struct.pack("<I", len(payload)) + payload
    return b"RIFF" + struct.pack("<I", len(chunk) + 4) + b"WEBP" + chunk


def test_upload_text_returns_validated_record(tmp_path: Path) -> None:
    content = "第一行\n第二行\n".encode()
    expected_sha256 = hashlib.sha256(content).hexdigest()

    with TestClient(upload_test_app(tmp_path)) as client:
        response = client.post(
            "/api/v1/uploads",
            files={"file": ("notes.txt", content, "text/plain")},
        )

    assert response.status_code == 201
    payload = response.json()
    assert payload["original_name"] == "notes.txt"
    assert payload["format"] == "txt"
    assert payload["size_bytes"] == len(content)
    assert payload["sha256"] == expected_sha256
    assert payload["status"] == "validated"
    assert payload["preflight"]["text_encoding"]["value"] == "utf-8"
    assert payload["preflight"]["text_encoding"]["requires_confirmation"] is False
    assert payload["expires_at"] is not None

    staging_file = next((tmp_path / "staging").glob("*.bin"))
    assert staging_file.read_bytes() == content

    upload_id = payload["upload_id"]
    with TestClient(upload_test_app(tmp_path)) as client:
        get_response = client.get(f"/api/v1/uploads/{upload_id}")

    assert get_response.status_code == 200
    assert get_response.json()["sha256"] == expected_sha256


def test_unsupported_extension_is_rejected(tmp_path: Path) -> None:
    with TestClient(upload_test_app(tmp_path)) as client:
        response = client.post(
            "/api/v1/uploads",
            files={"file": ("payload.exe", b"MZ", "application/octet-stream")},
        )

    assert response.status_code == 400
    assert response.json()["code"] == "UNSUPPORTED_FILE_TYPE"
    assert not list((tmp_path / "staging").glob("*"))


def test_macro_extension_is_rejected(tmp_path: Path) -> None:
    with TestClient(upload_test_app(tmp_path)) as client:
        response = client.post(
            "/api/v1/uploads",
            files={
                "file": (
                    "report.docm",
                    b"PK\x03\x04macro",
                    "application/vnd.ms-word.document.macroEnabled.12",
                )
            },
        )

    assert response.status_code == 400
    assert response.json()["code"] == "MACRO_FILE_REJECTED"


def test_docx_extension_with_non_zip_content_is_rejected(tmp_path: Path) -> None:
    with TestClient(upload_test_app(tmp_path)) as client:
        response = client.post(
            "/api/v1/uploads",
            files={
                "file": (
                    "report.docx",
                    b"not-a-zip",
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )
            },
        )

    assert response.status_code == 400
    assert response.json()["code"] == "MALFORMED_FILE"
    assert not list((tmp_path / "staging").glob("*"))


def test_oversized_text_file_is_rejected(tmp_path: Path) -> None:
    oversized = b"a" * (2 * 1024 * 1024 + 1)

    with TestClient(upload_test_app(tmp_path)) as client:
        response = client.post(
            "/api/v1/uploads",
            files={"file": ("large.txt", oversized, "text/plain")},
        )

    assert response.status_code == 400
    assert response.json()["code"] == "TEXT_FILE_TOO_LARGE"
    assert not list((tmp_path / "staging").glob("*"))


def test_delete_removes_unconsumed_upload_and_file(tmp_path: Path) -> None:
    with TestClient(upload_test_app(tmp_path)) as client:
        upload = client.post(
            "/api/v1/uploads",
            files={"file": ("notes.txt", b"hello", "text/plain")},
        ).json()
        response = client.delete(f"/api/v1/uploads/{upload['upload_id']}")

    assert response.status_code == 204
    assert not list((tmp_path / "staging").glob("*"))
    with TestClient(upload_test_app(tmp_path)) as client:
        missing = client.get(f"/api/v1/uploads/{upload['upload_id']}")
    assert missing.status_code == 404
    assert missing.json()["code"] == "UPLOAD_NOT_FOUND"


def test_expired_upload_is_marked_and_removed(tmp_path: Path) -> None:
    app = upload_test_app(tmp_path)
    with TestClient(app) as client:
        upload = client.post(
            "/api/v1/uploads",
            files={"file": ("notes.txt", b"hello", "text/plain")},
        ).json()

    expired_at = datetime.now(UTC) - timedelta(minutes=1)
    with sqlite3.connect(tmp_path / "app.db") as connection:
        connection.execute(
            "UPDATE uploads SET expires_at = ? WHERE id = ?",
            (expired_at.replace(tzinfo=None).isoformat(" "), upload["upload_id"]),
        )
        connection.commit()

    with TestClient(upload_test_app(tmp_path)) as client:
        response = client.get(f"/api/v1/uploads/{upload['upload_id']}")

    assert response.status_code == 200
    assert response.json()["status"] == "expired"
    assert not list((tmp_path / "staging").glob("*"))


def test_consumed_upload_cannot_be_deleted(tmp_path: Path) -> None:
    app = upload_test_app(tmp_path)
    with TestClient(app) as client:
        upload = client.post(
            "/api/v1/uploads",
            files={"file": ("notes.txt", b"hello", "text/plain")},
        ).json()

    with sqlite3.connect(tmp_path / "app.db") as connection:
        connection.execute(
            "UPDATE uploads SET status = 'consumed' WHERE id = ?",
            (upload["upload_id"],),
        )
        connection.commit()

    with TestClient(upload_test_app(tmp_path)) as client:
        response = client.delete(f"/api/v1/uploads/{upload['upload_id']}")

    assert response.status_code == 409
    assert response.json()["code"] == "UPLOAD_ALREADY_CONSUMED"


def test_valid_docx_is_marked_as_template_candidate(tmp_path: Path) -> None:
    with TestClient(upload_test_app(tmp_path)) as client:
        response = client.post(
            "/api/v1/uploads",
            files={
                "file": (
                    "template.docx",
                    docx_bytes(),
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )
            },
        )

    assert response.status_code == 201
    assert response.json()["preflight"]["template_candidate"] is True


def test_csv_preflight_counts_data_rows(tmp_path: Path) -> None:
    csv_content = b'name,note\r\nAlice,"line 1\nline 2"\r\nBob,ok\r\n'

    with TestClient(upload_test_app(tmp_path)) as client:
        response = client.post(
            "/api/v1/uploads",
            files={"file": ("contacts.csv", csv_content, "text/csv")},
        )

    assert response.status_code == 201
    preflight = response.json()["preflight"]
    assert preflight["row_count"] == 2
    assert preflight["csv"]["delimiter"] == ","
    assert preflight["text_encoding"]["value"] == "utf-8"


def test_png_preflight_reads_dimensions_and_alpha(tmp_path: Path) -> None:
    with TestClient(upload_test_app(tmp_path)) as client:
        response = client.post(
            "/api/v1/uploads",
            files={"file": ("image.png", png_header(120, 80), "image/png")},
        )

    assert response.status_code == 201
    image = response.json()["preflight"]["image"]
    assert image["logical_width"] == 120
    assert image["logical_height"] == 80
    assert image["source_width"] == 120
    assert image["source_height"] == 80
    assert image["has_alpha"] is True


def test_png_dimensions_over_limit_are_rejected(tmp_path: Path) -> None:
    with TestClient(upload_test_app(tmp_path)) as client:
        response = client.post(
            "/api/v1/uploads",
            files={
                "file": (
                    "wide.png",
                    png_header(20_001, 1),
                    "image/png",
                )
            },
        )

    assert response.status_code == 400
    assert response.json()["code"] == "IMAGE_DIMENSION_LIMIT_EXCEEDED"


def test_mime_type_mismatch_is_rejected(tmp_path: Path) -> None:
    with TestClient(upload_test_app(tmp_path)) as client:
        response = client.post(
            "/api/v1/uploads",
            files={"file": ("notes.txt", b"hello", "image/png")},
        )

    assert response.status_code == 400
    assert response.json()["code"] == "MALFORMED_FILE"


def test_jpeg_preflight_reads_dimensions(tmp_path: Path) -> None:
    with TestClient(upload_test_app(tmp_path)) as client:
        response = client.post(
            "/api/v1/uploads",
            files={"file": ("photo.jpg", jpeg_header(640, 480), "image/jpeg")},
        )

    assert response.status_code == 201
    image = response.json()["preflight"]["image"]
    assert image["format"] == "jpeg"
    assert image["logical_width"] == 640
    assert image["logical_height"] == 480
    assert image["has_alpha"] is False


def test_webp_preflight_reads_alpha_canvas(tmp_path: Path) -> None:
    with TestClient(upload_test_app(tmp_path)) as client:
        response = client.post(
            "/api/v1/uploads",
            files={"file": ("image.webp", webp_header(300, 200), "image/webp")},
        )

    assert response.status_code == 201
    image = response.json()["preflight"]["image"]
    assert image["format"] == "webp"
    assert image["logical_width"] == 300
    assert image["logical_height"] == 200
    assert image["has_alpha"] is True


def test_pdf_header_is_validated(tmp_path: Path) -> None:
    with TestClient(upload_test_app(tmp_path)) as client:
        valid = client.post(
            "/api/v1/uploads",
            files={"file": ("report.pdf", b"%PDF-1.7\n%%EOF\n", "application/pdf")},
        )
        invalid = client.post(
            "/api/v1/uploads",
            files={"file": ("broken.pdf", b"not-a-pdf", "application/pdf")},
        )

    assert valid.status_code == 201
    assert invalid.status_code == 400
    assert invalid.json()["code"] == "MALFORMED_FILE"


def test_ooxml_with_vba_project_is_rejected(tmp_path: Path) -> None:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("word/vbaProject.bin", b"macro")

    with TestClient(upload_test_app(tmp_path)) as client:
        response = client.post(
            "/api/v1/uploads",
            files={
                "file": (
                    "report.docx",
                    buffer.getvalue(),
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )
            },
        )

    assert response.status_code == 400
    assert response.json()["code"] == "MACRO_FILE_REJECTED"


def test_utf16le_bom_is_detected(tmp_path: Path) -> None:
    content = codecs.BOM_UTF16_LE + "中文内容".encode("utf-16-le")

    with TestClient(upload_test_app(tmp_path)) as client:
        response = client.post(
            "/api/v1/uploads",
            files={"file": ("utf16.txt", content, "text/plain")},
        )

    assert response.status_code == 201
    encoding = response.json()["preflight"]["text_encoding"]
    assert encoding["value"] == "utf-16-le"
    assert encoding["requires_confirmation"] is False


def test_gb18030_requires_confirmation(tmp_path: Path) -> None:
    content = "中文内容".encode("gb18030")

    with TestClient(upload_test_app(tmp_path)) as client:
        response = client.post(
            "/api/v1/uploads",
            files={"file": ("gb.txt", content, "text/plain")},
        )

    assert response.status_code == 201
    encoding = response.json()["preflight"]["text_encoding"]
    assert encoding["value"] == "gb18030"
    assert encoding["requires_confirmation"] is True


def test_markdown_uses_text_encoding_preflight(tmp_path: Path) -> None:
    content = codecs.BOM_UTF8 + "# 标题\n\n正文".encode()

    with TestClient(upload_test_app(tmp_path)) as client:
        response = client.post(
            "/api/v1/uploads",
            files={"file": ("notes.md", content, "text/markdown")},
        )

    assert response.status_code == 201
    encoding = response.json()["preflight"]["text_encoding"]
    assert encoding["value"] == "utf-8-sig"


def test_csv_row_limit_is_enforced(tmp_path: Path) -> None:
    content = b"value\n" + (b"x\n" * 100_001)

    with TestClient(upload_test_app(tmp_path)) as client:
        response = client.post(
            "/api/v1/uploads",
            files={"file": ("large.csv", content, "text/csv")},
        )

    assert response.status_code == 400
    assert response.json()["code"] == "ROW_LIMIT_EXCEEDED"
    assert not list((tmp_path / "staging").glob("*"))
