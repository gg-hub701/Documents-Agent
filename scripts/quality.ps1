$ErrorActionPreference = "Stop"

. (Join-Path $PSScriptRoot "quality-lib.ps1")

$previousDataDir = $env:DOC_AGENT_DATA_DIR
$tempDataDir = Join-Path ([System.IO.Path]::GetTempPath()) (
    "doc-agent-quality-" + [guid]::NewGuid().ToString("N")
)

try {
    Invoke-NativeChecked { uv run ruff check . }
    Invoke-NativeChecked { uv run pyright backend app scripts }
    Invoke-NativeChecked { uv run pytest backend/tests }
    $env:DOC_AGENT_DATA_DIR = $tempDataDir
    try {
        Invoke-NativeChecked { uv run alembic upgrade head }
    }
    finally {
        if ($null -eq $previousDataDir) {
            Remove-Item Env:DOC_AGENT_DATA_DIR -ErrorAction SilentlyContinue
        }
        else {
            $env:DOC_AGENT_DATA_DIR = $previousDataDir
        }
    }
    Invoke-NativeChecked {
        uv run python -m scripts.contracts.generate_frontend_contracts --check
    }
    Invoke-NativeChecked { pnpm --dir frontend lint }
    Invoke-NativeChecked { pnpm --dir frontend typecheck }
    Invoke-NativeChecked { pnpm --dir frontend test }
    Invoke-NativeChecked { pnpm --dir frontend build }

    Write-Host "All quality checks passed."
}
finally {
    if ($null -eq $previousDataDir) {
        Remove-Item Env:DOC_AGENT_DATA_DIR -ErrorAction SilentlyContinue
    }
    else {
        $env:DOC_AGENT_DATA_DIR = $previousDataDir
    }

    $tempRoot = [System.IO.Path]::GetFullPath(
        [System.IO.Path]::GetTempPath()
    )
    $resolvedDataDir = [System.IO.Path]::GetFullPath($tempDataDir)
    if (
        $resolvedDataDir.StartsWith(
            $tempRoot,
            [System.StringComparison]::OrdinalIgnoreCase
        ) -and
        (Split-Path -Leaf $resolvedDataDir).StartsWith(
            "doc-agent-quality-",
            [System.StringComparison]::Ordinal
        ) -and
        (Test-Path -LiteralPath $resolvedDataDir)
    ) {
        Remove-Item -LiteralPath $resolvedDataDir -Recurse -Force
    }
}
