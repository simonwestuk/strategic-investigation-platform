# syntax=docker/dockerfile:1
#
# Web image: Next.js app built with `output: "standalone"` (next.config must set it).
#   docker build -t sip-web --build-arg NEXT_PUBLIC_API_BASE_URL=http://localhost:8000 apps/web
# NEXT_PUBLIC_* values are inlined into the client bundle at build time, so the API URL is a build arg,
# not a runtime setting. Rebuild the image to point it at a different API.

ARG NODE_VERSION=22

# ---- deps: install exactly what the lockfile pins ------------------------------------------
FROM node:${NODE_VERSION}-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund

# ---- build ---------------------------------------------------------------------------------
FROM node:${NODE_VERSION}-alpine AS build
WORKDIR /app
ARG NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_BASE_URL=${NEXT_PUBLIC_API_BASE_URL} \
    NEXT_TELEMETRY_DISABLED=1 \
    NODE_ENV=production
COPY --from=deps /app/node_modules ./node_modules
COPY . .
# `public/` is optional in a Next.js app; make sure it exists so the runtime COPY below never fails.
RUN mkdir -p public && npm run build

# ---- runtime: only the standalone server, static assets and public files ------------------
FROM node:${NODE_VERSION}-alpine AS runtime
WORKDIR /app
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0
# The official image ships an unprivileged `node` user (uid/gid 1000); run as it numerically.
COPY --from=build --chown=node:node /app/.next/standalone ./
COPY --from=build --chown=node:node /app/.next/static ./.next/static
COPY --from=build --chown=node:node /app/public ./public
USER 1000:1000
EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD ["wget", "-q", "-O", "/dev/null", "http://127.0.0.1:3000/"]

CMD ["node", "server.js"]
