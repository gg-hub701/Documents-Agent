from __future__ import annotations

from enum import StrEnum
from uuid import UUID

from pydantic import AwareDatetime, Field

from app.api.schemas.common import ContractModel


class SupportedFormat(StrEnum):
    DOCX = "docx"
    XLSX = "xlsx"
    PPTX = "pptx"
    PDF = "pdf"
    CSV = "csv"
    MD = "md"
    TXT = "txt"
    PNG = "png"
    JPEG = "jpeg"
    WEBP = "webp"


class FileRole(StrEnum):
    SOURCE_FILE = "source_file"
    CONVERSION_INPUT = "conversion_input"
    TEMPLATE = "template"
    DATA_SOURCE = "data_source"
    REFERENCE_IMAGE = "reference_image"


class UploadStatus(StrEnum):
    STAGED = "staged"
    VALIDATING = "validating"
    VALIDATED = "validated"
    REJECTED = "rejected"
    CONSUMED = "consumed"
    EXPIRED = "expired"
    DELETING = "deleting"


class TextEncodingPreflight(ContractModel):
    value: str
    confidence: float = Field(ge=0.0, le=1.0)
    source: str
    requires_confirmation: bool


class ImagePreflight(ContractModel):
    format: SupportedFormat
    logical_width: int = Field(gt=0)
    logical_height: int = Field(gt=0)
    source_width: int = Field(gt=0)
    source_height: int = Field(gt=0)
    orientation: int
    color_mode: str
    has_alpha: bool


class CsvPreflight(ContractModel):
    delimiter: str
    quotechar: str
    has_header: bool


class UploadPreflight(ContractModel):
    page_count: int | None = Field(default=None, ge=0)
    row_count: int | None = Field(default=None, ge=0)
    slide_count: int | None = Field(default=None, ge=0)
    text_encoding: TextEncodingPreflight | None = None
    image: ImagePreflight | None = None
    csv: CsvPreflight | None = None
    template_candidate: bool = False
    warnings: list[str] = Field(default_factory=list[str])


class UploadRecord(ContractModel):
    upload_id: UUID
    original_name: str
    format: SupportedFormat
    size_bytes: int = Field(ge=0)
    sha256: str
    status: UploadStatus
    preflight: UploadPreflight
    expires_at: AwareDatetime | None


class FileRoleSummary(ContractModel):
    role: FileRole
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: list[str] = Field(default_factory=list[str])


class UploadedFileSummary(ContractModel):
    file_id: UUID
    upload_id: UUID
    original_name: str
    format: SupportedFormat
    size_bytes: int = Field(ge=0)
    sha256: str
    candidate_roles: list[FileRoleSummary] = Field(
        default_factory=list[FileRoleSummary]
    )
    selected_role: FileRole | None = None
