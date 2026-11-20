$ErrorActionPreference = "Stop"

uv run ruff check .
uv run pyright backend app scripts
uv run pytest backend/tests
uv run alembic upgrade head
uv run python -m scripts.contracts.generate_frontend_contracts --check
pnpm --dir frontend lint
pnpm --dir frontend typecheck
pnpm --dir frontend test
pnpm --dir frontend build

Write-Host "All quality checks passed."
