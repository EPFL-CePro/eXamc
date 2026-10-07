# Base Docker images
ARG PYTHON_IMAGE="python:3.12-slim-bookworm"
FROM ghcr.io/astral-sh/uv:0.12 AS uv


# =========================
# UV BASE: uv, build deps and lockfile, shared by both builders
# =========================
FROM ${PYTHON_IMAGE} AS uv-base

COPY --from=uv /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_NO_CACHE=1

WORKDIR /app

# Build deps: mysqlclient is compiled from source for both venvs
COPY ./install-build-deps.sh /opt/install-build-deps.sh
RUN /opt/install-build-deps.sh

COPY app/pyproject.toml app/uv.lock ./


# =========================
# BUILDER: production venv + docs
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
# BUILDER-TOOLING: dev/test venv (all groups)
# =========================
FROM uv-base AS builder-tooling

ENV UV_PROJECT_ENVIRONMENT=/opt/venv-tooling

RUN uv sync --frozen --group test --group docs --group dev --no-install-project


# =========================
# RUNTIME BASE: system packages, the app user and its data dirs (no app code)
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
        texlive-xetex \
        texlive-latex-recommended \
        texlive-latex-extra \
        texlive-fonts-recommended \
        texlive-fonts-extra \
        lmodern \
        texlive-lang-european \
        latexmk \
        ghostscript \
        poppler-utils \
        pandoc; \
    test -x /usr/bin/auto-multiple-choice; \
    test -x /usr/bin/pandoc; \
    rm -rf /var/lib/apt/lists/*

# Root owns the code, examc owns the data.
# The data dirs exist in the image so new named volumes start owned by examc
# (bind mounts keep the host's ownership: chown them to UID:GID on the host).
RUN groupadd --gid ${GID} examc \
    && useradd --uid ${UID} --gid ${GID} --create-home --shell /bin/bash examc \
    && mkdir -p /static /media /private_media \
    && chown examc:examc /static /media /private_media


# =========================
# PRODUCTION: code and venv owned by root, read-only for examc
# =========================
FROM runtime-base AS production

COPY entrypoint.sh /opt/entrypoint.sh
RUN chmod +x /opt/entrypoint.sh && sed -i 's/\r$//' /opt/entrypoint.sh

ENV PATH="/opt/venv-prod/bin:$PATH"

VOLUME /static

COPY --from=builder /opt/venv-prod /opt/venv-prod
COPY --exclude=app/docs ./app /app
COPY --from=builder /app/examc_app/static/docs /app/examc_app/static/docs

USER examc

# Entrypoint: migrations, collectstatic, then execute CMD
ENTRYPOINT ["/opt/entrypoint.sh"]


# =========================
# TOOLING (dev and test; CI runs the tests in it): everything owned by examc
# =========================
FROM runtime-base AS tooling

ENV PATH="/opt/venv-tooling/bin:$PATH" \
    UV_PROJECT_ENVIRONMENT=/opt/venv-tooling

RUN chown examc:examc /app

COPY --from=uv-base /bin/uv /bin/uvx /bin/
COPY ./sphinx-autobuild.py /opt/sphinx-autobuild.py
COPY --from=builder-tooling --chown=examc:examc /opt/venv-tooling /opt/venv-tooling

USER examc

COPY --chown=examc:examc --exclude=app/docs ./app /app


# =========================
# DEV (same as tooling, with build deps installed
# =========================
FROM runtime-base AS dev

COPY --from=uv-base /opt/install-build-deps.sh /opt/
RUN /opt/install-build-deps.sh