from __future__ import annotations

import asyncio
import contextlib
import logging

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.api.schemas.events import ExecutionEvent
from app.application.events import record_to_execution_event
from app.infrastructure.db.models.event import ExecutionEvent as ExecutionEventRecord


class EventCursorError(ValueError):
    pass


class EventBroker:
    def __init__(
        self,
        session_factory: sessionmaker[Session],
        *,
        poll_interval_seconds: float = 0.25,
    ) -> None:
        self._session_factory = session_factory
        self._poll_interval_seconds = poll_interval_seconds
        self._subscribers: set[asyncio.Queue[ExecutionEvent]] = set()
        self._last_event_id = 0
        self._task: asyncio.Task[None] | None = None
        self._logger = logging.getLogger("doc_agent.events")

    async def start(self) -> None:
        self._last_event_id = await asyncio.to_thread(self._current_max_event_id)
        self._task = asyncio.create_task(self._poll_loop())

    async def stop(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await self._task
        self._task = None

    def subscribe(self) -> asyncio.Queue[ExecutionEvent]:
        queue: asyncio.Queue[ExecutionEvent] = asyncio.Queue()
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[ExecutionEvent]) -> None:
        self._subscribers.discard(queue)

    async def validate_cursor(self, task_id: str, cursor: int) -> None:
        if cursor < 0:
            raise EventCursorError("事件游标不能为负数")
        if cursor == 0:
            return
        record = await asyncio.to_thread(self._event_by_id, cursor)
        if record is None or record.task_id != task_id:
            raise EventCursorError("事件游标不属于当前任务")

    async def replay(self, task_id: str, cursor: int) -> list[ExecutionEvent]:
        return await asyncio.to_thread(self._events_for_task_after, task_id, cursor)

    async def _poll_loop(self) -> None:
        while True:
            await asyncio.sleep(self._poll_interval_seconds)
            try:
                events = await asyncio.to_thread(
                    self._global_events_after,
                    self._last_event_id,
                )
                for event in events:
                    self._last_event_id = max(self._last_event_id, event.seq)
                    for queue in tuple(self._subscribers):
                        queue.put_nowait(event)
            except asyncio.CancelledError:
                raise
            except Exception:
                self._logger.exception("event.broker.poll_failed")

    def _current_max_event_id(self) -> int:
        with self._session_factory() as session:
            return int(
                session.scalar(select(func.max(ExecutionEventRecord.id))) or 0
            )

    def _event_by_id(self, event_id: int) -> ExecutionEventRecord | None:
        with self._session_factory() as session:
            return session.get(ExecutionEventRecord, event_id)

    def _events_for_task_after(
        self,
        task_id: str,
        cursor: int,
    ) -> list[ExecutionEvent]:
        with self._session_factory() as session:
            records = session.scalars(
                select(ExecutionEventRecord)
                .where(
                    ExecutionEventRecord.task_id == task_id,
                    ExecutionEventRecord.id > cursor,
                )
                .order_by(ExecutionEventRecord.id.asc())
            ).all()
        return [record_to_execution_event(record) for record in records]

    def _global_events_after(self, cursor: int) -> list[ExecutionEvent]:
        with self._session_factory() as session:
            records = session.scalars(
                select(ExecutionEventRecord)
                .where(ExecutionEventRecord.id > cursor)
                .order_by(ExecutionEventRecord.id.asc())
                .limit(500)
            ).all()
        return [record_to_execution_event(record) for record in records]
