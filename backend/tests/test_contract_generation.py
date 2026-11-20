from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.skipif(
    shutil.which("pnpm") is None,
    reason="contract generation is covered by the dedicated contracts CI job",
)
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
