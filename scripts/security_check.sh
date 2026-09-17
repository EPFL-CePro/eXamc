#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

DJANGO_DIR="django"
APP_DIR="$DJANGO_DIR/app"

echo "[security] syncing test dependencies..."
uv sync --project "$APP_DIR" --group test

echo "[security] checking hardened mutation endpoints require POST..."
uv run --project "$APP_DIR" python scripts/check_require_post.py

echo "[security] scanning for forbidden high-risk calls..."
uv run --project "$APP_DIR" python -W ignore::SyntaxWarning scripts/check_forbidden_calls.py

echo "[security] running Bandit (blocking only on HIGH/HIGH)..."
uv run --project "$APP_DIR" bandit -q -r examc_app -x examc_app/migrations,examc_app/tests -lll -iii

echo "[security] running dependency audit..."
uv run --project "$APP_DIR" pip-audit

echo "[security] all checks passed."