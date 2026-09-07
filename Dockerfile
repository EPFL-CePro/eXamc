# =========================
# Stage 1 — BUILDER
# =========================
FROM python:3.12-slim-bookworm AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_NO_CACHE=1 \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    pkg-config \
    libmariadb-dev-compat \
    libmariadb-dev \
 && rm -rf /var/lib/apt/lists/*

COPY app/pyproject.toml app/uv.lock ./

RUN uv sync --frozen \
    --no-dev --group docs \
    --no-install-project

COPY app/ .

RUN sphinx-build -M html docs/source examc_app/static/docs

RUN uv sync --frozen \
    --no-dev \
    --no-install-project


# =========================
# TEST BUILDER
# =========================
FROM builder AS test-builder

RUN uv sync --frozen \
    --group test \
    --no-install-project


# =========================
# PRODUCTION
# =========================
FROM python:3.12-slim-bookworm AS production

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /app

# Runtime dependencies only (NO compiler/toolchain):
# - libmariadb3: MariaDB client library written in C, used by mysqlclient
# - libzbar0: barcode scanning support
# - tzdata/ca-certificates: correct timezone and TLS support
RUN apt-get update && apt-get install -y --no-install-recommends \
    libmariadb3 \
    libzbar0 \
    tzdata \
    ca-certificates \
    curl \
    gnupg \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    fonts-dejavu-core \
    fonts-liberation \
    fonts-noto-core \
 && rm -rf /var/lib/apt/lists/*


# --- Auto Multiple Choice (AMC) from OBS (Debian) ---
# Install the required Debian packages for Auto Multiple Choice.
RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
      auto-multiple-choice \
      texlive-xetex \
      texlive-latex-recommended \
      texlive-latex-extra \
      texlive-fonts-recommended \
      texlive-fonts-extra \
      lmodern \
      texlive-lang-european \
      fonts-noto-core \
      latexmk \
      ghostscript \
      poppler-utils \
 && test -x /usr/bin/auto-multiple-choice \
 && rm -rf /var/lib/apt/lists/*

COPY --from=builder /opt/venv /opt/venv
COPY ./app/ /app/

# Patch runsslserver.
# Enable it at build time with: --build-arg APPLY_SSL_PATCH=1
ARG APPLY_SSL_PATCH=0
RUN if [ "$APPLY_SSL_PATCH" = "1" ]; then \
      target="/opt/venv/lib/python3.12/site-packages/sslserver/management/commands/runsslserver.py"; \
      if [ -f "$target" ] && [ -f "/app/docker/sslserver/management/commands/runsslserver.py" ]; then \
        cp /app/docker/sslserver/management/commands/runsslserver.py "$target"; \
      fi; \
    fi


# =========================
# TEST
# =========================
FROM production AS test

COPY --from=builder /bin/uv /bin/uvx /bin/
COPY --from=test-builder /opt/venv /opt/venv

CMD ["uv", "run", "pytest"]