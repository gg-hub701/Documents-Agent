from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Literal, TypeVar

from app.infrastructure.clock import Clock
from app.infrastructure.model_gateway import (
    ModelGateway,
    ModelGatewayError,
    ModelOperation,
)
from pydantic import BaseModel, JsonValue

OutputModel = TypeVar("OutputModel", bound=BaseModel)


@dataclass(frozen=True, slots=True)
class DriverCall:
    operation: ModelOperation
    output_schema: str
    status: Literal["succeeded", "failed"]
    error_code: str | None
    started_at: datetime
    finished_at: datetime


class DeterministicWorkerDriver:
    def __init__(self, gateway: ModelGateway, clock: Clock) -> None:
        self._gateway = gateway
        self._clock = clock
        self.calls: list[DriverCall] = []

    async def _run(
        self,
        operation: ModelOperation,
        schema: type[OutputModel],
        call: Callable[[], Awaitable[OutputModel]],
        *,
        duration_seconds: float,
    ) -> OutputModel:
        started_at = self._clock.now()
        try:
            result = await call()
        except ModelGatewayError as exc:
            await self._clock.sleep(duration_seconds)
            self.calls.append(
                DriverCall(
                    operation=operation,
                    output_schema=schema.__name__,
                    status="failed",
                    error_code=exc.code.value,
                    started_at=started_at,
                    finished_at=self._clock.now(),
                )
            )
            raise
        except Exception:
            await self._clock.sleep(duration_seconds)
            self.calls.append(
                DriverCall(
                    operation=operation,
                    output_schema=schema.__name__,
                    status="failed",
                    error_code="MODEL_DRIVER_ERROR",
                    started_at=started_at,
                    finished_at=self._clock.now(),
                )
            )
            raise

        await self._clock.sleep(duration_seconds)
        self.calls.append(
            DriverCall(
                operation=operation,
                output_schema=schema.__name__,
                status="succeeded",
                error_code=None,
                started_at=started_at,
                finished_at=self._clock.now(),
            )
        )
        return result

    async def understand(
        self,
        context: Mapping[str, JsonValue],
        schema: type[OutputModel],
    ) -> OutputModel:
        return await self._run(
            ModelOperation.UNDERSTAND,
            schema,
            lambda: self._gateway.understand(context, schema),
            duration_seconds=1.0,
        )

    async def plan_dag(
        self,
        intent: Mapping[str, JsonValue],
        capabilities: Sequence[str],
        schema: type[OutputModel],
    ) -> OutputModel:
        return await self._run(
            ModelOperation.PLAN_DAG,
            schema,
            lambda: self._gateway.plan_dag(intent, capabilities, schema),
            duration_seconds=1.0,
        )

    async def map_template(
        self,
        manifest: Mapping[str, JsonValue],
        data_profiles: Sequence[Mapping[str, JsonValue]],
        schema: type[OutputModel],
    ) -> OutputModel:
        return await self._run(
            ModelOperation.MAP_TEMPLATE,
            schema,
            lambda: self._gateway.map_template(
                manifest,
                data_profiles,
                schema,
            ),
            duration_seconds=1.0,
        )

    async def generate_spec(
        self,
        context: Mapping[str, JsonValue],
        schema: type[OutputModel],
    ) -> OutputModel:
        return await self._run(
            ModelOperation.GENERATE_SPEC,
            schema,
            lambda: self._gateway.generate_spec(context, schema),
            duration_seconds=1.0,
        )

    async def vision(
        self,
        images_or_regions: Sequence[bytes],
        prompt: str,
        schema: type[OutputModel],
    ) -> OutputModel:
        return await self._run(
            ModelOperation.VISION,
            schema,
            lambda: self._gateway.vision(images_or_regions, prompt, schema),
            duration_seconds=1.0,
        )
