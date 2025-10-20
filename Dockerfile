# =========================
# Stage 1 — BUILDER
# =========================
FROM python:3.12-slim AS builder

ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app

# Déps de build pour mysqlclient (lié à libmariadb), et pkg-config
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential pkg-config libmariadb-dev-compat libmariadb-dev \
 && rm -rf /var/lib/apt/lists/*

# Installe les deps Python dans un prefix isolé (/install) pour les copier ensuite
COPY requirements.txt /app/
RUN python -m pip install --upgrade pip \
 && pip install --prefix=/install -r requirements.txt \
 && pip install --prefix=/install gunicorn
# ↑ garde gunicorn si pas déjà dans requirements.txt


# =========================
# Stage 2 — RUNTIME (léger)
# =========================
FROM python:3.12-slim

# Réglages Python “prod”
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Déps runtime uniquement (PAS de toolchain) :
# - libmariadb3 : client C MariaDB (mysqlclient s’y lie)
# - libzbar0    : tu l’avais dans ton Dockerfile (ex. lecture code-barres)
# - tzdata/ca-certificates : TLS & timezone corrects
RUN apt-get update && apt-get install -y --no-install-recommends \
    libmariadb3 libzbar0 tzdata ca-certificates curl \
 && rm -rf /var/lib/apt/lists/*

# Copie des libs Python construites au stage "builder"
COPY --from=builder /install /usr/local

# Copie de ton code
COPY . /app

#Patch du runsslserver .
# Active-le en build si tu le veux :  --build-arg APPLY_SSL_PATCH=1
ARG APPLY_SSL_PATCH=0
RUN if [ "$APPLY_SSL_PATCH" = "1" ]; then \
      target="/usr/local/lib/python3.12/site-packages/sslserver/management/commands/runsslserver.py"; \
      if [ -f "$target" ] && [ -f "/app/docker/sslserver/management/commands/runsslserver.py" ]; then \
        cp /app/docker/sslserver/management/commands/runsslserver.py "$target"; \
      fi; \
    fi

# User non-root
RUN groupadd -g 1000 app && useradd -m -u 1000 -g 1000 app
USER app

# Gunicorn conf
ENV GUNICORN_CMD_ARGS="--config deploy/gunicorn.conf.py"

# Entrypoint : migrations, collectstatic, puis exécute la CMD
ENTRYPOINT ["./deploy/entrypoint.sh"]
