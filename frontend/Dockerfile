# =========================
# 1. BASE — shared deps install (cached layer, only invalidated when lockfile changes)
# =========================
FROM node:24-slim AS base

RUN corepack enable

WORKDIR /app/frontend

COPY app/package.json app/pnpm-lock.yaml app/pnpm-workspace.yaml ./

# Install the PNPM version mentionned in package.json
RUN corepack prepare --activate $(node -p "require('./package.json').packageManager")

RUN pnpm install --frozen-lockfile


# =========================
# 2. DEV — Vite dev server
# =========================
FROM base AS dev

EXPOSE 5173

CMD ["pnpm", "run", "dev", "--host"]


# =========================
# 3. BUILD — production build, reusing base's already-installed node_modules
# =========================
FROM base AS build

COPY app/ /app/frontend

RUN pnpm run build


# =========================
# 4. ARTIFACT — lightweight deploy image, just the built output
# =========================
FROM alpine:3 AS artifact

ARG UID=1000
ARG GID=1000

RUN mkdir -p /static && chown ${UID}:${GID} /static

VOLUME /static

COPY --from=build --chown=${UID}:${GID} /app/frontend/dist/vite /vite
COPY ./deploy-static.sh /deploy-static.sh
RUN chmod +x /deploy-static.sh

USER ${UID}:${GID}

ENTRYPOINT ["/deploy-static.sh"]