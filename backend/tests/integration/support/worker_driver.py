from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from typing import TypeVar

from app.infrastructure.clock import Clock
from app.infrastructure.model_gateway import ModelGateway, ModelOperation

OutputT = TypeVar("OutputT")


@dataclass(frozen=True, slots=True)
class DriverCall:
    operation: ModelOperation
    output_schema: str
    started_at: datetime
    finished_at: datetime


class DeterministicWorkerDriver:
    def __init__(self, gateway: ModelGateway, clock: Clock) -> None:
        self._gateway = gateway
        self._clock = clock
        self.calls: list[DriverCall] = []

    async def run(
        self,
        operation: ModelOperation,
        call: Callable[[], Awaitable[OutputT]],
        *,
        duration_seconds: float = 1.0,
    ) -> OutputT:
        started_at = self._clock.now()
        result = await call()
        await self._clock.sleep(duration_seconds)
        finished_at = self._clock.now()
        self.calls.append(
            DriverCall(
                operation=operation,
                output_schema=type(result).__name__,
                started_at=started_at,
                finished_at=finished_at,
            )
        )
        return result
