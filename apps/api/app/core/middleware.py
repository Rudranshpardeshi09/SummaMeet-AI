"""Request ID middleware — adds X-Request-Id header to all responses for tracing."""

from __future__ import annotations

import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

import structlog


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Adds a unique X-Request-Id to every request/response for log correlation."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        request_id = request.headers.get("X-Request-Id", str(uuid.uuid4()))

        # Bind request_id to structlog context for all downstream logging
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)

        response = await call_next(request)
        response.headers["X-Request-Id"] = request_id

        return response
