from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_checked_in_frontend_contracts_match_backend_contracts() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.contracts.generate_frontend_contracts",
            "--check",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
