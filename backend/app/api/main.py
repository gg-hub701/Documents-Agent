from collections.abc import Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.errors import install_exception_handlers
from app.api.routes.contracts import install_contract_components
from app.api.routes.health import router as health_router
from app.api.routes.task_events import router as task_events_router
from app.api.routes.tasks import router as tasks_router
from app.api.routes.uploads import router as uploads_router
from app.api.schemas.common import OfficeHealth
from app.infrastructure.db.engine import create_engine_for_path
from app.infrastructure.db.migrations import check_database_migrations
from app.infrastructure.db.session import create_session_factory
from app.infrastructure.events.broker import EventBroker
from app.infrastructure.observability import configure_logging
from app.infrastructure.office.status import detect_office_status
from app.settings import AppSettings


def _default_office_probe() -> OfficeHealth:
    status = detect_office_status()
    return OfficeHealth(status=status.status, detail=status.detail)


def create_app(
    *,
    settings: AppSettings | None = None,
    office_probe: Callable[[], OfficeHealth] | None = None,
) -> FastAPI:
    resolved_settings = settings or AppSettings.from_env()
    configure_logging(resolved_settings.log_level)
    engine = create_engine_for_path(resolved_settings.database_path)
    session_factory = create_session_factory(engine)
    event_broker = EventBroker(
        session_factory,
        poll_interval_seconds=0.25,
    )
    probe = office_probe or _default_office_probe

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        check_database_migrations(engine)
        application.state.migration_status = "ok"
        application.state.config_status = "ok"
        await event_broker.start()
        try:
            application.state.office_status = probe()
        except Exception:
            application.state.office_status = OfficeHealth(
                status="unknown",
                detail="probe_failed",
            )
        try:
            yield
        finally:
            await event_broker.stop()
            engine.dispose()

    application = FastAPI(
        title="文档处理办公 Agent API",
        version="0.1.0",
        docs_url="/docs",
        openapi_url="/api/v1/openapi.json",
        lifespan=lifespan,
    )
    application.state.settings = resolved_settings
    application.state.database_engine = engine
    application.state.session_factory = session_factory
    application.state.event_broker = event_broker
    install_exception_handlers(application)
    application.include_router(health_router)
    application.include_router(tasks_router)
    application.include_router(task_events_router)
    application.include_router(uploads_router)
    install_contract_components(application)
    return application


app = create_app()
