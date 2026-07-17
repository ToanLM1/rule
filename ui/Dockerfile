FROM node:22-alpine AS build
RUN corepack enable
WORKDIR /app
COPY ui/package.json ui/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile
COPY ui ./
ARG VITE_BRP_API_BASE_URL=
ENV VITE_BRP_API_BASE_URL=$VITE_BRP_API_BASE_URL
RUN pnpm build

FROM nginxinc/nginx-unprivileged:1.29-alpine
COPY ui/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
USER 101:101
EXPOSE 8080
HEALTHCHECK --interval=20s --timeout=3s --start-period=5s --retries=3 CMD ["wget", "-qO-", "http://127.0.0.1:8080/healthz"]
