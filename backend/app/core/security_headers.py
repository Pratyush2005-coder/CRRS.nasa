"""Security headers ASGI middleware."""

from starlette.types import ASGIApp, Receive, Scope, Send
from starlette.datastructures import MutableHeaders


class SecurityHeadersMiddleware:
    """
    ASGI middleware that adds security headers to all HTTP responses.

    This middleware operates at the ASGI level, intercepting the
    `http.response.start` message to add headers. This ensures headers
    are added to ALL responses, including:
    - Normal responses
    - Error responses (4xx, 5xx)
    - CORS preflight responses (handled by CORSMiddleware before calling inner app)
    - Rate-limit responses (from exception handlers)

    Applied headers:
    - X-Content-Type-Options: nosniff
    - X-Frame-Options: DENY
    - Referrer-Policy: strict-origin-when-cross-origin
    - Permissions-Policy: camera=(), microphone=(), geolocation=()

    These headers are safe for a JSON API and do not interfere with
    Swagger UI (/docs, /redoc) or CORS.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_security_headers(message):
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers.setdefault("X-Content-Type-Options", "nosniff")
                headers.setdefault("X-Frame-Options", "DENY")
                headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
                headers.setdefault(
                    "Permissions-Policy",
                    "camera=(), microphone=(), geolocation=()",
                )
            await send(message)

        await self.app(scope, receive, send_with_security_headers)