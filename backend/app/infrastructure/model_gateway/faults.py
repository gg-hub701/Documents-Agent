from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

from pydantic import JsonValue

from app.infrastructure.model_gateway.errors import (
    ModelErrorCode,
    ModelGatewayError,
)
from app.infrastructure.model_gateway.gateway import (
    ModelGateway,
    ModelOperation,
    SchemaT,
)


@dataclass(frozen=True, slots=True)
class ModelFault:
    operation: ModelOperation
    code: ModelErrorCode
    message: str | None = None
    http_status: int | None = None


class FaultInjectingModelGateway:
    def __init__(
        self,
        delegate: ModelGateway,
        faults: Iterable[ModelFault] = (),
    ) -> None:
        self._delegate = delegate
        self._faults = list(faults)

    def inject(self, fault: ModelFault) -> None:
        self._faults.append(fault)

    def _raise_fault(self, operation: ModelOperation) -> None:
        for index, fault in enumerate(self._faults):
            if fault.operation is operation:
                del self._faults[index]
                raise ModelGatewayError(
                    fault.code,
                    fault.message,
                    http_status=fault.http_status,
                )

    async def understand(
        self,
        context: Mapping[str, JsonValue],
        schema: type[SchemaT],
    ) -> SchemaT:
        self._raise_fault(ModelOperation.UNDERSTAND)
        return await self._delegate.understand(context, schema)

    async def plan_dag(
        self,
        intent: Mapping[str, JsonValue],
        capabilities: Sequence[str],
        schema: type[SchemaT],
    ) -> SchemaT:
        self._raise_fault(ModelOperation.PLAN_DAG)
        return await self._delegate.plan_dag(intent, capabilities, schema)

    async def map_template(
        self,
        manifest: Mapping[str, JsonValue],
        data_profiles: Sequence[Mapping[str, JsonValue]],
        schema: type[SchemaT],
    ) -> SchemaT:
        self._raise_fault(ModelOperation.MAP_TEMPLATE)
        return await self._delegate.map_template(
            manifest,
            data_profiles,
            schema,
        )

    async def generate_spec(
        self,
        context: Mapping[str, JsonValue],
        output_schema: type[SchemaT],
    ) -> SchemaT:
        self._raise_fault(ModelOperation.GENERATE_SPEC)
        return await self._delegate.generate_spec(context, output_schema)

    async def vision(
        self,
        images_or_regions: Sequence[bytes],
        prompt: str,
        output_schema: type[SchemaT],
    ) -> SchemaT:
        self._raise_fault(ModelOperation.VISION)
        return await self._delegate.vision(
            images_or_regions,
            prompt,
            output_schema,
        )
