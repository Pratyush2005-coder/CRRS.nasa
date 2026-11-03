"""Rate limiting configuration and utilities."""

from typing import Optional
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import Request, FastAPI
from fastapi.responses import JSONResponse

from app.core.config import settings


# Custom key function that respects X-Forwarded-For only when explicitly configured
def get_client_identifier(request: Request) -> str:
    """
    Get client identifier for rate limiting.

    By default, uses the direct client IP from the request.
    Only uses X-Forwarded-For when BEHIND_TRUSTED_PROXY is True.
    """
    if getattr(settings, "BEHIND_TRUSTED_PROXY", False):
        # Trust X-Forwarded-For header when behind a trusted proxy (e.g., nginx, ALB)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # Take the first IP in the chain (original client)
            return forwarded_for.split(",")[0].strip()

    # Default: use direct client IP
    return get_remote_address(request)


# Rate limit configurations (requests per minute)
class RateLimitConfig:
    """Centralized rate limit configuration."""

    # Auth endpoints - strict limits to prevent brute force
    LOGIN = "5/minute"
    REGISTER = "10/minute"

    # Public coordinate-based endpoints
    CLIMATE_ANALYSIS = "30/minute"
    ROTATION_COORDINATE = "30/minute"

    # Other public endpoints
    DEFAULT_PUBLIC = "60/minute"


# Create limiter instance with custom key function
limiter = Limiter(
    key_func=get_client_identifier,
    default_limits=[RateLimitConfig.DEFAULT_PUBLIC],
    storage_uri="memory://",  # In-memory storage (not shared across workers)
    strategy="fixed-window",
)


def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """
    Custom handler for rate limit exceeded errors.

    Returns HTTP 429 with Retry-After header and minimal error details.
    """
    # Get retry-after from the exception
    retry_after = exc.retry_after if hasattr(exc, "retry_after") else 60

    return JSONResponse(
        status_code=429,
        content={
            "detail": "Rate limit exceeded. Please slow down your requests.",
            "retry_after_seconds": retry_after,
        },
        headers={
            "Retry-After": str(retry_after),
            "X-RateLimit-Limit": str(exc.limit.limit) if exc.limit else "unknown",
            "X-RateLimit-Remaining": "0",
            "X-RateLimit-Reset": str(retry_after),
        },
    )


def setup_rate_limiting(app: FastAPI) -> None:
    """
    Configure rate limiting for the FastAPI application.

    Args:
        app: The FastAPI application instance.
    """
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)


# Decorators for specific endpoint limits
def login_rate_limit():
    """Rate limit decorator for login endpoint: 5 requests per minute."""
    return limiter.limit(RateLimitConfig.LOGIN)


def register_rate_limit():
    """Rate limit decorator for register endpoint: 10 requests per minute."""
    return limiter.limit(RateLimitConfig.REGISTER)


def climate_analysis_rate_limit():
    """Rate limit decorator for climate analysis endpoint: 30 requests per minute."""
    return limiter.limit(RateLimitConfig.CLIMATE_ANALYSIS)


def rotation_coordinate_rate_limit():
    """Rate limit decorator for coordinate-based rotation endpoint: 30 requests per minute."""
    return limiter.limit(RateLimitConfig.ROTATION_COORDINATE)