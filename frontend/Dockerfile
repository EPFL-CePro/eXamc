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

USER node
EXPOSE 5173
CMD ["pnpm", "run", "dev"]


# =========================
# 3. BUILD — production build, reusing base's already-installed node_modules
# =========================
FROM base AS build

COPY app/ /app/frontend
RUN pnpm run build   # <-- no reinstall needed, node_modules already present from base


# =========================
# 4. ARTIFACT — lightweight deploy image, just the built output
# =========================
FROM alpine:3 AS artifact

COPY --from=build /app/frontend/dist/vite /vite
COPY ./deploy-static.sh /deploy-static.sh
RUN chmod +x /deploy-static.sh

ENTRYPOINT ["/deploy-static.sh"]