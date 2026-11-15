from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from app.infrastructure.paths import PathForbiddenError, ensure_within


class ConfigurationError(ValueError):
    pass


_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}


def _positive_int(
    env: Mapping[str, str],
    name: str,
    default: int,
) -> int:
    raw = env.get(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ConfigurationError(f"{name} 必须是正整数") from exc
    if value <= 0:
        raise ConfigurationError(f"{name} 必须是正整数")
    return value


@dataclass(frozen=True, slots=True)
class AppSettings:
    data_dir: Path
    database_path: Path
    log_level: str
    office_render_timeout_seconds: int
    task_timeout_seconds: int
    model_request_timeout_seconds: int
    max_model_calls_per_job: int
    max_tool_calls_per_job: int
    upload_staging_ttl_hours: int

    @classmethod
    def from_env(
        cls,
        *,
        env: Mapping[str, str] | None = None,
        cwd: Path | None = None,
    ) -> AppSettings:
        source = os.environ if env is None else env
        working_directory = (cwd or Path.cwd()).resolve()

        data_dir = Path(source.get("DOC_AGENT_DATA_DIR", "./data")).expanduser()
        if not data_dir.is_absolute():
            data_dir = working_directory / data_dir
        data_dir = data_dir.resolve()

        database_config = source.get("DOC_AGENT_DB_PATH", "app.db")
        configured_database_path = Path(database_config).expanduser()
        if configured_database_path.is_absolute():
            database_path = configured_database_path
        else:
            if configured_database_path.drive or ".." in configured_database_path.parts:
                raise PathForbiddenError("数据库路径必须是数据根目录内的相对路径")
            database_path = data_dir / configured_database_path
        database_path = ensure_within(data_dir, database_path)

        log_level = source.get("LOG_LEVEL", "INFO").upper()
        if log_level not in _LOG_LEVELS:
            raise ConfigurationError("LOG_LEVEL 不是受支持的日志级别")

        settings = cls(
            data_dir=data_dir,
            database_path=database_path,
            log_level=log_level,
            office_render_timeout_seconds=_positive_int(
                source,
                "OFFICE_RENDER_TIMEOUT_SECONDS",
                120,
            ),
            task_timeout_seconds=_positive_int(
                source,
                "DOC_AGENT_TASK_TIMEOUT_SECONDS",
                900,
            ),
            model_request_timeout_seconds=_positive_int(
                source,
                "MODEL_REQUEST_TIMEOUT_SECONDS",
                60,
            ),
            max_model_calls_per_job=_positive_int(
                source,
                "DOC_AGENT_MAX_MODEL_CALLS_PER_JOB",
                12,
            ),
            max_tool_calls_per_job=_positive_int(
                source,
                "DOC_AGENT_MAX_TOOL_CALLS_PER_JOB",
                30,
            ),
            upload_staging_ttl_hours=_positive_int(
                source,
                "UPLOAD_STAGING_TTL_HOURS",
                24,
            ),
        )
        settings.ensure_directories()
        return settings

    def ensure_directories(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        for name in ("tasks", "staging", "logs"):
            (self.data_dir / name).mkdir(parents=True, exist_ok=True)
