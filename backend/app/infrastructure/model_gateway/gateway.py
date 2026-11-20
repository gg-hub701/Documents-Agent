from __future__ import annotations

from collections.abc import Mapping, Sequence
from enum import StrEnum
from typing import Protocol, TypeVar

from pydantic import BaseModel, JsonValue


class ModelOperation(StrEnum):
    UNDERSTAND = "understand"
    PLAN_DAG = "plan_dag"
    MAP_TEMPLATE = "map_template"
    GENERATE_SPEC = "generate_spec"
    VISION = "vision"


SchemaT = TypeVar("SchemaT", bound=BaseModel)


class ModelGateway(Protocol):
    async def understand(
        self,
        context: Mapping[str, JsonValue],
        schema: type[SchemaT],
    ) -> SchemaT: ...

    async def plan_dag(
        self,
        intent: Mapping[str, JsonValue],
        capabilities: Sequence[str],
        schema: type[SchemaT],
    ) -> SchemaT: ...

    async def map_template(
        self,
        manifest: Mapping[str, JsonValue],
        data_profiles: Sequence[Mapping[str, JsonValue]],
        schema: type[SchemaT],
    ) -> SchemaT: ...

    async def generate_spec(
        self,
        context: Mapping[str, JsonValue],
        output_schema: type[SchemaT],
    ) -> SchemaT: ...

    async def vision(
        self,
        images_or_regions: Sequence[bytes],
        prompt: str,
        output_schema: type[SchemaT],
    ) -> SchemaT: ...
