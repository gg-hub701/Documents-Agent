from __future__ import annotations

from collections.abc import Mapping, Sequence

from pydantic import JsonValue, ValidationError

from app.infrastructure.model_gateway.errors import (
    ModelErrorCode,
    ModelGatewayError,
)
from app.infrastructure.model_gateway.gateway import (
    ModelOperation,
    SchemaT,
)


def _schema_details(exc: ValidationError) -> tuple[str, ...]:
    return tuple(
        f"{'.'.join(str(part) for part in error['loc'])}:{error['type']}"
        for error in exc.errors(include_input=False, include_url=False)
    )


class FakeModelGateway:
    def __init__(
        self,
        *,
        responses: Mapping[
            ModelOperation,
            Mapping[str, JsonValue],
        ]
        | None = None,
    ) -> None:
        self.responses = dict(responses or {})
        self.calls: list[ModelOperation] = []

    def set_response(
        self,
        operation: ModelOperation,
        payload: Mapping[str, JsonValue],
    ) -> None:
        self.responses[operation] = payload

    async def _respond(
        self,
        operation: ModelOperation,
        schema: type[SchemaT],
    ) -> SchemaT:
        self.calls.append(operation)
        payload = self.responses.get(operation)
        if payload is None:
            raise ModelGatewayError(ModelErrorCode.MODEL_RESPONSE_UNAVAILABLE)
        try:
            return schema.model_validate(payload)
        except ValidationError as exc:
            raise ModelGatewayError(
                ModelErrorCode.MODEL_SCHEMA_INVALID,
                details=_schema_details(exc),
            ) from exc

    async def understand(
        self,
        context: Mapping[str, JsonValue],
        schema: type[SchemaT],
    ) -> SchemaT:
        del context
        return await self._respond(ModelOperation.UNDERSTAND, schema)

    async def plan_dag(
        self,
        intent: Mapping[str, JsonValue],
        capabilities: Sequence[str],
        schema: type[SchemaT],
    ) -> SchemaT:
        del intent, capabilities
        return await self._respond(ModelOperation.PLAN_DAG, schema)

    async def map_template(
        self,
        manifest: Mapping[str, JsonValue],
        data_profiles: Sequence[Mapping[str, JsonValue]],
        schema: type[SchemaT],
    ) -> SchemaT:
        del manifest, data_profiles
        return await self._respond(ModelOperation.MAP_TEMPLATE, schema)

    async def generate_spec(
        self,
        context: Mapping[str, JsonValue],
        output_schema: type[SchemaT],
    ) -> SchemaT:
        del context
        return await self._respond(ModelOperation.GENERATE_SPEC, output_schema)

    async def vision(
        self,
        images_or_regions: Sequence[bytes],
        prompt: str,
        output_schema: type[SchemaT],
    ) -> SchemaT:
        del images_or_regions, prompt
        return await self._respond(ModelOperation.VISION, output_schema)
