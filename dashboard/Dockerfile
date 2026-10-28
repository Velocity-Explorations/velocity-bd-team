# The dashboard as one container (PRO-511). Build from the repo root:
#   docker build -t velocity-bd-dashboard dashboard
# Every setting (DATABASE_URL, DASHBOARD_USERS, DASHBOARD_IAP_AUDIENCE and the rest in
# README.md) comes from the environment when it runs. .dockerignore keeps .env files out.

FROM node:24.19.0-alpine AS deps
WORKDIR /app
RUN apk add --no-cache libc6-compat
COPY package.json package-lock.json ./
RUN npm ci

FROM node:24.19.0-alpine AS build
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

FROM node:24.19.0-alpine AS run
WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 PORT=8080 HOSTNAME=0.0.0.0
COPY --from=build --chown=node:node /app/.next/standalone ./
COPY --from=build --chown=node:node /app/.next/static ./.next/static
COPY --from=build --chown=node:node /app/public ./public
USER node
EXPOSE 8080
CMD ["node", "server.js"]
