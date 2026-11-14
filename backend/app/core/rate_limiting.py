"""Rate limiting configuration and utilities.

This module provides rate limiting functionality using SlowAPI with support for
both in-memory storage (development/single-worker) and Redis-backed storage
(production/multi-worker distributed rate limiting).

Rate limits are applied per endpoint using decorators:
- @register_rate_limit() - for registration endpoint
- @login_rate_limit() - for login endpoint
- @forgot_password_rate_limit() - for forgot password endpoint
- @reset_password_rate_limit() - for reset password endpoint
- @climate_analysis_rate_limit() - for climate analysis endpoint
- @rotation_coordinate_rate_limit() - for coordinate-based rotation endpoint

Each decorator registers a custom rate limit key function and limit string.
The key function extracts client identifier (IP address) from request.

Redis Integration:
- When REDIS_RATE_LIMITING_ENABLED=True, attempts to use RedisStorage
- Falls back to in-memory storage if Redis is unavailable
- Redis client lifecycle is managed with proper connection pooling
- Health checks ensure Redis connectivity before enabling distributed limiting
"""

import logging
from typing import Optional, Any
from contextlib import asynccontextmanager
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from starlette.requests import Request
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.core.config import settings

logger = logging.getLogger(__name__)

# Global Redis client for lifecycle management
_redis_client: Optional[Any] = None
_redis_storage: Optional[Any] = None
_using_redis: bool = False


def get_client_identifier(request: Request) -> str:
    """Extract client identifier for rate limiting.

    Uses X-Forwarded-For header when BEHIND_TRUSTED_PROXY is True,
    otherwise falls back to direct client IP.

    Args:
        request: FastAPI/Starlette request object.

    Returns:
        Client identifier string (IP address).
    """
    if settings.BEHIND_TRUSTED_PROXY:
        # Trust X-Forwarded-For header from trusted reverse proxy
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # Take the first IP in the chain (original client)
            return forwarded_for.split(",")[0].strip()
    # Direct client IP (fallback or when not behind proxy)
    return get_remote_address(request)


def _create_redis_storage() -> Optional[str]:
    """Attempt to create Redis storage URI for distributed rate limiting.

    Returns:
        Redis storage URI string if successful, None if Redis unavailable or disabled.
    """
    global _redis_client, _redis_storage, _using_redis

    if not settings.REDIS_RATE_LIMITING_ENABLED:
        logger.info("Redis rate limiting disabled via configuration (REDIS_RATE_LIMITING_ENABLED=False)")
        return None

    try:
        import redis
        from limits.storage import storage_from_string

        # Create Redis client with connection pooling and timeouts
        _redis_client = redis.Redis.from_url(
            settings.REDIS_URL,
            socket_timeout=settings.REDIS_SOCKET_TIMEOUT,
            socket_connect_timeout=settings.REDIS_CONNECTION_TIMEOUT,
            socket_keepalive=settings.REDIS_SOCKET_KEEPALIVE > 0,
            socket_keepalive_options={} if settings.REDIS_SOCKET_KEEPALIVE <= 0 else None,
            max_connections=10,
            retry_on_timeout=True,
            health_check_interval=settings.REDIS_HEALTH_CHECK_INTERVAL if settings.REDIS_HEALTH_CHECK_INTERVAL > 0 else None,
        )

        # Test connection with retries
        for attempt in range(settings.REDIS_MAX_RETRIES + 1):
            try:
                _redis_client.ping()
                break
            except redis.ConnectionError as e:
                if attempt == settings.REDIS_MAX_RETRIES:
                    raise
                import time
                time.sleep(settings.REDIS_RETRY_BACKOFF * (2 ** attempt))

        # Build storage URI for limits library
        from urllib.parse import urlparse
        parsed = urlparse(settings.REDIS_URL)
        host = parsed.hostname or "localhost"
        port = parsed.port or 6379
        db = int(parsed.path.lstrip("/")) if parsed.path and parsed.path != "/" else 0

        # Build storage URI for limits library (redis://host:port/db)
        storage_uri = f"redis://{host}:{port}/{db}"

        # Test that storage can be created
        _redis_storage = storage_from_string(
            storage_uri,
            socket_timeout=settings.REDIS_SOCKET_TIMEOUT,
            socket_connect_timeout=settings.REDIS_CONNECTION_TIMEOUT,
            socket_keepalive=settings.REDIS_SOCKET_KEEPALIVE > 0,
            max_connections=10,
        )
        _using_redis = True
        logger.info("Redis-backed distributed rate limiting enabled successfully")
        return storage_uri

    except ImportError:
        logger.warning(
            "redis-py package not installed. Redis rate limiting unavailable. "
            "Install with: pip install redis"
        )
        return None
    except Exception as e:
        logger.warning(
            f"Failed to initialize Redis rate limiting: {type(e).__name__}: {e}. "
            "Falling back to in-memory rate limiting."
        )
        _cleanup_redis()
        return None


def _cleanup_redis() -> None:
    """Clean up Redis client and storage."""
    global _redis_client, _redis_storage, _using_redis
    if _redis_client:
        try:
            _redis_client.close()
        except Exception:
            pass
        _redis_client = None
    _redis_storage = None
    _using_redis = False


