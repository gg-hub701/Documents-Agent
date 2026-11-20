# pyright: basic

from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256
from typing import Literal

import pytest
from app.infrastructure.clock import FixedClock
from app.infrastructure.model_gateway import (
    FakeModelGateway,
    FaultInjectingModelGateway,
    ModelErrorCode,
    ModelFault,
    ModelGatewayError,
    ModelOperation,
)
from pydantic import BaseModel, ConfigDict, Field

from backend.tests.integration.support.worker_driver import (
    DeterministicWorkerDriver,
)


class ReadIntent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["read"]
    target_format: Literal["csv"]


class ReadPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    steps: list[str] = Field(min_length=1)


class VisionObservation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str
    confidence: float = Field(ge=0.0, le=1.0)


@pytest.mark.asyncio
async def test_fake_gateway_and_worker_driver_run_without_network() -> None:
    clock = FixedClock(
        now=datetime(2026, 11, 20, tzinfo=UTC),
        monotonic=100.0,
    )
    gateway = FakeModelGateway(
        responses={
            ModelOperation.UNDERSTAND: {
                "kind": "read",
                "target_format": "csv",
            },
            ModelOperation.PLAN_DAG: {"steps": ["read", "validate"]},
            ModelOperation.VISION: {"text": "收入表", "confidence": 0.91},
        }
    )
    driver = DeterministicWorkerDriver(gateway, clock)

    intent = await driver.understand({"instruction": "读取 CSV"}, ReadIntent)
    plan = await driver.plan_dag(
        {"kind": "read"},
        ["table.read"],
        ReadPlan,
    )
    observation = await driver.vision(
        [b"image-bytes"],
        "读取表格",
        VisionObservation,
    )

    assert intent == ReadIntent(kind="read", target_format="csv")
    assert plan == ReadPlan(steps=["read", "validate"])
    assert observation == VisionObservation(text="收入表", confidence=0.91)
    assert [call.operation for call in driver.calls] == [
        ModelOperation.UNDERSTAND,
        ModelOperation.PLAN_DAG,
        ModelOperation.VISION,
    ]
    assert [call.started_at.second for call in driver.calls] == [0, 1, 2]
    assert [call.finished_at.second for call in driver.calls] == [1, 2, 3]
    assert [call.status for call in driver.calls] == [
        "succeeded",
        "succeeded",
        "succeeded",
    ]
    assert [call.operation for call in gateway.calls] == [
        ModelOperation.UNDERSTAND,
        ModelOperation.PLAN_DAG,
        ModelOperation.VISION,
    ]
    assert [call.output_schema for call in gateway.calls] == [
        "ReadIntent",
        "ReadPlan",
        "VisionObservation",
    ]
    assert gateway.calls[0].context_keys == ("instruction",)
    assert gateway.calls[1].capabilities == ("table.read",)
    assert gateway.calls[2].image_hashes == (sha256(b"image-bytes").hexdigest(),)
    assert all(len(call.input_sha256) == 64 for call in gateway.calls)


@pytest.mark.asyncio
async def test_fake_gateway_rejects_schema_mismatch() -> None:
    gateway = FakeModelGateway(
        responses={
            ModelOperation.UNDERSTAND: {
                "kind": "edit",
                "target_format": "csv",
            }
        }
    )

    with pytest.raises(ModelGatewayError) as exc_info:
        await gateway.understand({"instruction": "读取"}, ReadIntent)

    assert exc_info.value.code is ModelErrorCode.MODEL_SCHEMA_INVALID


@pytest.mark.asyncio
async def test_fake_gateway_uses_queued_responses_for_repeated_operations() -> None:
    gateway = FakeModelGateway(
        responses={
            ModelOperation.UNDERSTAND: [
                {"kind": "read", "target_format": "csv"},
                {"kind": "read", "target_format": "csv"},
            ]
        }
    )

    first = await gateway.understand({"instruction": "第一次"}, ReadIntent)
    second = await gateway.understand({"instruction": "第二次"}, ReadIntent)

    assert first == second
    assert len(gateway.calls) == 2
    assert gateway.calls[0].input_sha256 != gateway.calls[1].input_sha256


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "code",
    [
        ModelErrorCode.MODEL_TIMEOUT,
        ModelErrorCode.MODEL_RATE_LIMITED,
        ModelErrorCode.MODEL_SCHEMA_INVALID,
    ],
)
async def test_fault_injection_raises_stable_error_codes(
    code: ModelErrorCode,
) -> None:
    delegate = FakeModelGateway(
        responses={
            ModelOperation.UNDERSTAND: {
                "kind": "read",
                "target_format": "csv",
            }
        }
    )
    gateway = FaultInjectingModelGateway(
        delegate,
        [ModelFault(operation=ModelOperation.UNDERSTAND, code=code)],
    )

    with pytest.raises(ModelGatewayError) as exc_info:
        await gateway.understand({"instruction": "读取"}, ReadIntent)

    assert exc_info.value.code is code
    assert delegate.calls == []
    if code is ModelErrorCode.MODEL_RATE_LIMITED:
        assert exc_info.value.http_status == 429


@pytest.mark.asyncio
async def test_worker_driver_records_failed_gateway_call() -> None:
    delegate = FakeModelGateway(
        responses={
            ModelOperation.UNDERSTAND: {
                "kind": "read",
                "target_format": "csv",
            }
        }
    )
    gateway = FaultInjectingModelGateway(
        delegate,
        [
            ModelFault(
                operation=ModelOperation.UNDERSTAND,
                code=ModelErrorCode.MODEL_RATE_LIMITED,
            )
        ],
    )
    driver = DeterministicWorkerDriver(
        gateway,
        FixedClock(now=datetime(2026, 11, 20, tzinfo=UTC)),
    )

    with pytest.raises(ModelGatewayError):
        await driver.understand({"instruction": "读取"}, ReadIntent)

    assert len(driver.calls) == 1
    assert driver.calls[0].status == "failed"
    assert driver.calls[0].error_code == "MODEL_RATE_LIMITED"


@pytest.mark.asyncio
async def test_fixed_clock_advances_deterministically() -> None:
    clock = FixedClock(
        now=datetime(2026, 11, 20, tzinfo=UTC),
        monotonic=10.0,
    )

    await clock.sleep(1.5)

    assert clock.now() == datetime(2026, 11, 20, 0, 0, 1, 500000, tzinfo=UTC)
    assert clock.monotonic() == 11.5
