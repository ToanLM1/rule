"""HTTP correlation and Prometheus instrumentation."""

from __future__ import annotations

import json
import logging
import re
import time
from uuid import uuid4

from fastapi import Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

REQUEST_COUNT = Counter("brp_http_requests_total", "HTTP requests", ("method", "route", "status"))
REQUEST_DURATION = Histogram(
    "brp_http_request_duration_seconds", "HTTP request duration", ("method", "route")
)
LOGGER = logging.getLogger("brp.http")
SECRET_PATTERNS = (
    re.compile(r"(?i)(password|token|secret|api[_-]?key)(\s*[=:]\s*)[^\s,;]+"),
    re.compile(r"(postgres(?:ql)?(?:\+psycopg)?://[^:/\s]+:)[^@\s]+(@)"),
)


def configure_json_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")


def redact(value: str) -> str:
    result = value
    for pattern in SECRET_PATTERNS:
        result = pattern.sub(lambda match: f"{match.group(1)}[REDACTED]{match.group(2)}", result)
    return result


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        correlation_id = request.headers.get("X-Request-ID") or str(uuid4())
        request.state.correlation_id = correlation_id
        started = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
        except Exception:
            LOGGER.exception(
                json.dumps(
                    {
                        "event": "http.request.failed",
                        "correlationId": correlation_id,
                        "method": request.method,
                        "path": request.url.path,
                    },
                    separators=(",", ":"),
                )
            )
            raise
        route = request.scope.get("route")
        route_path = getattr(route, "path", request.url.path)
        duration = time.perf_counter() - started
        REQUEST_COUNT.labels(request.method, route_path, str(status)).inc()
        REQUEST_DURATION.labels(request.method, route_path).observe(duration)
        LOGGER.info(
            json.dumps(
                {
                    "event": "http.request",
                    "correlationId": correlation_id,
                    "method": request.method,
                    "route": route_path,
                    "status": status,
                    "durationMs": round(duration * 1000, 3),
                },
                separators=(",", ":"),
            )
        )
        response.headers["X-Request-ID"] = correlation_id
        return response


def metrics_response() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
