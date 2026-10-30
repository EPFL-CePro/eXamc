# =========================
# 1. BASE — shared deps install (cached layer, only invalidated when lockfile changes)
# =========================
FROM dhi.io/node:24.22.2-dev AS base

# Corepack keeps the pnpm binary in a shared location (not root's home),
# so the non-root user of the dev stage can run it too
ENV COREPACK_HOME=/opt/corepack

WORKDIR /app/frontend

COPY app/package.json app/pnpm-lock.yaml app/pnpm-workspace.yaml ./

# Install the pnpm version mentioned in package.json
RUN corepack enable \
    && corepack prepare --activate "$(node -p "require('./package.json').packageManager")" \
    && chmod -R a+rX "$COREPACK_HOME"

RUN pnpm install --frozen-lockfile


# =========================
# 2. DEV — Vite dev server, as the dev user (UID/GID of your host user)
# =========================
FROM base AS dev

ARG UID=1000
ARG GID=1000

RUN (getent group "${GID}" || groupadd --gid "${GID}" examc) \
    && (getent passwd "${UID}" || useradd --uid "${UID}" --gid "${GID}" --create-home --shell /bin/bash examc) \
    && chown -R "${UID}:${GID}" /app/frontend

USER ${UID}:${GID}

EXPOSE 5173

CMD ["pnpm", "run", "dev", "--host"]


# =========================
# 3. BUILD — production build, reusing base's already-installed node_modules
# =========================
FROM base AS build

COPY app/ /app/frontend

RUN pnpm run build


# =========================
# 4. ARTIFACT — small deploy image: copies the built output into the static volume
# (deploy-static.sh needs a shell, hence the -dev variant)
# Build staging/prod with --build-arg UID=1500 --build-arg GID=1500 (the host's examc user).
# =========================
FROM dhi.io/alpine-base:3.24-dev AS artifact

ARG UID=1000
ARG GID=1000

RUN mkdir -p /static && chown "${UID}:${GID}" /static

VOLUME /static

COPY --from=build --chown=${UID}:${GID} /app/frontend/dist/vite /vite
COPY --chmod=0755 ./deploy-static.sh /deploy-static.sh

USER ${UID}:${GID}

ENTRYPOINT ["/deploy-static.sh"]
