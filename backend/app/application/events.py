from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, TypeAdapter
from sqlalchemy.orm import Session

from app.api.schemas.events import ExecutionEvent
from app.infrastructure.db.models.event import ExecutionEvent as ExecutionEventRecord
from app.infrastructure.db.time import as_utc

_EVENT_ADAPTER: TypeAdapter[ExecutionEvent] = TypeAdapter(ExecutionEvent)


def append_event(
    session: Session,
    *,
    task_id: str,
    turn_id: str | None,
    job_id: str | None,
    event_type: str,
    severity: str,
    message: str,
    data: BaseModel,
    created_at: datetime | None = None,
) -> ExecutionEvent:
    record = ExecutionEventRecord(
        task_id=task_id,
        turn_id=turn_id,
        job_id=job_id,
        type=event_type,
        severity=severity,
        message=message,
        payload_json=data.model_dump(mode="json"),
        created_at=created_at or datetime.now(UTC),
    )
    session.add(record)
    session.flush()
    return record_to_execution_event(record)


def record_to_execution_event(record: ExecutionEventRecord) -> ExecutionEvent:
    return _EVENT_ADAPTER.validate_python(
        {
            "seq": record.id,
            "type": record.type,
            "task_id": record.task_id,
            "turn_id": record.turn_id,
            "job_id": record.job_id,
            "timestamp": as_utc(record.created_at),
            "data": record.payload_json,
        }
    )
