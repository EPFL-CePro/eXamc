# Base Docker images
ARG PYTHON_IMAGE="python:3.12-slim-bookworm"
FROM ghcr.io/astral-sh/uv:0.12 AS uv


# =========================
# UV BASE: uv + lockfile, shared by both builders
# =========================
FROM ${PYTHON_IMAGE} AS uv-base

# Pin uv: "latest" would invalidate the builders on every uv release
COPY --from=uv /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_NO_CACHE=1

WORKDIR /app

COPY app/pyproject.toml app/uv.lock ./


# =========================
# BUILDER: production venv + docs (no build deps needed)
# =========================
FROM uv-base AS builder

ENV UV_PROJECT_ENVIRONMENT=/opt/venv-prod \
    PATH="/opt/venv-prod/bin:$PATH"

# Build the docs with the docs group, then remove it from the venv
RUN uv sync --frozen --no-dev --group docs --no-install-project
COPY app/docs/ /app/docs/
RUN sphinx-build -M html docs/source examc_app/static/docs
RUN uv sync --frozen --no-dev --no-install-project


# =========================
# BUILDER-TOOLING: dev/test venv, the only one that needs compilers
# =========================
FROM uv-base AS builder-tooling

ENV UV_PROJECT_ENVIRONMENT=/opt/venv-tooling

COPY ./install-build-deps.sh /opt/install-build-deps.sh
RUN /opt/install-build-deps.sh

RUN uv sync --frozen --group test --group docs --group dev --no-install-project


# =========================
# RUNTIME BASE: system packages and the app user (no app code)
# =========================
FROM ${PYTHON_IMAGE} AS runtime-base

ARG UID=1000
ARG GID=1000

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
        libmariadb3 libzbar0 tzdata ca-certificates curl gnupg \
        libgl1 libglib2.0-0 libsm6 libxext6 mariadb-client \
        fonts-dejavu-core fonts-liberation fonts-noto-core \
        auto-multiple-choice \
        texlive-xetex texlive-latex-recommended texlive-latex-extra \
        texlive-fonts-recommended texlive-fonts-extra lmodern \
        texlive-lang-european latexmk ghostscript poppler-utils; \
    test -x /usr/bin/auto-multiple-choice; \
    rm -rf /var/lib/apt/lists/*

RUN groupadd --gid ${GID} examc \
    && useradd --uid ${UID} --gid ${GID} --create-home --shell /bin/bash examc \
    && chown examc:examc /app


# =========================
# PRODUCTION
# =========================
FROM runtime-base AS production

COPY entrypoint.sh /opt/entrypoint.sh
RUN chmod +x /opt/entrypoint.sh && sed -i 's/\r$//' /opt/entrypoint.sh

ENV PATH="/opt/venv-prod/bin:$PATH"

# Create /static owned by examc *before* declaring the volume,
# so a fresh volume starts with that ownership and collectstatic can write to it
RUN mkdir -p /static && chown examc:examc /static
VOLUME /static

COPY --from=builder --chown=examc:examc /opt/venv-prod /opt/venv-prod
COPY --chown=examc:examc --exclude=app/docs ./app /app
COPY --from=builder --chown=examc:examc /app/examc_app/static/docs /app/examc_app/static/docs

USER examc

ENTRYPOINT ["/opt/entrypoint.sh"]


# =========================
# TOOLING (dev and test; CI runs the tests in it)
# =========================
FROM runtime-base AS tooling

ENV PATH="/opt/venv-tooling/bin:$PATH" \
    UV_PROJECT_ENVIRONMENT=/opt/venv-tooling

COPY --from=uv-base /bin/uv /bin/uvx /bin/
COPY ./sphinx-autobuild.py /opt/sphinx-autobuild.py
COPY --from=builder-tooling --chown=examc:examc /opt/venv-tooling /opt/venv-tooling

USER examc

COPY --chown=examc:examc --exclude=app/docs ./app /app