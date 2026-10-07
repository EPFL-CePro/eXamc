#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

DJANGO_DIR="django"
APP_DIR="$DJANGO_DIR/app"

echo "[security] syncing test dependencies..."
uv sync --project "$APP_DIR" --group test

echo "[security] checking hardened mutation endpoints require POST..."
uv run --project "$APP_DIR" python "$DJANGO_DIR/security/check_require_post.py"

echo "[security] scanning for forbidden high-risk calls..."
uv run --project "$APP_DIR" python -W ignore::SyntaxWarning "$DJANGO_DIR/security/check_forbidden_calls.py"

echo "[security] running Bandit (blocking only on HIGH/HIGH)..."
uv run --project "$APP_DIR" bandit -q -r examc_app -x examc_app/migrations,examc_app/tests -lll -iii

echo "[security] auditing dependencies with pip-audit..."
REQS="$(mktemp)"
trap 'rm -f "$REQS"' EXIT
uv export --project "$APP_DIR" --frozen --no-emit-project --all-groups --format requirements-txt > "$REQS"
uv run --project "$APP_DIR" pip-audit -r "$REQS" --disable-pip

echo "[security] all checks passed."