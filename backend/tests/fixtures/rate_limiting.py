"""Shared fixtures for rate limiting tests."""

import pytest
from app.core.rate_limiting import get_limiter
from limits.storage import MemoryStorage
from limits.strategies import STRATEGIES

# Capture TRUE original limiter state at module load time
_limiter = get_limiter()
TRUE_ORIGINAL_ENABLED = _limiter.enabled
TRUE_ORIGINAL_STORAGE = _limiter._storage
TRUE_ORIGINAL_KEY_FUNC = _limiter._key_func


@pytest.fixture
def reset_rate_limiter():
    """Reset rate limiter storage before each test that uses rate limiting."""
    limiter = get_limiter()

    # Reset to clean test state (disabled, fresh memory storage, original key func)
    limiter.enabled = False
    limiter._storage = MemoryStorage()
    limiter._limiter = STRATEGIES["fixed-window"](limiter._storage)
    limiter._key_func = TRUE_ORIGINAL_KEY_FUNC

    yield

    # Restore to TRUE original state
    limiter.enabled = TRUE_ORIGINAL_ENABLED
    limiter._storage = TRUE_ORIGINAL_STORAGE
    limiter._limiter = STRATEGIES["fixed-window"](limiter._storage)
    limiter._key_func = TRUE_ORIGINAL_KEY_FUNC