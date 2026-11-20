from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.skipif(
    shutil.which("powershell") is None,
    reason="the local quality command is PowerShell-based",
)
def test_quality_command_wrapper_returns_native_failure_code(tmp_path: Path) -> None:
    probe = tmp_path / "quality-probe.ps1"
    probe.write_text(
        "\n".join(
            [
                f". '{ROOT / 'scripts' / 'quality-lib.ps1'}'",
                "Invoke-NativeChecked { cmd /c exit 7 }",
                "Write-Output 'unreachable'",
            ]
        ),
        encoding="utf-8-sig",
        newline="\n",
    )

    result = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(probe),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 7, result.stdout + result.stderr
    assert "unreachable" not in result.stdout
