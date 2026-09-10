#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "[security] checking hardened mutation endpoints require POST..."
python3 scripts/check_require_post.py

echo "[security] scanning for forbidden high-risk calls..."
python3 -W ignore::SyntaxWarning scripts/check_forbidden_calls.py

echo "[security] running Bandit (blocking only on HIGH/HIGH)..."
python3 -m bandit -q -r app/examc_app -x app/examc_app/migrations,app/examc_app/tests -lll -iii

echo "[security] running dependency audit..."
AUDIT_REQUIREMENTS="$(mktemp)"
trap 'rm -f "$AUDIT_REQUIREMENTS"' EXIT
uv --directory app export --format requirements.txt --no-dev --no-hashes -o "$AUDIT_REQUIREMENTS" >/dev/null
# Drop the local editable install line (-e .): it's the app itself, not a
# PyPI dependency, and pip-audit can't resolve it without cwd=app anyway.
grep -v '^-e \.' "$AUDIT_REQUIREMENTS" > "$AUDIT_REQUIREMENTS.filtered"
mv "$AUDIT_REQUIREMENTS.filtered" "$AUDIT_REQUIREMENTS"
python3 -m pip_audit -r "$AUDIT_REQUIREMENTS"

echo "[security] all checks passed."
