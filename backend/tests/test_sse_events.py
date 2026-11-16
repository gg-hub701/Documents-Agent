# pyright: basic

import sqlite3
import threading
import time
from pathlib import Path

from alembic import command
from alembic.config import Config
from app.api.main import create_app
from app.api.schemas.common import OfficeHealth
from app.api.schemas.events import ToolStartedEventData
from app.application.events import append_event
from app.settings import AppSettings
from fastapi.testclient import TestClient


def sse_test_app(tmp_path: Path):
    settings = AppSettings.from_env(
        env={
            "DOC_AGENT_DATA_DIR": str(tmp_path),
            "SSE_HEARTBEAT_SECONDS": "1",
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


def create_task(client: TestClient, instruction: str = "生成周报") -> dict:
    return client.post(
        "/api/v1/tasks",
        json={"upload_ids": [], "instruction": instruction},
    ).json()


def task_event_ids(database_path: Path, task_id: str) -> list[int]:
    with sqlite3.connect(database_path) as connection:
        rows = connection.execute(
            "SELECT id FROM execution_events WHERE task_id = ? ORDER BY id",
            (task_id,),
        ).fetchall()
    return [int(row[0]) for row in rows]


def test_task_creation_persists_task_queued_event(tmp_path: Path) -> None:
    app = sse_test_app(tmp_path)
    with TestClient(app) as client:
        task = create_task(client)

    event_ids = task_event_ids(tmp_path / "app.db", task["task_id"])
    assert len(event_ids) == 1
    with sqlite3.connect(tmp_path / "app.db") as connection:
        event_type, payload = connection.execute(
            "SELECT type, payload_json FROM execution_events WHERE id = ?",
            (event_ids[0],),
        ).fetchone()
    assert event_type == "task.queued"
    assert '"queue_position"' in payload


def test_sse_replays_persisted_events(tmp_path: Path) -> None:
    app = sse_test_app(tmp_path)
    with TestClient(app) as client:
        task = create_task(client)
        with client.stream(
            "GET",
            f"/api/v1/tasks/{task['task_id']}/events?after_event_id=0",
        ) as response:
            assert response.status_code == 200
            assert response.headers["content-type"].startswith("text/event-stream")
            lines = response.iter_lines()
            id_line = next(lines)
            event_line = next(lines)
            data_line = next(lines)

    assert id_line.startswith("id: ")
    assert event_line == "event: task.queued"
    assert data_line.startswith("data: ")
    assert '"type":"task.queued"' in data_line
    assert f'"task_id":"{task["task_id"]}"' in data_line


def test_sse_rejects_cursor_from_another_task(tmp_path: Path) -> None:
    app = sse_test_app(tmp_path)
    with TestClient(app) as client:
        first = create_task(client, "任务一")
        second = create_task(client, "任务二")
        first_event_id = task_event_ids(tmp_path / "app.db", first["task_id"])[0]
        response = client.get(
            f"/api/v1/tasks/{second['task_id']}/events"
            f"?after_event_id={first_event_id}"
        )

    assert response.status_code == 400
    assert response.json()["code"] == "EVENT_CURSOR_INVALID"


def test_last_event_id_header_resumes_after_event(tmp_path: Path) -> None:
    app = sse_test_app(tmp_path)
    database_path = tmp_path / "app.db"
    with TestClient(app) as client:
        task = create_task(client)
        first_event_id = task_event_ids(database_path, task["task_id"])[0]
        with app.state.session_factory() as session:
            append_event(
                session,
                task_id=task["task_id"],
                turn_id=task["current_turn_id"],
                job_id=None,
                event_type="tool.started",
                severity="info",
                message="开始读取文档",
                data=ToolStartedEventData(tool_name="document.read"),
            )
            session.commit()

        with client.stream(
            "GET",
            f"/api/v1/tasks/{task['task_id']}/events",
            headers={"Last-Event-ID": str(first_event_id)},
        ) as response:
            lines = response.iter_lines()
            id_line = next(lines)
            event_line = next(lines)
            data_line = next(lines)

    assert id_line.startswith("id: ")
    assert event_line == "event: tool.started"
    assert '"tool_name":"document.read"' in data_line


def test_sse_receives_live_event(tmp_path: Path) -> None:
    app = sse_test_app(tmp_path)
    database_path = tmp_path / "app.db"
    with TestClient(app) as client:
        task = create_task(client)
        latest_event_id = task_event_ids(database_path, task["task_id"])[-1]

        def append_live_event() -> None:
            time.sleep(0.35)
            with app.state.session_factory() as session:
                append_event(
                    session,
                    task_id=task["task_id"],
                    turn_id=task["current_turn_id"],
                    job_id=None,
                    event_type="tool.started",
                    severity="info",
                    message="实时工具开始",
                    data=ToolStartedEventData(tool_name="document.read"),
                )
                session.commit()

        thread = threading.Thread(target=append_live_event)
        with client.stream(
            "GET",
            f"/api/v1/tasks/{task['task_id']}/events"
            f"?after_event_id={latest_event_id}",
        ) as response:
            thread.start()
            lines = response.iter_lines()
            seen_event = None
            for line in lines:
                if line.startswith("event: "):
                    seen_event = line.removeprefix("event: ")
                    if seen_event == "tool.started":
                        break
        thread.join()

    assert seen_event == "tool.started"


def test_sse_emits_heartbeat_without_persisting_event(tmp_path: Path) -> None:
    app = sse_test_app(tmp_path)
    database_path = tmp_path / "app.db"
    with TestClient(app) as client:
        task = create_task(client)
        latest_event_id = task_event_ids(database_path, task["task_id"])[-1]
        before_count = len(task_event_ids(database_path, task["task_id"]))
        with client.stream(
            "GET",
            f"/api/v1/tasks/{task['task_id']}/events"
            f"?after_event_id={latest_event_id}",
        ) as response:
            lines = response.iter_lines()
            seen_event = None
            for line in lines:
                if line.startswith("event: "):
                    seen_event = line.removeprefix("event: ")
                    if seen_event == "heartbeat":
                        break
        after_count = len(task_event_ids(database_path, task["task_id"]))

    assert seen_event == "heartbeat"
    assert after_count == before_count


def test_task_detail_includes_recent_execution_events(tmp_path: Path) -> None:
    app = sse_test_app(tmp_path)
    with TestClient(app) as client:
        task = create_task(client)
        detail = client.get(f"/api/v1/tasks/{task['task_id']}").json()

    assert len(detail["recent_events"]) == 1
    assert detail["recent_events"][0]["type"] == "task.queued"
    assert detail["recent_events"][0]["message"] == "任务已进入队列"


def test_negative_event_cursor_is_rejected(tmp_path: Path) -> None:
    app = sse_test_app(tmp_path)
    with TestClient(app) as client:
        task = create_task(client)
        response = client.get(
            f"/api/v1/tasks/{task['task_id']}/events?after_event_id=-1"
        )

    assert response.status_code == 400
    assert response.json()["code"] == "EVENT_CURSOR_INVALID"


def test_malformed_last_event_id_is_rejected(tmp_path: Path) -> None:
    app = sse_test_app(tmp_path)
    with TestClient(app) as client:
        task = create_task(client)
        response = client.get(
            f"/api/v1/tasks/{task['task_id']}/events",
            headers={"Last-Event-ID": "invalid"},
        )

    assert response.status_code == 400
    assert response.json()["code"] == "EVENT_CURSOR_INVALID"
