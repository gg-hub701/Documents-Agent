from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import cast, get_args

from app.api.schemas.events import EventUnion
from pydantic import BaseModel

from scripts.contracts.export_openapi import render_openapi

ROOT = Path(__file__).resolve().parents[2]
FRONTEND_ROOT = ROOT / "frontend"
OPENAPI_PATH = ROOT / "backend" / "openapi.json"
FRONTEND_API_DIR = FRONTEND_ROOT / "src" / "lib" / "api"
SCHEMA_PATH = FRONTEND_API_DIR / "schema.d.ts"
EVENTS_PATH = FRONTEND_API_DIR / "events.generated.ts"


def _event_classes() -> list[type[BaseModel]]:
    return cast(list[type[BaseModel]], list(get_args(EventUnion)))


def _event_type(model: type[BaseModel]) -> str:
    fields = model.model_fields
    annotation = fields["type"].annotation
    values = get_args(annotation)
    if len(values) != 1 or not isinstance(values[0], str):
        raise TypeError(f"{model.__name__} must define a string type discriminator")
    return values[0]


def render_event_contract() -> str:
    events = _event_classes()
    event_types = [_event_type(model) for model in events]
    event_types_source = "\n".join(f'  "{event_type}",' for event_type in event_types)
    event_union_source = "\n".join(
        f'  | components["schemas"]["{model.__name__}"]' for model in events
    )
    return (
        "// Generated from backend/app/api/schemas/events.py. Do not edit.\n"
        'import type { components } from "./schema";\n\n'
        "export const EXECUTION_EVENT_TYPES = [\n"
        f"{event_types_source}\n"
        "] as const;\n\n"
        "export type ExecutionEventType = "
        "(typeof EXECUTION_EVENT_TYPES)[number];\n\n"
        "export type ExecutionEvent =\n"
        f"{event_union_source};\n"
    )


def _run_openapi_typescript(openapi_path: Path, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    pnpm = shutil.which("pnpm")
    if pnpm is None:
        raise RuntimeError("pnpm is required to generate frontend contracts")
    openapi_arg = os.path.relpath(openapi_path, FRONTEND_ROOT)
    output_arg = os.path.relpath(output_path, FRONTEND_ROOT)
    subprocess.run(
        [
            pnpm,
            "--dir",
            "frontend",
            "exec",
            "openapi-typescript",
            openapi_arg,
            "--output",
            output_arg,
        ],
        cwd=ROOT,
        check=True,
    )


def _write_contracts(directory: Path) -> None:
    openapi_path = directory / "openapi.json"
    schema_path = directory / "schema.d.ts"
    events_path = directory / "events.generated.ts"
    openapi_path.write_text(render_openapi(), encoding="utf-8", newline="\n")
    _run_openapi_typescript(openapi_path, schema_path)
    events_path.write_text(render_event_contract(), encoding="utf-8", newline="\n")


def _contract_paths(directory: Path) -> dict[Path, Path]:
    return {
        OPENAPI_PATH: directory / "openapi.json",
        SCHEMA_PATH: directory / "schema.d.ts",
        EVENTS_PATH: directory / "events.generated.ts",
    }


def check_contracts() -> bool:
    FRONTEND_API_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=".contract-check-",
        dir=FRONTEND_API_DIR,
    ) as temp:
        generated_dir = Path(temp)
        _write_contracts(generated_dir)
        mismatches = [
            committed_path
            for committed_path, generated_path in _contract_paths(generated_dir).items()
            if not committed_path.exists()
            or committed_path.read_text(encoding="utf-8")
            != generated_path.read_text(encoding="utf-8")
        ]

    if mismatches:
        for path in mismatches:
            print(f"Contract output is missing or stale: {path.relative_to(ROOT)}")
        return False
    return True


def generate_contracts() -> None:
    OPENAPI_PATH.parent.mkdir(parents=True, exist_ok=True)
    FRONTEND_API_DIR.mkdir(parents=True, exist_ok=True)
    OPENAPI_PATH.write_text(render_openapi(), encoding="utf-8", newline="\n")
    _run_openapi_typescript(OPENAPI_PATH, SCHEMA_PATH)
    EVENTS_PATH.write_text(render_event_contract(), encoding="utf-8", newline="\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate frontend API contracts.")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail when committed contract outputs differ from the backend models.",
    )
    args = parser.parse_args()

    if args.check:
        return 0 if check_contracts() else 1

    generate_contracts()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
