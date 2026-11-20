from __future__ import annotations

import json
from pathlib import Path

from app.api.main import app


def render_openapi() -> str:
    return json.dumps(
        app.openapi(),
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ) + "\n"


def export_openapi(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_openapi(), encoding="utf-8", newline="\n")


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[2]
    export_openapi(root / "backend" / "openapi.json")
