"""Request logging and correlation ID middleware for FastAPI.

Provides:
- Request correlation ID generation/validation
- Structured HTTP request/response logging
- Request duration tracking
- Sensitive data sanitization
"""

import re
import time
import uuid
from typing import Optional

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.core.config import settings
from app.core.logging_config import (
    get_logger,
    get_request_id,
    set_request_id,
    clear_request_id,
    RequestContextFilter,
)


# Valid characters for request ID: alphanumeric, hyphen, underscore
REQUEST_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")


def generate_request_id() -> str:
    """Generate a new UUID request ID."""
    return str(uuid.uuid4())


def validate_request_id(request_id: str) -> bool:
    """Validate incoming request ID format.

    Args:
        request_id: Request ID string to validate.

    Returns:
        True if valid, False otherwise.
    """
    return bool(REQUEST_ID_PATTERN.match(request_id))


def sanitize_path(path: str) -> str:
    """Sanitize URL path by removing query parameters.

    Args:
        path: Full URL path with potential query string.

    Returns:
        Path without query string.
    """
    return path.split("?")[0] if "?" in path else path


def sanitize_headers(headers: dict) -> dict:
    """Remove sensitive headers from logging.

    Args:
        headers: Raw headers dictionary.

    Returns:
        Sanitized headers dictionary.
    """
    sensitive_headers = {
        "authorization",
        "cookie",
        "x-api-key",
        "x-auth-token",
        "proxy-authorization",
        "set-cookie",
    }
    return {
        k: v for k, v in headers.items()
        if k.lower() not in sensitive_headers
    }


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for structured HTTP request/response logging with correlation IDs."""

    def __init__(
        self,
        app: ASGIApp,
        *,
        log_requests: bool = True,
        log_responses: bool = True,
        excluded_paths: Optional[set[str]] = None,
    ):
        """Initialize request logging middleware.

        Args:
            app: ASGI application.
            log_requests: Whether to log incoming requests.
            log_responses: Whether to log responses.
            excluded_paths: Set of paths to exclude from logging (e.g., docs).
        """
        super().__init__(app)
        self.logger = get_logger("app.requests")
        self.log_requests = log_requests
        self.log_responses = log_responses
        self.excluded_paths = excluded_paths or {"/docs", "/redoc", "/openapi.json"}

    async def dispatch(self, request: Request, call_next):
        """Process request and log structured information."""
        # Skip logging for excluded paths
        if request.url.path in self.excluded_paths:
            return await call_next(request)

        # Extract or generate request ID
        incoming_request_id = request.headers.get("X-Request-ID")
        if incoming_request_id and validate_request_id(incoming_request_id):
            request_id = incoming_request_id
        else:
            request_id = generate_request_id()

        # Set request ID in context for this request
        set_request_id(request_id)

        # Add request ID to request state for access in route handlers
        request.state.request_id = request_id

        # Prepare request log data
        start_time = time.perf_counter()
        sanitized_path = sanitize_path(str(request.url))

        # Log incoming request
        if self.log_requests:
            extra = {
                "request_id": request_id,
                "method": request.method,
                "path": sanitized_path,
            }
            # Only include client IP if explicitly enabled (privacy)
            if getattr(settings, "LOG_CLIENT_IP", False):
                extra["client_host"] = request.client.host if request.client else None
            self.logger.info("HTTP request received", extra=extra)

        # Process request
        try:
            response = await call_next(request)
        except Exception as exc:
            # Log unhandled exception with request context
            duration_ms = (time.perf_counter() - start_time) * 1000
            self.logger.exception(
                "Unhandled exception during request processing",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": sanitized_path,
                    "duration_ms": round(duration_ms, 2),
                    "exception_type": type(exc).__name__,
                },
            )
            # Clear request ID before re-raising
            clear_request_id()
            raise

        # Calculate duration
        duration_ms = (time.perf_counter() - start_time) * 1000

        # Add request ID to response headers
        response.headers["X-Request-ID"] = request_id

        # Log response
        if self.log_responses:
            self.logger.info(
                "HTTP response sent",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": sanitized_path,
                    "status_code": response.status_code,
                    "duration_ms": round(duration_ms, 2),
                },
            )

        # Clear request ID context
        clear_request_id()

        return response