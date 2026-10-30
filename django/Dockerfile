# Base image: hardened uv on Debian 13, without the app's Python.
# The app's Python is installed by uv (version from requires-python in pyproject.toml),
# separately from the system's python3 that some apt packages pull in.
# The two never replace each other. -dev variant: shell + apt for the RUN steps below.
FROM dhi.io/uv:0.13.6-debian13-dev AS base


# =========================
# UV BASE: uv, build deps and lockfile, shared by both builders
# =========================
FROM base AS uv-base

# Python goes to /opt/uv-python (copied as is into the final images, so the venvs'
# interpreter link stays valid). only-managed: never use a system python3.
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_NO_CACHE=1 \
    UV_PYTHON_INSTALL_DIR=/opt/uv-python \
    UV_PYTHON_PREFERENCE=only-managed

WORKDIR /app

# ca-certificates: uv downloads Python and packages over HTTPS
RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends ca-certificates; \
    rm -rf /var/lib/apt/lists/*

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
# (the first sync installs the Python required by pyproject.toml)
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
# RUNTIME BASE: system packages, the app user and its data dirs (no app code, no app Python)
# =========================
FROM base AS runtime-base

# The uv base image runs `uv` by default: clear it, so containers run
# exactly the command they're given (Compose `command:`, `docker run ...`)
ENTRYPOINT []
CMD []

ARG UID=1000
ARG GID=1000

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# cm-super: Type 1 (vector) versions of the EC fonts used by the exams (fontenc T1). Only recommended by
# texlive-fonts-extra, so not installed with --no-install-recommends: pdflatex then generated bitmap fonts
# with METAFONT at each worker start.
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
        cm-super \
        lmodern \
        texlive-lang-european \
        texlive-lang-french \
        latexmk \
        ghostscript \
        poppler-utils \
        pandoc; \
    test -x /usr/bin/auto-multiple-choice; \
    test -x /usr/bin/pandoc; \
    ldconfig; \
    rm -rf /var/lib/apt/lists/*

# Root owns the code, examc owns the data.
# The data dirs exist in the image so new named volumes start owned by examc
# (bind mounts keep the host's ownership: chown them to UID:GID on the host).
RUN groupadd --gid ${GID} examc \
    && useradd --uid ${UID} --gid ${GID} --create-home --shell /bin/bash examc \
    && mkdir -p /static /media /private_media \
    && chown -R examc:examc /static /media /private_media


# =========================
# PRODUCTION: code, venv and Python owned by root, read-only for examc
# =========================
FROM runtime-base AS production

COPY --chmod=0755 entrypoint.sh /opt/entrypoint.sh
RUN sed -i 's/\r$//' /opt/entrypoint.sh

ENV PATH="/opt/venv-prod/bin:$PATH"

VOLUME /static

COPY --from=builder /opt/uv-python /opt/uv-python
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

# Same uv settings as the builders, so `uv` run inside dev containers keeps
# using /opt/uv-python and never the system's python3
ENV PATH="/opt/venv-tooling/bin:$PATH" \
    UV_PROJECT_ENVIRONMENT=/opt/venv-tooling \
    UV_PYTHON_INSTALL_DIR=/opt/uv-python \
    UV_PYTHON_PREFERENCE=only-managed \
    SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt

RUN chown -R examc:examc /app

COPY ./sphinx-autobuild.py /opt/sphinx-autobuild.py
COPY --from=builder-tooling /opt/uv-python /opt/uv-python
COPY --from=builder-tooling --chown=examc:examc /opt/venv-tooling /opt/venv-tooling

USER examc

COPY --chown=examc:examc --exclude=app/docs ./app /app


# =========================
# DEV: same as tooling, with build deps installed (to add packages with uv)
# =========================
FROM tooling AS dev

# Install build deps, then revert to examc user
USER root
COPY --from=uv-base /opt/install-build-deps.sh /opt/
RUN /opt/install-build-deps.sh
USER examc
