from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.dependencies import get_session
from app.api.errors import AppError, ErrorCode
from app.api.schemas.events import (
    ExecutionEvent,
    HeartbeatEvent,
    HeartbeatEventData,
)
from app.infrastructure.db.models.task import Task
from app.infrastructure.events.broker import EventBroker, EventCursorError
from app.settings import AppSettings

router = APIRouter(prefix="/api/v1/tasks", tags=["events"])


def _format_sse(event: ExecutionEvent, *, include_id: bool = True) -> str:
    lines: list[str] = []
    if include_id:
        lines.append(f"id: {event.seq}")
    lines.extend(
        [
            f"event: {event.type}",
            f"data: {event.model_dump_json()}",
            "",
            "",
        ]
    )
    return "\n".join(lines)


@router.get("/{task_id}/events")
async def task_events(
    task_id: UUID,
    request: Request,
    session: Annotated[Session, Depends(get_session)],
    after_event_id: Annotated[int | None, Query()] = None,
    last_event_id: Annotated[
        str | None,
        Header(alias="Last-Event-ID"),
    ] = None,
) -> StreamingResponse:
    if session.get(Task, str(task_id)) is None:
        raise AppError(
            code=ErrorCode.TASK_NOT_FOUND,
            message="任务不存在",
            status_code=404,
        )

    cursor = 0
    try:
        if last_event_id is not None:
            cursor = int(last_event_id)
        elif after_event_id is not None:
            cursor = after_event_id
    except ValueError as exc:
        raise AppError(
            code=ErrorCode.EVENT_CURSOR_INVALID,
            message="事件游标无效",
            status_code=400,
        ) from exc

    broker = cast(EventBroker, request.app.state.event_broker)
    settings = cast(AppSettings, request.app.state.settings)
    try:
        await broker.validate_cursor(str(task_id), cursor)
    except EventCursorError as exc:
        raise AppError(
            code=ErrorCode.EVENT_CURSOR_INVALID,
            message=str(exc),
            status_code=400,
        ) from exc

    async def stream():
        queue = broker.subscribe()
        last_sent = cursor
        try:
            replay = await broker.replay(str(task_id), cursor)
            for event in replay:
                last_sent = max(last_sent, event.seq)
                yield _format_sse(event)
            while True:
                try:
                    event = await asyncio.wait_for(
                        queue.get(),
                        timeout=settings.sse_heartbeat_seconds,
                    )
                except TimeoutError:
                    heartbeat = HeartbeatEvent(
                        seq=max(last_sent, 1),
                        type="heartbeat",
                        task_id=task_id,
                        turn_id=None,
                        job_id=None,
                        timestamp=datetime.now(UTC),
                        data=HeartbeatEventData(
                            interval_seconds=settings.sse_heartbeat_seconds
                        ),
                    )
                    yield _format_sse(heartbeat, include_id=False)
                    continue
                if event.seq <= last_sent or event.task_id != task_id:
                    continue
                last_sent = event.seq
                yield _format_sse(event)
        finally:
            broker.unsubscribe(queue)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
