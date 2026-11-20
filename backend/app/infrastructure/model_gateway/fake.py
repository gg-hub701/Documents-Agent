from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256

from pydantic import JsonValue, ValidationError

from app.infrastructure.model_gateway.errors import (
    ModelErrorCode,
    ModelGatewayError,
)
from app.infrastructure.model_gateway.gateway import (
    ModelOperation,
    SchemaT,
)

StructuredPayload = Mapping[str, JsonValue]
ResponseValue = StructuredPayload | Sequence[StructuredPayload]


@dataclass(frozen=True, slots=True)
class FakeModelCall:
    operation: ModelOperation
    output_schema: str
    input_sha256: str
    context_keys: tuple[str, ...] = ()
    capabilities: tuple[str, ...] = ()
    image_hashes: tuple[str, ...] = ()
    data_profile_count: int = 0


def _schema_details(exc: ValidationError) -> tuple[str, ...]:
    return tuple(
        f"{'.'.join(str(part) for part in error['loc'])}:{error['type']}"
        for error in exc.errors(include_input=False, include_url=False)
    )


def _digest(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return sha256(encoded).hexdigest()


class FakeModelGateway:
    def __init__(
        self,
        *,
        responses: Mapping[ModelOperation, ResponseValue] | None = None,
    ) -> None:
        self._static_responses: dict[ModelOperation, StructuredPayload] = {}
        self._response_queues: dict[ModelOperation, list[StructuredPayload]] = {}
        self.calls: list[FakeModelCall] = []
        for operation, value in (responses or {}).items():
            self._set_response_value(operation, value)

    def _set_response_value(
        self,
        operation: ModelOperation,
        value: ResponseValue,
    ) -> None:
        if isinstance(value, Mapping):
            self._static_responses[operation] = value
            self._response_queues.pop(operation, None)
        else:
            self._static_responses.pop(operation, None)
            self._response_queues[operation] = list(value)

    def set_response(
        self,
        operation: ModelOperation,
        payload: StructuredPayload,
    ) -> None:
        self._set_response_value(operation, payload)

    def add_response(
        self,
        operation: ModelOperation,
        payload: StructuredPayload,
    ) -> None:
        self._response_queues.setdefault(operation, []).append(payload)
        self._static_responses.pop(operation, None)

    def _take_payload(self, operation: ModelOperation) -> StructuredPayload:
        queue = self._response_queues.get(operation)
        if queue:
            return queue.pop(0)
        payload = self._static_responses.get(operation)
        if payload is None:
            raise ModelGatewayError(ModelErrorCode.MODEL_RESPONSE_UNAVAILABLE)
        return payload

    async def _respond(
        self,
        call: FakeModelCall,
        schema: type[SchemaT],
    ) -> SchemaT:
        self.calls.append(call)
        payload = self._take_payload(call.operation)
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
        call = FakeModelCall(
            operation=ModelOperation.UNDERSTAND,
            output_schema=schema.__name__,
            input_sha256=_digest({"context": context}),
            context_keys=tuple(sorted(context)),
        )
        return await self._respond(call, schema)

    async def plan_dag(
        self,
        intent: Mapping[str, JsonValue],
        capabilities: Sequence[str],
        schema: type[SchemaT],
    ) -> SchemaT:
        call = FakeModelCall(
            operation=ModelOperation.PLAN_DAG,
            output_schema=schema.__name__,
            input_sha256=_digest(
                {
                    "intent": intent,
                    "capabilities": capabilities,
                }
            ),
            context_keys=tuple(sorted(intent)),
            capabilities=tuple(capabilities),
        )
        return await self._respond(call, schema)

    async def map_template(
        self,
        manifest: Mapping[str, JsonValue],
        data_profiles: Sequence[Mapping[str, JsonValue]],
        schema: type[SchemaT],
    ) -> SchemaT:
        call = FakeModelCall(
            operation=ModelOperation.MAP_TEMPLATE,
            output_schema=schema.__name__,
            input_sha256=_digest(
                {
                    "manifest": manifest,
                    "data_profiles": data_profiles,
                }
            ),
            context_keys=tuple(sorted(manifest)),
            data_profile_count=len(data_profiles),
        )
        return await self._respond(call, schema)

    async def generate_spec(
        self,
        context: Mapping[str, JsonValue],
        output_schema: type[SchemaT],
    ) -> SchemaT:
        call = FakeModelCall(
            operation=ModelOperation.GENERATE_SPEC,
            output_schema=output_schema.__name__,
            input_sha256=_digest({"context": context}),
            context_keys=tuple(sorted(context)),
        )
        return await self._respond(call, output_schema)

    async def vision(
        self,
        images_or_regions: Sequence[bytes],
        prompt: str,
        output_schema: type[SchemaT],
    ) -> SchemaT:
        image_hashes = tuple(
            sha256(image).hexdigest() for image in images_or_regions
        )
        call = FakeModelCall(
            operation=ModelOperation.VISION,
            output_schema=output_schema.__name__,
            input_sha256=_digest(
                {
                    "prompt": prompt,
                    "image_hashes": image_hashes,
                    "image_sizes": [len(image) for image in images_or_regions],
                }
            ),
            image_hashes=image_hashes,
        )
        return await self._respond(call, output_schema)
