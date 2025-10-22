#!/usr/bin/env bash
set -Eeuo pipefail
trap 'echo "Entrypoint failed at line $LINENO" >&2' ERR

# --- LOG CONTEXTE (pas de secrets) ---
echo "[entrypoint] ENV=${ENV:-unset}"
echo "[entrypoint] DJANGO_SETTINGS_MODULE=${DJANGO_SETTINGS_MODULE:-(set via setdefault dans le code)}"
echo "[entrypoint] running as uid=$(id -u) gid=$(id -g)"
echo "[entrypoint] DB_HOST=${DB_HOST:-unset} DB_PORT=${DB_PORT:-unset}"
echo "[entrypoint] STATIC_ROOT=${STATIC_ROOT:-/static} MEDIA_ROOT=${MEDIA_ROOT:-/media} PRIVATE_MEDIA_ROOT=${PRIVATE_MEDIA_ROOT:-/private_media}"
echo "[entrypoint] CMD to exec: $*"

# --- Wait for DB (configurable) ---
WAIT_FOR_DB="${WAIT_FOR_DB:-1}"
WAIT_HOST="${DB_HOST:-mysql}"
WAIT_PORT="${DB_PORT:-3306}"
WAIT_TIMEOUT="${WAIT_FOR_DB_TIMEOUT:-180}"

if [ "$WAIT_FOR_DB" = "1" ]; then
  export WAIT_HOST WAIT_PORT WAIT_TIMEOUT
  python - <<PY
import os, time, sys, socket
host=os.environ.get("WAIT_HOST","mysql")
port=int(os.environ.get("WAIT_PORT","3306"))
timeout=int(os.environ.get("WAIT_TIMEOUT","180"))
deadline=time.time()+timeout
attempt=0
while time.time()<deadline:
    attempt+=1
    try:
        with socket.create_connection((host, port), timeout=2):
            print(f"[wait-for-db] Connected to {host}:{port} after {attempt} tries")
            sys.exit(0)
    except Exception as e:
        print(f"[wait-for-db] {host}:{port} not ready (try {attempt}) - {e}")
        time.sleep(1)
print(f"[wait-for-db] Gave up after {timeout}s waiting {host}:{port}", file=sys.stderr)
sys.exit(1)
PY
fi

# --- Ensure user & permissions ---
id app >/dev/null 2>&1 || useradd -m -u 1000 -s /bin/bash app || true
if [ "$(id -u)" -eq 0 ]; then
  mkdir -p /static /media /private_media
  chown -R app:app /static /media /private_media /app || true
fi

# --- helpers to run as app ---
run_as_app() { runuser -u app -- bash -lc "$*"; }

# --- DB migrations & static collection (as 'app') ---
run_as_app "python manage.py migrate --noinput"
if [ "${COLLECTSTATIC:-1}" = "1" ]; then
  run_as_app "python manage.py collectstatic --noinput"
fi

# --- hand over to the main process (runserver/gunicorn) ---
exec runuser -u app -- "$@"
