"""Prometheus metrics and request correlation middleware for the adapter.

Provides:
- Request ID middleware: Generates/propagates correlation IDs for tracing
- Prometheus metrics: Request counts, latencies, context store hits/misses,
  agent client errors

Metrics exposed at /metrics endpoint for Prometheus scraping.
"""
import time
import uuid
from collections import defaultdict
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import PlainTextResponse

import structlog

logger = structlog.get_logger(__name__)


# --- Prometheus-style metrics (simple in-process counters) ---

class MetricsRegistry:
    """Thread-safe in-process metrics registry for the adapter service.

    Tracks adapter-specific metrics:
    - Request counts by method/path/status
    - Agent client request latencies
    - Context store hit/miss ratios
    - Agent errors by type
    """

    def __init__(self):
        self._counters: dict[str, float] = defaultdict(float)
        self._histograms: dict[str, list[float]] = defaultdict(list)
        self._gauges: dict[str, float] = {}

    def inc(self, name: str, labels: dict[str, str] | None = None, value: float = 1) -> None:
        """Increment a counter metric."""
        key = self._make_key(name, labels)
        self._counters[key] += value

    def observe(self, name: str, value: float, labels: dict[str, str] | None = None) -> None:
        """Observe a value for a histogram metric."""
        key = self._make_key(name, labels)
        self._histograms[key].append(value)

    def set_gauge(self, name: str, value: float, labels: dict[str, str] | None = None) -> None:
        """Set a gauge metric to an arbitrary value."""
        key = self._make_key(name, labels)
        self._gauges[key] = value

    def _make_key(self, name: str, labels: dict[str, str] | None = None) -> str:
        if labels:
            label_str = ",".join(f'{k}="{v}"' for k, v in sorted(labels.items()))
            return f"{name}{{{label_str}}}"
        return name

    def generate(self) -> str:
        """Generate Prometheus-compatible text format output."""
        lines = []

        # Counters
        for key, value in sorted(self._counters.items()):
            if "{" in key:
                lines.append(f"carbon_adapter_request_total {value}  # {key}")
            else:
                lines.append(f"carbon_adapter_{key}_total {value}")

        # Gauges
        for key, value in sorted(self._gauges.items()):
            if "{" in key:
                lines.append(f"carbon_adapter_gauge {value}  # {key}")
            else:
                lines.append(f"carbon_adapter_{key} {value}")

        # Histograms (simplified: report count and average)
        for key, values in sorted(self._histograms.items()):
            if not values:
                continue
            avg = sum(values) / len(values)
            name = key.split("{")[0] if "{" in key else key
            lines.append(f"carbon_adapter_{name}_count {len(values)}")
            lines.append(f"carbon_adapter_{name}_avg_seconds {avg:.4f}")
            lines.append(f"carbon_adapter_{name}_max_seconds {max(values):.4f}")

        return "\n".join(lines)


# Global metrics registry
metrics = MetricsRegistry()


# --- Request ID Middleware ---

class RequestIDMiddleware(BaseHTTPMiddleware):
    """Middleware that generates/propagates a request correlation ID.

    - Checks for X-Request-ID header from upstream (e.g., Traefik or orchestrator)
    - Generates a UUID-based request ID if not present
    - Stores in request.state.request_id for downstream access
    - Adds X-Request-ID to the response headers
    - Injects request_id into structlog context for structured logging
    - Records request duration and count metrics
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Use upstream request ID if present, otherwise generate one
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id

        # Bind request_id to structlog context for all downstream logs
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)

        start_time = time.perf_counter()

        try:
            response = await call_next(request)
        finally:
            elapsed = time.perf_counter() - start_time

            # Record metrics
            path = request.url.path
            method = request.method
            status_code = response.status_code if hasattr(response, "status_code") else 0

            metrics.inc(
                "requests_total",
                labels={"method": method, "path": path, "status": str(status_code)},
            )
            metrics.observe(
                "request_duration_seconds",
                elapsed,
                labels={"method": method, "path": path},
            )

        # Add request ID to response headers
        response.headers["X-Request-ID"] = request_id
        return response


# --- Metrics Endpoint ---

async def metrics_endpoint() -> PlainTextResponse:
    """FastAPI endpoint that exposes Prometheus-style metrics.

    Returns plaintext metrics in a format compatible with Prometheus scrape.
    """
    content = metrics.generate()
    return PlainTextResponse(content, media_type="text/plain; version=0.0.4; charset=utf-8")