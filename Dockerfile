# =========================
# Stage 1 — BUILDER
# =========================
FROM python:3.12-slim-bookworm AS builder

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_NO_CACHE=1 \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /app

# Build dependencies for mysqlclient (linked against libmariadb), and pkg-config
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    pkg-config \
    libmariadb-dev-compat \
    libmariadb-dev \
 && rm -rf /var/lib/apt/lists/*

# Copy project metadata and lockfile first to maximize Docker layer caching
COPY app/pyproject.toml app/uv.lock ./

# Install both production and docs generation dependencies into the virtual environment.
# --frozen ensures that uv.lock is used exactly as-is.
# --no-install-project skips installing the project itself at this stage.
RUN uv sync --frozen \
    --no-dev --group docs \
    --no-install-project

# Copy the application source
COPY app/ .

# Build bundled Sphinx documentation from tracked sources before collectstatic.
RUN sphinx-build -M html docs/source examc_app/static/docs


# Removes the unnecessary dependencies
RUN uv sync --frozen \
    --no-dev \
    --no-install-project


# =========================
# Stage 2 — RUNTIME
# =========================
FROM python:3.12-slim-bookworm

# Python production settings
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
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


# Copy the Python virtual environment built in the builder stage
COPY --from=builder /opt/venv /opt/venv

# Copy the application source
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


# Create a non-root application user
RUN groupadd -g 1000 app && useradd -m -u 1000 -g 1000 app

# Gunicorn configuration
ENV GUNICORN_CMD_ARGS="--config gunicorn.conf.py"

# Entrypoint: run migrations, collect static files, then execute CMD
ENTRYPOINT ["/app/entrypoint.sh"]
