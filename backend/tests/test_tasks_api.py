# pyright: basic

from pathlib import Path

from alembic import command
from alembic.config import Config
from app.api.main import create_app
from app.api.schemas.common import OfficeHealth
from app.settings import AppSettings
from fastapi.testclient import TestClient


def task_test_app(tmp_path: Path):
    settings = AppSettings.from_env(
        env={"DOC_AGENT_DATA_DIR": str(tmp_path)},
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


def test_create_task_returns_queued_empty_dag_and_persists(
    tmp_path: Path,
) -> None:
    with TestClient(task_test_app(tmp_path)) as client:
        response = client.post(
            "/api/v1/tasks",
            json={
                "upload_ids": [],
                "instruction": "从零生成一份季度经营报告",
                "output_hints": [{"format": "docx", "label": "季度报告"}],
            },
        )

    assert response.status_code == 202
    payload = response.json()
    assert payload["title"] == "从零生成一份季度经营报告"
    assert payload["status"] == "queued"
    assert payload["current_turn_id"] == payload["turns"][0]["turn_id"]
    assert payload["turns"][0]["sequence"] == 1
    assert payload["turns"][0]["status"] == "queued"
    assert payload["jobs"] == []

    task_id = payload["task_id"]
    with TestClient(task_test_app(tmp_path)) as client:
        get_response = client.get(f"/api/v1/tasks/{task_id}")

    assert get_response.status_code == 200
    assert get_response.json()["task_id"] == task_id
    assert get_response.json()["turns"][0]["instruction"] == payload["turns"][0][
        "instruction"
    ]


def test_task_creation_consumes_upload_and_moves_file(tmp_path: Path) -> None:
    app = task_test_app(tmp_path)
    with TestClient(app) as client:
        upload = client.post(
            "/api/v1/uploads",
            files={"file": ("notes.txt", b"hello task", "text/plain")},
        ).json()
        response = client.post(
            "/api/v1/tasks",
            json={
                "upload_ids": [upload["upload_id"]],
                "instruction": "总结 notes.txt",
            },
        )

    assert response.status_code == 202
    payload = response.json()
    assert len(payload["uploaded_files"]) == 1
    assert payload["uploaded_files"][0]["original_name"] == "notes.txt"
    task_input_dir = tmp_path / "tasks" / payload["task_id"] / "input"
    assert len(list(task_input_dir.iterdir())) == 1
    assert not list((tmp_path / "staging").glob("*.bin"))

    with TestClient(task_test_app(tmp_path)) as client:
        upload_response = client.get(
            f"/api/v1/uploads/{upload['upload_id']}"
        )
    assert upload_response.json()["status"] == "consumed"


def test_task_creation_replays_idempotent_request(tmp_path: Path) -> None:
    body = {
        "upload_ids": [],
        "instruction": "生成一份项目周报",
    }

    with TestClient(task_test_app(tmp_path)) as client:
        first = client.post(
            "/api/v1/tasks",
            json=body,
            headers={"Idempotency-Key": "task-create-1"},
        )
        replay = client.post(
            "/api/v1/tasks",
            json=body,
            headers={"Idempotency-Key": "task-create-1"},
        )

    assert first.status_code == 202
    assert replay.status_code == 202
    assert first.json()["task_id"] == replay.json()["task_id"]


def test_changed_request_with_same_idempotency_key_conflicts(
    tmp_path: Path,
) -> None:
    with TestClient(task_test_app(tmp_path)) as client:
        client.post(
            "/api/v1/tasks",
            json={"upload_ids": [], "instruction": "生成周报"},
            headers={"Idempotency-Key": "task-create-conflict"},
        )
        response = client.post(
            "/api/v1/tasks",
            json={"upload_ids": [], "instruction": "生成月报"},
            headers={"Idempotency-Key": "task-create-conflict"},
        )

    assert response.status_code == 409
    assert response.json()["code"] == "IDEMPOTENCY_CONFLICT"


def test_task_list_uses_cursor_pagination(tmp_path: Path) -> None:
    with TestClient(task_test_app(tmp_path)) as client:
        task_ids = [
            client.post(
                "/api/v1/tasks",
                json={"upload_ids": [], "instruction": f"任务 {index}"},
            ).json()["task_id"]
            for index in range(3)
        ]
        first_page = client.get("/api/v1/tasks?limit=2")
        second_page = client.get(
            f"/api/v1/tasks?limit=2&cursor={first_page.json()['next_cursor']}"
        )

    assert first_page.status_code == 200
    assert len(first_page.json()["items"]) == 2
    assert first_page.json()["has_more"] is True
    assert second_page.status_code == 200
    assert len(second_page.json()["items"]) == 1
    assert second_page.json()["has_more"] is False
    returned_ids = {
        item["task_id"]
        for item in first_page.json()["items"] + second_page.json()["items"]
    }
    assert returned_ids == set(task_ids)


def test_invalid_task_cursor_is_rejected(tmp_path: Path) -> None:
    with TestClient(task_test_app(tmp_path)) as client:
        response = client.get("/api/v1/tasks?cursor=not-a-cursor")

    assert response.status_code == 400
    assert response.json()["code"] == "CURSOR_INVALID"


def test_missing_task_returns_stable_error(tmp_path: Path) -> None:
    with TestClient(task_test_app(tmp_path)) as client:
        response = client.get(
            "/api/v1/tasks/9f2a3dc2-4b76-4f5f-b8ee-5b04e79573ee"
        )

    assert response.status_code == 404
    assert response.json()["code"] == "TASK_NOT_FOUND"


def test_new_turn_is_appended_to_existing_task(tmp_path: Path) -> None:
    with TestClient(task_test_app(tmp_path)) as client:
        task = client.post(
            "/api/v1/tasks",
            json={"upload_ids": [], "instruction": "生成周报"},
        ).json()
        response = client.post(
            f"/api/v1/tasks/{task['task_id']}/turns",
            json={"instruction": "补充风险章节", "base_refs": []},
        )

    assert response.status_code == 202
    payload = response.json()
    assert len(payload["turns"]) == 2
    assert payload["turns"][1]["sequence"] == 2
    assert payload["current_turn_id"] == payload["turns"][1]["turn_id"]


def test_consumed_upload_cannot_create_second_task(tmp_path: Path) -> None:
    with TestClient(task_test_app(tmp_path)) as client:
        upload = client.post(
            "/api/v1/uploads",
            files={"file": ("notes.txt", b"hello", "text/plain")},
        ).json()
        first = client.post(
            "/api/v1/tasks",
            json={"upload_ids": [upload["upload_id"]], "instruction": "任务一"},
        )
        second = client.post(
            "/api/v1/tasks",
            json={"upload_ids": [upload["upload_id"]], "instruction": "任务二"},
        )
        tasks = client.get("/api/v1/tasks").json()

    assert first.status_code == 202
    assert second.status_code == 400
    assert second.json()["code"] == "JOB_INPUT_UNAVAILABLE"
    assert len(tasks["items"]) == 1


def test_new_turn_replays_idempotent_request(tmp_path: Path) -> None:
    with TestClient(task_test_app(tmp_path)) as client:
        task = client.post(
            "/api/v1/tasks",
            json={"upload_ids": [], "instruction": "生成周报"},
        ).json()
        body = {"instruction": "补充风险章节", "base_refs": []}
        headers = {"Idempotency-Key": "turn-create-1"}
        first = client.post(
            f"/api/v1/tasks/{task['task_id']}/turns",
            json=body,
            headers=headers,
        )
        replay = client.post(
            f"/api/v1/tasks/{task['task_id']}/turns",
            json=body,
            headers=headers,
        )

    assert first.status_code == 202
    assert replay.status_code == 202
    assert len(replay.json()["turns"]) == 2
    assert first.json()["current_turn_id"] == replay.json()["current_turn_id"]


def test_turn_rejects_uploaded_file_from_other_task(tmp_path: Path) -> None:
    with TestClient(task_test_app(tmp_path)) as client:
        upload = client.post(
            "/api/v1/uploads",
            files={"file": ("notes.txt", b"hello", "text/plain")},
        ).json()
        task_with_file = client.post(
            "/api/v1/tasks",
            json={"upload_ids": [upload["upload_id"]], "instruction": "任务一"},
        ).json()
        other_task = client.post(
            "/api/v1/tasks",
            json={"upload_ids": [], "instruction": "任务二"},
        ).json()
        response = client.post(
            f"/api/v1/tasks/{other_task['task_id']}/turns",
            json={
                "instruction": "基于其他任务文件继续",
                "base_refs": [
                    {
                        "kind": "uploaded_file",
                        "id": task_with_file["uploaded_files"][0]["file_id"],
                    }
                ],
            },
        )

    assert response.status_code == 400
    assert response.json()["code"] == "JOB_INPUT_UNAVAILABLE"
