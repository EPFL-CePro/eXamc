#!/usr/bin/env bash
# Entrypoint of the django, celery and celery_beat containers (same image):
# waits for MySQL, runs the migrations and collectstatic when enabled, then runs the command.
#
#   MIGRATE=1              run `migrate` (only the django service; celery and celery_beat set 0)
#   COLLECTSTATIC=1        run `collectstatic` (same)
#   WAIT_FOR_DB=1          wait for MySQL before anything else
#   WAIT_FOR_DB_TIMEOUT=180
#   DB_HOST=mysql DB_PORT=3306
#
# The images run as the examc user (USER in the Dockerfile, UID:GID in Compose), never as root.

set -Eeuo pipefail
trap 'echo "[entrypoint] failed at line $LINENO" >&2' ERR

# ---- Default command: Gunicorn ----
if [ "$#" -eq 0 ] || [ -z "${1:-}" ]; then
  set -- gunicorn examc.wsgi:application --config gunicorn.conf.py
fi

# ---- Context (no secrets) ----
echo "[entrypoint] ENV=${ENV:-unset}"
echo "[entrypoint] DJANGO_SETTINGS_MODULE=${DJANGO_SETTINGS_MODULE:-(default from the code)}"
echo "[entrypoint] running as uid=$(id -u) gid=$(id -g)"
echo "[entrypoint] DB_HOST=${DB_HOST:-mysql} DB_PORT=${DB_PORT:-3306}"
echo "[entrypoint] STATIC_ROOT=${STATIC_ROOT:-/static} PRIVATE_MEDIA_ROOT=${PRIVATE_MEDIA_ROOT:-/private_media}"
echo "[entrypoint] $(python --version)"
echo "[entrypoint] MIGRATE=${MIGRATE:-1} COLLECTSTATIC=${COLLECTSTATIC:-1}"
echo "[entrypoint] command: $*"

if [ "$(id -u)" -eq 0 ]; then
  echo "[entrypoint] warning: running as root; the images are meant to run as examc" >&2
fi

# ---- Wait for MySQL ----
if [ "${WAIT_FOR_DB:-1}" = "1" ]; then
  WAIT_HOST="${DB_HOST:-mysql}" \
  WAIT_PORT="${DB_PORT:-3306}" \
  WAIT_TIMEOUT="${WAIT_FOR_DB_TIMEOUT:-180}" \
  python - <<'PY'
import os
import socket
import sys
import time

host = os.environ["WAIT_HOST"]
port = int(os.environ["WAIT_PORT"])
timeout = int(os.environ["WAIT_TIMEOUT"])
deadline = time.time() + timeout
attempt = 0

while time.time() < deadline:
    attempt += 1
    try:
        with socket.create_connection((host, port), timeout=2):
            print(f"[wait-for-db] connected to {host}:{port} after {attempt} attempt(s)")
            sys.exit(0)
    except OSError as error:
        print(f"[wait-for-db] {host}:{port} not ready (attempt {attempt}): {error}")
        time.sleep(1)

print(f"[wait-for-db] gave up after {timeout}s waiting for {host}:{port}", file=sys.stderr)
sys.exit(1)
PY
fi

# ---- Migrations and static files (django service only) ----
if [ "${MIGRATE:-1}" = "1" ]; then
  echo "[entrypoint] migrate"
  python manage.py migrate --noinput
fi

if [ "${COLLECTSTATIC:-1}" = "1" ]; then
  echo "[entrypoint] collectstatic"
  python manage.py collectstatic --noinput
fi

# ---- Run the command (PID 1, receives the container's signals) ----
exec "$@"