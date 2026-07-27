FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS build
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
WORKDIR /build/platform
COPY mcp-db-connector /build/mcp-db-connector
COPY platform/pyproject.toml platform/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY platform ./
RUN uv sync --frozen --no-dev --no-editable

FROM python:3.12-slim-bookworm AS runtime
ENV PATH=/app/.venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64 \
    GRADLE_USER_HOME=/tmp/.gradle
ARG GH_VERSION=2.93.0
ARG GH_AMD64_SHA256=5371f77155e5dd81b6e897c379431f734949b99b99ae1f01c5e3ab6d3795cf4d
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates curl git openjdk-17-jdk-headless openssh-client \
    && curl --fail --location --silent --show-error \
        "https://github.com/cli/cli/releases/download/v${GH_VERSION}/gh_${GH_VERSION}_linux_amd64.deb" \
        --output /tmp/gh.deb \
    && echo "${GH_AMD64_SHA256}  /tmp/gh.deb" | sha256sum --check - \
    && apt-get install -y --no-install-recommends /tmp/gh.deb \
    && rm -f /tmp/gh.deb \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system --gid 10001 brp \
    && useradd --system --uid 10001 --gid brp --home /app brp
WORKDIR /app
COPY --from=build --chown=brp:brp /build/platform /app
COPY --chown=brp:brp java-toolchain /app/java-toolchain
RUN mkdir -p /app/output/artifacts && chown -R brp:brp /app/output
USER 10001:10001
EXPOSE 8100
HEALTHCHECK --interval=20s --timeout=3s --start-period=20s --retries=3 CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8100/health/live', timeout=2)"]
CMD ["uvicorn", "brp.api.app:app", "--host", "0.0.0.0", "--port", "8100", "--proxy-headers"]
