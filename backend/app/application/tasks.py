from __future__ import annotations

import base64
import hashlib
import json
import os
import shutil
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.api.schemas.common import CursorPage
from app.api.schemas.events import TaskQueuedEventData
from app.api.schemas.tasks import (
    CreateTaskRequest,
    CreateTurnRequest,
    EventPreview,
    MessageRole,
    TaskDetail,
    TaskStatus,
    TaskSummary,
    TurnStatus,
    TurnSummary,
)
from app.api.schemas.uploads import SupportedFormat, UploadedFileSummary, UploadStatus
from app.application.events import append_event
from app.infrastructure.db.models.artifact import Artifact
from app.infrastructure.db.models.event import ExecutionEvent
from app.infrastructure.db.models.idempotency import IdempotencyKey
from app.infrastructure.db.models.task import Message, Task, TaskTurn
from app.infrastructure.db.models.upload import Upload, UploadedFile
from app.infrastructure.db.time import as_utc
from app.infrastructure.paths import resolve_relative_path
from app.settings import AppSettings


class TaskNotFoundError(LookupError):
    pass


class TaskInputUnavailableError(ValueError):
    pass


class IdempotencyConflictError(ValueError):
    pass


class InvalidCursorError(ValueError):
    pass


class TaskService:
    def __init__(self, session: Session, settings: AppSettings) -> None:
        self._session = session
        self._settings = settings

    def create(
        self,
        request: CreateTaskRequest,
        idempotency_key: str | None = None,
    ) -> TaskDetail:
        request_hash = self._request_hash(request.model_dump(mode="json"))
        now = datetime.now(UTC)
        replay_id = self._idempotency_replay(
            idempotency_key,
            "create_task",
            request_hash,
            now,
        )
        if replay_id is not None:
            return self.get(UUID(replay_id))

        upload_ids = [str(upload_id) for upload_id in request.upload_ids]
        if len(set(upload_ids)) != len(upload_ids):
            raise TaskInputUnavailableError("上传 ID 不能重复")

        uploads: list[Upload] = []
        for upload_id in upload_ids:
            upload = self._session.get(Upload, upload_id)
            if upload is None or upload.status != UploadStatus.VALIDATED.value:
                raise TaskInputUnavailableError("上传不存在或未通过预检")
            expires_at = as_utc(upload.expires_at)
            if expires_at is not None and expires_at <= now:
                raise TaskInputUnavailableError("上传已过期")
            uploads.append(upload)

        task_id = uuid4()
        turn_id = uuid4()
        task_dir = resolve_relative_path(
            self._settings.data_dir,
            f"tasks/{task_id}",
        )
        input_dir = task_dir / "input"
        input_dir.mkdir(parents=True, exist_ok=True)
        moved_files: list[tuple[Path, Path]] = []
        try:
            uploaded_files = [
                self._move_upload_to_task(upload, task_id, input_dir, moved_files)
                for upload in uploads
            ]
            title = self._title_from_instruction(request.instruction)
            task = Task(
                id=str(task_id),
                title=title,
                status=TaskStatus.QUEUED.value,
                current_turn_id=str(turn_id),
                aggregate_json={
                    "succeeded": 0,
                    "warning": 0,
                    "failed": 0,
                    "blocked": 0,
                },
                created_at=now,
                updated_at=now,
            )
            turn = TaskTurn(
                id=str(turn_id),
                task_id=str(task_id),
                sequence=1,
                instruction=request.instruction,
                task_kinds=[],
                status=TurnStatus.QUEUED.value,
                constraints_json={
                    "output_hints": [
                        hint.model_dump(mode="json") for hint in request.output_hints
                    ]
                },
                created_at=now,
            )
            message = Message(
                task_id=str(task_id),
                turn_id=str(turn_id),
                role=MessageRole.USER.value,
                content=request.instruction,
                metadata_json={"output_hints": turn.constraints_json["output_hints"]},
                created_at=now,
            )
            self._session.add(task)
            self._session.flush()
            self._session.add(turn)
            self._session.flush()
            append_event(
                self._session,
                task_id=str(task_id),
                turn_id=str(turn_id),
                job_id=None,
                event_type="task.queued",
                severity="info",
                message="任务已进入队列",
                data=TaskQueuedEventData(queue_position=0),
                created_at=now,
            )
            self._session.add_all([message, *uploaded_files])
            if idempotency_key is not None:
                self._session.add(
                    self._idempotency_record(
                        idempotency_key,
                        "create_task",
                        request_hash,
                        str(task_id),
                        now,
                    )
                )
            self._session.commit()
        except Exception:
            self._session.rollback()
            self._restore_moved_files(moved_files)
            shutil.rmtree(task_dir, ignore_errors=True)
            raise
        return self.get(task_id)

    def list(
        self,
        *,
        limit: int,
        cursor: str | None,
    ) -> CursorPage[TaskSummary]:
        statement = select(Task).order_by(Task.created_at.desc(), Task.id.desc())
        if cursor is not None:
            cursor_time, cursor_id = self._decode_cursor(cursor)
            statement = statement.where(
                or_(
                    Task.created_at < cursor_time,
                    and_(Task.created_at == cursor_time, Task.id < cursor_id),
                )
            )
        tasks = self._session.scalars(statement.limit(limit + 1)).all()
        has_more = len(tasks) > limit
        visible = tasks[:limit]
        next_cursor = (
            self._encode_cursor(visible[-1]) if has_more and visible else None
        )
        return CursorPage[TaskSummary](
            items=[
                TaskSummary(
                    task_id=UUID(task.id),
                    title=task.title,
                    status=TaskStatus(task.status),
                    created_at=as_utc(task.created_at) or datetime.now(UTC),
                    updated_at=as_utc(task.updated_at) or datetime.now(UTC),
                )
                for task in visible
            ],
            next_cursor=next_cursor,
            has_more=has_more,
        )

    def create_turn(
        self,
        task_id: UUID,
        request: CreateTurnRequest,
        idempotency_key: str | None = None,
    ) -> TaskDetail:
        task = self._session.get(Task, str(task_id))
        if task is None:
            raise TaskNotFoundError(str(task_id))
        request_hash = self._request_hash(request.model_dump(mode="json"))
        now = datetime.now(UTC)
        replay_id = self._idempotency_replay(
            idempotency_key,
            "task_turn",
            request_hash,
            now,
        )
        if replay_id is not None:
            replay_turn = self._session.get(TaskTurn, replay_id)
            if replay_turn is None or replay_turn.task_id != str(task_id):
                raise IdempotencyConflictError("幂等键已绑定其他请求")
            return self.get(UUID(replay_turn.task_id))
        self._validate_base_refs(task_id, request)

        max_sequence = self._session.scalar(
            select(func.max(TaskTurn.sequence)).where(TaskTurn.task_id == str(task_id))
        )
        turn_id = uuid4()
        turn = TaskTurn(
            id=str(turn_id),
            task_id=str(task_id),
            sequence=(max_sequence or 0) + 1,
            instruction=request.instruction,
            task_kinds=[],
            status=TurnStatus.QUEUED.value,
            constraints_json={
                "base_refs": [
                    base_ref.model_dump(mode="json") for base_ref in request.base_refs
                ]
            },
            created_at=now,
        )
        message = Message(
            task_id=str(task_id),
            turn_id=str(turn_id),
            role=MessageRole.USER.value,
            content=request.instruction,
            metadata_json={"base_refs": turn.constraints_json["base_refs"]},
            created_at=now,
        )
        task.current_turn_id = str(turn_id)
        task.status = TaskStatus.QUEUED.value
        task.updated_at = now
        try:
            self._session.add(turn)
            self._session.flush()
            append_event(
                self._session,
                task_id=str(task_id),
                turn_id=str(turn_id),
                job_id=None,
                event_type="task.queued",
                severity="info",
                message="新一轮已进入队列",
                data=TaskQueuedEventData(queue_position=0),
                created_at=now,
            )
            self._session.add(message)
            if idempotency_key is not None:
                self._session.add(
                    self._idempotency_record(
                        idempotency_key,
                        "task_turn",
                        request_hash,
                        str(turn_id),
                        now,
                    )
                )
            self._session.commit()
        except Exception:
            self._session.rollback()
            raise
        return self.get(task_id)

    def get(self, task_id: UUID) -> TaskDetail:
        task = self._session.get(Task, str(task_id))
        if task is None:
            raise TaskNotFoundError(str(task_id))
        turns = self._session.scalars(
            select(TaskTurn)
            .where(TaskTurn.task_id == str(task_id))
            .order_by(TaskTurn.sequence.asc())
        ).all()
        uploaded_files = self._session.scalars(
            select(UploadedFile)
            .where(UploadedFile.task_id == str(task_id))
            .order_by(UploadedFile.created_at.asc())
        ).all()
        recent_events = self._session.scalars(
            select(ExecutionEvent)
            .where(ExecutionEvent.task_id == str(task_id))
            .order_by(ExecutionEvent.id.desc())
            .limit(20)
        ).all()
        return TaskDetail(
            task_id=UUID(task.id),
            title=task.title,
            status=TaskStatus(task.status),
            current_turn_id=(
                UUID(task.current_turn_id) if task.current_turn_id is not None else None
            ),
            aggregate=task.aggregate_json,
            turns=[
                TurnSummary(
                    turn_id=UUID(turn.id),
                    sequence=turn.sequence,
                    instruction=turn.instruction,
                    task_kinds=[],
                    status=TurnStatus(turn.status),
                    created_at=as_utc(turn.created_at) or datetime.now(UTC),
                    started_at=as_utc(turn.started_at),
                    finished_at=as_utc(turn.finished_at),
                )
                for turn in turns
            ],
            uploaded_files=[
                UploadedFileSummary(
                    file_id=UUID(uploaded.id),
                    upload_id=UUID(uploaded.upload_id),
                    original_name=uploaded.original_name,
                    format=SupportedFormat(uploaded.format),
                    size_bytes=uploaded.size_bytes,
                    sha256=uploaded.sha256,
                )
                for uploaded in uploaded_files
            ],
            recent_events=[
                EventPreview(
                    event_id=event.id,
                    type=event.type,
                    message=event.message,
                    severity=event.severity,
                    created_at=as_utc(event.created_at) or datetime.now(UTC),
                )
                for event in reversed(recent_events)
            ],
            created_at=as_utc(task.created_at) or datetime.now(UTC),
            updated_at=as_utc(task.updated_at) or datetime.now(UTC),
            started_at=as_utc(task.started_at),
            finished_at=as_utc(task.finished_at),
        )

    def _move_upload_to_task(
        self,
        upload: Upload,
        task_id: UUID,
        input_dir: Path,
        moved_files: list[tuple[Path, Path]],
    ) -> UploadedFile:
        source = resolve_relative_path(
            self._settings.data_dir / "staging",
            upload.stored_name,
        )
        file_id = uuid4()
        destination = input_dir / f"{file_id}.bin"
        os.replace(source, destination)
        moved_files.append((source, destination))
        upload.status = UploadStatus.CONSUMED.value
        stored_name = destination.relative_to(self._settings.data_dir).as_posix()
        return UploadedFile(
            id=str(file_id),
            task_id=str(task_id),
            upload_id=upload.id,
            original_name=upload.original_name,
            stored_name=stored_name,
            sha256=upload.sha256,
            format=upload.format,
            size_bytes=upload.size_bytes,
            preflight_json=upload.preflight_json,
            created_at=datetime.now(UTC),
        )

    def _validate_base_refs(
        self,
        task_id: UUID,
        request: CreateTurnRequest,
    ) -> None:
        for base_ref in request.base_refs:
            if base_ref.kind == "uploaded_file":
                uploaded = self._session.get(UploadedFile, str(base_ref.id))
                if uploaded is None or uploaded.task_id != str(task_id):
                    raise TaskInputUnavailableError("基准文件不属于当前任务")
            else:
                artifact = self._session.get(Artifact, str(base_ref.id))
                if (
                    artifact is None
                    or artifact.task_id != str(task_id)
                    or artifact.state != "published"
                ):
                    raise TaskInputUnavailableError("基准产物不可用")

    def _idempotency_replay(
        self,
        raw_key: str | None,
        scope: str,
        request_hash: str,
        now: datetime,
    ) -> str | None:
        if raw_key is None:
            return None
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        record = self._session.get(IdempotencyKey, key_hash)
        if record is None:
            return None
        if (as_utc(record.expires_at) or now) <= now:
            self._session.delete(record)
            return None
        if record.scope != scope or record.request_hash != request_hash:
            raise IdempotencyConflictError("幂等键已被不同请求使用")
        return record.response_resource_id

    @staticmethod
    def _idempotency_record(
        raw_key: str,
        scope: str,
        request_hash: str,
        resource_id: str,
        now: datetime,
    ) -> IdempotencyKey:
        return IdempotencyKey(
            key_hash=hashlib.sha256(raw_key.encode()).hexdigest(),
            scope=scope,
            request_hash=request_hash,
            response_resource_id=resource_id,
            created_at=now,
            expires_at=now + timedelta(hours=24),
        )

    @staticmethod
    def _request_hash(payload: dict[str, object]) -> str:
        canonical = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(canonical.encode()).hexdigest()

    @staticmethod
    def _encode_cursor(task: Task) -> str:
        created_at = as_utc(task.created_at) or datetime.now(UTC)
        payload = {
            "created_at": created_at.isoformat(),
            "id": task.id,
        }
        raw = json.dumps(payload, separators=(",", ":")).encode()
        return base64.urlsafe_b64encode(raw).decode().rstrip("=")

    @staticmethod
    def _decode_cursor(cursor: str) -> tuple[datetime, str]:
        try:
            padding = "=" * (-len(cursor) % 4)
            decoded = base64.urlsafe_b64decode(cursor + padding)
            payload = json.loads(decoded)
            created_at = datetime.fromisoformat(str(payload["created_at"]))
            cursor_id = str(payload["id"])
            if created_at.tzinfo is None or not cursor_id:
                raise ValueError
            return created_at.astimezone(UTC), cursor_id
        except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
            raise InvalidCursorError("任务游标无效") from exc

    @staticmethod
    def _restore_moved_files(moved_files: list[tuple[Path, Path]]) -> None:
        for source, destination in reversed(moved_files):
            if destination.exists():
                source.parent.mkdir(parents=True, exist_ok=True)
                os.replace(destination, source)

    @staticmethod
    def _title_from_instruction(instruction: str) -> str:
        title = instruction.strip().splitlines()[0]
        return title[:80]
