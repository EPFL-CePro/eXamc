# =========================
# BUILDER
# =========================
FROM python:3.12-slim-bookworm AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_NO_CACHE=1

WORKDIR /app

# Build-time dependencies
COPY docker/scripts/install-build-deps.sh /opt/install-build-deps.sh
RUN /opt/install-build-deps.sh

COPY app/pyproject.toml app/uv.lock ./


# --- Production environment docs ---
ENV UV_PROJECT_ENVIRONMENT=/opt/venv-prod \
    PATH="/opt/venv-prod/bin:$PATH"

# Include the necessary dependencies for docs
RUN uv sync --frozen \
    --no-dev \
    --group docs \
    --no-install-project

COPY app/docs/ /app/docs/

# Generate the docs
RUN sphinx-build -M html docs/source examc_app/static/docs

RUN uv sync --frozen \
    --no-dev \
    --no-install-project


# --- Dev + test environment ---
ENV UV_PROJECT_ENVIRONMENT=/opt/venv-tooling

RUN uv sync --frozen \
    --group test \
    --group dev \
    --no-install-project


# =========================
# RUNTIME BASE, with dependencies shared by prod and test targets
# =========================
FROM python:3.12-slim-bookworm AS runtime-base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Runtime dependencies only.
RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
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
        auto-multiple-choice \
        texlive-xetex \
        texlive-latex-recommended \
        texlive-latex-extra \
        texlive-fonts-recommended \
        texlive-fonts-extra \
        lmodern \
        texlive-lang-european \
        latexmk \
        ghostscript \
        poppler-utils; \
    test -x /usr/bin/auto-multiple-choice; \
    rm -rf /var/lib/apt/lists/*

# Copy everything, except the doc source which are not needed in the prod image
COPY --exclude=app/docs ./app /app


# =========================
# PRODUCTION IMAGE
# =========================
FROM runtime-base AS production

WORKDIR /app

COPY --from=builder /opt/venv-prod /opt/venv-prod
COPY --from=builder /app /app

ENV PATH="/opt/venv-prod/bin:$PATH"


# =========================
# TOOLING IMAGE (with dev and test dependencies installed)
# =========================
FROM runtime-base AS tooling

ARG UID=1000
ARG GID=1000

ENV PATH="/opt/venv-tooling/bin:$PATH"

RUN groupadd --gid ${GID} dev \
    && useradd --uid ${UID} --gid ${GID} --no-create-home --shell /bin/bash dev

# Reinstall the build deps to be able to build depencies
COPY docker/scripts/install-build-deps.sh /opt/install-build-deps.sh
RUN /opt/install-build-deps.sh

COPY --from=builder /bin/uv /bin/uvx /bin/
COPY --from=builder --chown=$UID:$GID /opt/venv-tooling /opt/venv-tooling
COPY --from=builder --chown=$UID:$GID /app /app