# Rate limit configurations (requests per minute)
class RateLimitConfig:
    """Centralized rate limit configuration."""

    # Auth endpoints - strict limits to prevent brute force
    LOGIN = "5/minute"
    REGISTER = "10/minute"
    FORGOT_PASSWORD = "3/minute"  # Very strict to prevent email enumeration
    RESET_PASSWORD = "5/minute"

    # Public coordinate-based endpoints
    CLIMATE_ANALYSIS = "30/minute"
    ROTATION_COORDINATE = "30/minute"

    # Other public endpoints
    DEFAULT_PUBLIC = "60/minute"


# Create limiter instance with custom key function
# Storage will be configured during setup_rate_limiting
_limiter: Optional[Limiter] = None


def _get_limiter() -> Limiter:
    """Get the current limiter instance, creating default if not initialized."""
    global _limiter
    if _limiter is None:
        _limiter = Limiter(
            key_func=get_client_identifier,
            default_limits=[RateLimitConfig.DEFAULT_PUBLIC],
            storage_uri="memory://",
            strategy="fixed-window",
            headers_enabled=False,
        )
    return _limiter


# Initialize default limiter at module load time so it's available for middleware
# This ensures app.state.limiter can be set before any requests are handled
_get_limiter()


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
    """Configure rate limiting for the FastAPI application.

    Attempts to initialize Redis-backed distributed rate limiting if enabled.
    Falls back to in-memory storage if Redis is unavailable.

    Registers the rate limit exceeded exception handler and attaches
    the limiter to the app state for access in route handlers.

    Args:
        app: FastAPI application instance.
    """
    global _limiter, _using_redis

    # Attempt to create Redis storage URI
    redis_storage_uri = _create_redis_storage()

    if redis_storage_uri:
        # Create new limiter with Redis storage
        _limiter = Limiter(
            key_func=get_client_identifier,
            storage_uri=redis_storage_uri,
            default_limits=[RateLimitConfig.DEFAULT_PUBLIC],
            strategy="fixed-window",
            headers_enabled=False,
        )
    else:
        # Ensure we're using in-memory storage
        _using_redis = False
        _limiter = Limiter(
            key_func=get_client_identifier,
            storage_uri="memory://",
            default_limits=[RateLimitConfig.DEFAULT_PUBLIC],
            strategy="fixed-window",
            headers_enabled=False,
        )

    app.state.limiter = _limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

    # Log rate limiting configuration
    if _using_redis:
        logger.info(
            "Rate limiting: Using Redis-backed distributed storage. "
            f"Redis URL: {settings.REDIS_URL.split('@')[-1] if '@' in settings.REDIS_URL else settings.REDIS_URL}"
        )
    else:
        if settings.BEHIND_TRUSTED_PROXY:
            logger.warning(
                "Rate limiting: BEHIND_TRUSTED_PROXY=True - trusting X-Forwarded-For header. "
                "Ensure this is only enabled when running behind a trusted reverse proxy. "
                "Using in-memory storage (not shared across workers)."
            )
        else:
            logger.info(
                "Rate limiting: BEHIND_TRUSTED_PROXY=False - using direct client IP. "
                "Do not enable BEHIND_TRUSTED_PROXY unless behind a trusted reverse proxy. "
                "Using in-memory storage (not shared across workers)."
            )


@asynccontextmanager
async def redis_lifespan(app: FastAPI):
    """Async context manager for Redis connection lifecycle.

    Can be used in FastAPI lifespan to ensure proper Redis cleanup.
    """
    yield
    _cleanup_redis()


# Decorators for specific endpoint limits
def login_rate_limit():
    """Rate limit decorator for login endpoint: 5 requests per minute."""
    return _get_limiter().limit(RateLimitConfig.LOGIN)


def register_rate_limit():
    """Rate limit decorator for register endpoint: 10 requests per minute."""
    return _get_limiter().limit(RateLimitConfig.REGISTER)


def forgot_password_rate_limit():
    """Rate limit decorator for forgot password endpoint: 3 requests per minute."""
    return _get_limiter().limit(RateLimitConfig.FORGOT_PASSWORD)


def reset_password_rate_limit():
    """Rate limit decorator for reset password endpoint: 5 requests per minute."""
    return _get_limiter().limit(RateLimitConfig.RESET_PASSWORD)


def climate_analysis_rate_limit():
    """Rate limit decorator for climate analysis endpoint: 30 requests per minute."""
    return _get_limiter().limit(RateLimitConfig.CLIMATE_ANALYSIS)


def rotation_coordinate_rate_limit():
    """Rate limit decorator for coordinate-based rotation endpoint: 30 requests per minute."""
    return _get_limiter().limit(RateLimitConfig.ROTATION_COORDINATE)


def is_using_redis() -> bool:
    """Check if Redis-backed rate limiting is currently active.

    Returns:
        True if using Redis storage, False if using in-memory fallback.
    """
    return _using_redis


def get_redis_client() -> Optional[Any]:
    """Get the Redis client instance for health checks or manual operations.

    Returns:
        Redis client if connected, None otherwise.
    """
    return _redis_client


def get_limiter() -> Limiter:
    """Get the current limiter instance for external access (e.g., testing)."""
    return _get_limiter()