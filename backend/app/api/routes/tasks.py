from __future__ import annotations

from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request
from sqlalchemy.orm import Session

from app.api.dependencies import get_session
from app.api.errors import AppError, ErrorCode
from app.api.schemas.common import CursorPage
from app.api.schemas.tasks import (
    CreateTaskRequest,
    CreateTurnRequest,
    TaskDetail,
    TaskSummary,
)
from app.application.tasks import (
    IdempotencyConflictError,
    InvalidCursorError,
    TaskInputUnavailableError,
    TaskNotFoundError,
    TaskService,
)
from app.settings import AppSettings

router = APIRouter(prefix="/api/v1/tasks", tags=["tasks"])


@router.post("", response_model=TaskDetail, status_code=202)
def create_task(
    request: Request,
    body: CreateTaskRequest,
    session: Annotated[Session, Depends(get_session)],
    idempotency_key: Annotated[
        str | None,
        Header(alias="Idempotency-Key"),
    ] = None,
) -> TaskDetail:
    settings = cast(AppSettings, request.app.state.settings)
    try:
        return TaskService(session, settings).create(body, idempotency_key)
    except IdempotencyConflictError as exc:
        raise AppError(
            code=ErrorCode.IDEMPOTENCY_CONFLICT,
            message=str(exc),
            status_code=409,
        ) from exc
    except TaskInputUnavailableError as exc:
        raise AppError(
            code=ErrorCode.JOB_INPUT_UNAVAILABLE,
            message=str(exc),
            status_code=400,
        ) from exc


@router.get("", response_model=CursorPage[TaskSummary])
def list_tasks(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
    cursor: Annotated[str | None, Query()] = None,
) -> CursorPage[TaskSummary]:
    settings = cast(AppSettings, request.app.state.settings)
    try:
        return TaskService(session, settings).list(limit=limit, cursor=cursor)
    except InvalidCursorError as exc:
        raise AppError(
            code=ErrorCode.CURSOR_INVALID,
            message=str(exc),
            status_code=400,
        ) from exc


@router.get("/{task_id}", response_model=TaskDetail)
def get_task(
    task_id: UUID,
    request: Request,
    session: Annotated[Session, Depends(get_session)],
) -> TaskDetail:
    settings = cast(AppSettings, request.app.state.settings)
    try:
        return TaskService(session, settings).get(task_id)
    except TaskNotFoundError as exc:
        raise AppError(
            code=ErrorCode.TASK_NOT_FOUND,
            message="任务不存在",
            status_code=404,
        ) from exc


@router.post("/{task_id}/turns", response_model=TaskDetail, status_code=202)
def create_turn(
    task_id: UUID,
    request: Request,
    body: CreateTurnRequest,
    session: Annotated[Session, Depends(get_session)],
    idempotency_key: Annotated[
        str | None,
        Header(alias="Idempotency-Key"),
    ] = None,
) -> TaskDetail:
    settings = cast(AppSettings, request.app.state.settings)
    try:
        return TaskService(session, settings).create_turn(
            task_id,
            body,
            idempotency_key,
        )
    except TaskNotFoundError as exc:
        raise AppError(
            code=ErrorCode.TASK_NOT_FOUND,
            message="任务不存在",
            status_code=404,
        ) from exc
    except TaskInputUnavailableError as exc:
        raise AppError(
            code=ErrorCode.JOB_INPUT_UNAVAILABLE,
            message=str(exc),
            status_code=400,
        ) from exc
    except IdempotencyConflictError as exc:
        raise AppError(
            code=ErrorCode.IDEMPOTENCY_CONFLICT,
            message=str(exc),
            status_code=409,
        ) from exc
