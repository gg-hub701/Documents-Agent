from __future__ import annotations

from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, File, Request, Response, UploadFile
from sqlalchemy.orm import Session

from app.api.dependencies import get_session
from app.api.errors import AppError, ErrorCode
from app.api.schemas.uploads import UploadRecord
from app.application.uploads import (
    FileTooLargeError,
    ImageDecodeError,
    ImageDimensionLimitError,
    ImagePixelLimitError,
    IncomingUpload,
    InvalidTextEncodingError,
    MacroUploadRejectedError,
    MalformedUploadError,
    RowLimitError,
    TextFileTooLargeError,
    UploadConsumedError,
    UploadNotFoundError,
    UploadRejectedError,
    UploadService,
)
from app.settings import AppSettings

router = APIRouter(prefix="/api/v1/uploads", tags=["uploads"])


@router.post("", response_model=UploadRecord, status_code=201)
def create_upload(
    request: Request,
    file: Annotated[UploadFile, File()],
    session: Annotated[Session, Depends(get_session)],
) -> UploadRecord:
    settings = cast(AppSettings, request.app.state.settings)
    try:
        return UploadService(session, settings).create(
            IncomingUpload(
                original_name=file.filename or "upload.bin",
                content_type=file.content_type,
                stream=file.file,
            )
        )
    except MacroUploadRejectedError as exc:
        raise AppError(
            code=ErrorCode.MACRO_FILE_REJECTED,
            message=str(exc),
            status_code=400,
        ) from exc
    except TextFileTooLargeError as exc:
        raise AppError(
            code=ErrorCode.TEXT_FILE_TOO_LARGE,
            message=str(exc),
            status_code=400,
        ) from exc
    except FileTooLargeError as exc:
        raise AppError(
            code=ErrorCode.FILE_TOO_LARGE,
            message=str(exc),
            status_code=400,
        ) from exc
    except MalformedUploadError as exc:
        raise AppError(
            code=ErrorCode.MALFORMED_FILE,
            message=str(exc),
            status_code=400,
        ) from exc
    except ImageDimensionLimitError as exc:
        raise AppError(
            code=ErrorCode.IMAGE_DIMENSION_LIMIT_EXCEEDED,
            message=str(exc),
            status_code=400,
        ) from exc
    except ImagePixelLimitError as exc:
        raise AppError(
            code=ErrorCode.IMAGE_PIXEL_LIMIT_EXCEEDED,
            message=str(exc),
            status_code=400,
        ) from exc
    except ImageDecodeError as exc:
        raise AppError(
            code=ErrorCode.IMAGE_DECODE_FAILED,
            message=str(exc),
            status_code=400,
        ) from exc
    except InvalidTextEncodingError as exc:
        raise AppError(
            code=ErrorCode.INVALID_TEXT_ENCODING,
            message=str(exc),
            status_code=400,
        ) from exc
    except RowLimitError as exc:
        raise AppError(
            code=ErrorCode.ROW_LIMIT_EXCEEDED,
            message=str(exc),
            status_code=400,
        ) from exc
    except UploadRejectedError as exc:
        raise AppError(
            code=ErrorCode.UNSUPPORTED_FILE_TYPE,
            message=str(exc),
            status_code=400,
        ) from exc


@router.get("/{upload_id}", response_model=UploadRecord)
def get_upload(
    upload_id: UUID,
    request: Request,
    session: Annotated[Session, Depends(get_session)],
) -> UploadRecord:
    settings = cast(AppSettings, request.app.state.settings)
    try:
        return UploadService(session, settings).get(upload_id)
    except UploadNotFoundError as exc:
        raise AppError(
            code=ErrorCode.UPLOAD_NOT_FOUND,
            message="上传记录不存在",
            status_code=404,
        ) from exc


@router.delete("/{upload_id}", status_code=204)
def delete_upload(
    upload_id: UUID,
    request: Request,
    session: Annotated[Session, Depends(get_session)],
) -> Response:
    settings = cast(AppSettings, request.app.state.settings)
    try:
        UploadService(session, settings).delete(upload_id)
    except UploadNotFoundError as exc:
        raise AppError(
            code=ErrorCode.UPLOAD_NOT_FOUND,
            message="上传记录不存在",
            status_code=404,
        ) from exc
    except UploadConsumedError as exc:
        raise AppError(
            code=ErrorCode.UPLOAD_ALREADY_CONSUMED,
            message="已消费的上传不能删除",
            status_code=409,
        ) from exc
    return Response(status_code=204)
