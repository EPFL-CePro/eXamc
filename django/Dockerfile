# Base image: hardened uv on Debian 13, without the app's Python.
# The app's Python is installed by uv (version from requires-python in pyproject.toml),
# separately from the system's python3 that some apt packages pull in.
# The two never replace each other. -dev variant: shell + apt for the RUN steps below.
FROM dhi.io/uv:0.13.7-debian13-dev AS base


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

# TeX Live isn't in this image: Compose's texlive service copies it from the official TeX Live
# image into the texlive volume, mounted at /opt/texlive (see compose.base.yml). Its binaries for
# either architecture go on the PATH, and TEXMFAUXTREES adds the TeX trees installed by apt
# packages (auto-multiple-choice's automultiplechoice.sty in /usr/share/texmf).
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt \
    PATH="/opt/texlive/bin/x86_64-linux:/opt/texlive/bin/aarch64-linux:$PATH" \
    TEXMFAUXTREES="/usr/share/texmf,"

WORKDIR /app

# System libraries and tools only: TeX Live (incl. latexmk, cm-super, lmodern) comes from the
# TeX Live image. auto-multiple-choice depends on Debian's texlive-* packages:
# texlive-local (an empty package built from texlive-local.ctl) "provides" them, so apt
# doesn't pull them in.
COPY texlive-local.ctl /tmp/texlive-local/DEBIAN/control
RUN set -eux; \
    dpkg-deb --build --root-owner-group /tmp/texlive-local /tmp/texlive-local.deb; \
    dpkg -i /tmp/texlive-local.deb; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
        libmariadb3 libzbar0 tzdata ca-certificates curl gnupg \
        libgl1 libglib2.0-0 libsm6 libxext6 mariadb-client \
        fonts-dejavu-core fonts-liberation fonts-noto-core \
        auto-multiple-choice \
        ghostscript \
        poppler-utils \
        pandoc; \
    update-mime-database /usr/share/mime; \
      test -s /usr/share/mime/globs2; \
    test -x /usr/bin/auto-multiple-choice; \
    test -x /usr/bin/pandoc; \
    if dpkg-query -W -f='${Package} ${Status}\n' 'texlive-*' 2>/dev/null \
        | grep -v '^texlive-local ' | grep -q ' installed$'; then \
        echo "Debian TeX Live got installed: add the missing package to texlive-local.ctl" >&2; exit 1; \
    fi; \
    ldconfig; \
    rm -rf /var/lib/apt/lists/* /tmp/texlive-local /tmp/texlive-local.deb

# TeX Live's fonts (OpenType, TrueType) for fontconfig, so tools outside TeX (pango in AMC's
# annotations, XeTeX's lookups by font name) find them too
COPY texlive-fonts.conf /etc/fonts/conf.d/09-texlive-fonts.conf

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
    UV_PYTHON_PREFERENCE=only-managed

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