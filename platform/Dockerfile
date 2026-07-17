FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS build
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
WORKDIR /build/platform
COPY mcp-db-connector /build/mcp-db-connector
COPY platform/pyproject.toml platform/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY platform ./
RUN uv sync --frozen --no-dev

FROM python:3.12-slim-bookworm AS runtime
ENV PATH=/app/.venv/bin:$PATH PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
RUN groupadd --system --gid 10001 brp && useradd --system --uid 10001 --gid brp --home /app brp
WORKDIR /app
COPY --from=build --chown=brp:brp /build/platform /app
RUN mkdir -p /app/output/artifacts && chown -R brp:brp /app/output
USER 10001:10001
EXPOSE 8100
HEALTHCHECK --interval=20s --timeout=3s --start-period=20s --retries=3 CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8100/health/live', timeout=2)"]
CMD ["sh", "-c", "python -m brp.migrate && exec uvicorn brp.api.app:app --host 0.0.0.0 --port 8100 --proxy-headers"]
