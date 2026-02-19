# api/app/middleware/auth.py
"""
Optional middleware for request-level auth logging.
The core auth is handled in dependencies.py via Depends().
"""
from __future__ import annotations

import logging
import time

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        t0 = time.monotonic()
        response = await call_next(request)
        elapsed = (time.monotonic() - t0) * 1000
        logger.info(
            "%s %s → %d (%.0fms)",
            request.method, request.url.path, response.status_code, elapsed,
        )
        return response
