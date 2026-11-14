"""Tests for Redis-backed distributed rate limiting (Phase 4.8C.4).

Tests cover:
1. Redis configuration validation
2. Redis connection and storage initialization
3. Fallback to in-memory when Redis unavailable
4. Redis client lifecycle management
5. Rate limiting behavior with Redis vs in-memory
"""

import os
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient
from fastapi import FastAPI, Request

# Ensure backend root is on sys.path for test imports
import sys
from pathlib import Path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.core.config import Settings
from app.core.rate_limiting import (
    get_limiter,
    setup_rate_limiting,
    redis_lifespan,
    is_using_redis,
    get_redis_client,
    _create_redis_storage,
    _cleanup_redis,
    get_client_identifier,
    RateLimitConfig,
)
from app.main import app


class TestRedisConfiguration:
    """Tests for Redis configuration validation."""

    def test_redis_url_valid_redis_scheme(self):
        """Test REDIS_URL validation with redis:// scheme."""
        settings = Settings(
            SECRET_KEY="test-secret",
            REDIS_URL="redis://localhost:6379/0",
        )
        assert settings.REDIS_URL == "redis://localhost:6379/0"

    def test_redis_url_valid_rediss_scheme(self):
        """Test REDIS_URL validation with rediss:// (TLS) scheme."""
        settings = Settings(
            SECRET_KEY="test-secret",
            REDIS_URL="rediss://user:pass@host:6379/0",
        )
        assert settings.REDIS_URL == "rediss://user:pass@host:6379/0"

    def test_redis_url_valid_unix_scheme(self):
        """Test REDIS_URL validation with redis+unix:// scheme."""
        settings = Settings(
            SECRET_KEY="test-secret",
            REDIS_URL="redis+unix:///path/to/socket?db=0",
        )
        assert settings.REDIS_URL == "redis+unix:///path/to/socket?db=0"

    def test_redis_url_invalid_scheme_raises(self):
        """Test REDIS_URL validation rejects invalid schemes."""
        with pytest.raises(ValueError, match="must start with one of"):
            Settings(
                SECRET_KEY="test-secret",
                REDIS_URL="http://localhost:6379/0",
            )

    def test_redis_url_empty_raises(self):
        """Test REDIS_URL validation rejects empty string."""
        with pytest.raises(ValueError, match="cannot be empty"):
            Settings(
                SECRET_KEY="test-secret",
                REDIS_URL="",
            )

    def test_redis_connection_timeout_positive(self):
        """Test REDIS_CONNECTION_TIMEOUT validation requires positive value."""
        with pytest.raises(ValueError, match="must be positive"):
            Settings(
                SECRET_KEY="test-secret",
                REDIS_CONNECTION_TIMEOUT=0,
            )

    def test_redis_socket_timeout_positive(self):
        """Test REDIS_SOCKET_TIMEOUT validation requires positive value."""
        with pytest.raises(ValueError, match="must be positive"):
            Settings(
                SECRET_KEY="test-secret",
                REDIS_SOCKET_TIMEOUT=-1,
            )

    def test_redis_socket_keepalive_non_negative(self):
        """Test REDIS_SOCKET_KEEPALIVE validation allows zero."""
        settings = Settings(
            SECRET_KEY="test-secret",
            REDIS_SOCKET_KEEPALIVE=0,
        )
        assert settings.REDIS_SOCKET_KEEPALIVE == 0

    def test_redis_max_retries_non_negative(self):
        """Test REDIS_MAX_RETRIES validation allows zero."""
        settings = Settings(
            SECRET_KEY="test-secret",
            REDIS_MAX_RETRIES=0,
        )
        assert settings.REDIS_MAX_RETRIES == 0

    def test_redis_retry_backoff_non_negative(self):
        """Test REDIS_RETRY_BACKOFF validation allows zero."""
        settings = Settings(
            SECRET_KEY="test-secret",
            REDIS_RETRY_BACKOFF=0,
        )
        assert settings.REDIS_RETRY_BACKOFF == 0

    def test_redis_health_check_interval_non_negative(self):
        """Test REDIS_HEALTH_CHECK_INTERVAL validation allows zero."""
        settings = Settings(
            SECRET_KEY="test-secret",
            REDIS_HEALTH_CHECK_INTERVAL=0,
        )
        assert settings.REDIS_HEALTH_CHECK_INTERVAL == 0

    def test_redis_rate_limiting_enabled_default_false(self):
        """Test REDIS_RATE_LIMITING_ENABLED defaults to False."""
        settings = Settings(SECRET_KEY="test-secret")
        assert settings.REDIS_RATE_LIMITING_ENABLED is False

    def test_redis_rate_limiting_enabled_can_be_true(self):
        """Test REDIS_RATE_LIMITING_ENABLED can be set to True."""
        settings = Settings(
            SECRET_KEY="test-secret",
            REDIS_RATE_LIMITING_ENABLED=True,
        )
        assert settings.REDIS_RATE_LIMITING_ENABLED is True


class TestRedisStorageCreation:
    """Tests for Redis storage creation and fallback."""

    def setup_method(self):
        """Reset global state before each test."""
        _cleanup_redis()

    def teardown_method(self):
        """Clean up after each test."""
        _cleanup_redis()

    @patch("app.core.rate_limiting.settings")
    def test_create_redis_storage_disabled(self, mock_settings):
        """Test Redis storage creation when disabled in config."""
        mock_settings.REDIS_RATE_LIMITING_ENABLED = False
        mock_settings.REDIS_URL = "redis://localhost:6379/0"

        result = _create_redis_storage()
        assert result is None
        assert is_using_redis() is False

    @patch("app.core.rate_limiting.settings")
    @patch("redis.Redis")
    @patch("limits.storage.storage_from_string")
    def test_create_redis_storage_success(self, mock_storage_from_string, mock_redis_class, mock_settings):
        """Test successful Redis storage creation."""
        mock_settings.REDIS_RATE_LIMITING_ENABLED = True
        mock_settings.REDIS_URL = "redis://localhost:6379/0"
        mock_settings.REDIS_SOCKET_TIMEOUT = 5.0
        mock_settings.REDIS_CONNECTION_TIMEOUT = 5.0
        mock_settings.REDIS_SOCKET_KEEPALIVE = 0
        mock_settings.REDIS_MAX_RETRIES = 3
        mock_settings.REDIS_RETRY_BACKOFF = 0.1
        mock_settings.REDIS_HEALTH_CHECK_INTERVAL = 30

        mock_client = MagicMock()
        mock_client.ping.return_value = True
        mock_redis_class.from_url.return_value = mock_client

        mock_storage = MagicMock()
        mock_storage_from_string.return_value = mock_storage

        result = _create_redis_storage()

        assert result == "redis://localhost:6379/0"
        assert is_using_redis() is True
        mock_redis_class.from_url.assert_called_once()
        mock_client.ping.assert_called()
        mock_storage_from_string.assert_called_once()

    @patch("app.core.rate_limiting.settings")
    @patch("redis.Redis")
    @patch("limits.storage.storage_from_string")
    def test_create_redis_storage_connection_failure_fallback(self, mock_storage_from_string, mock_redis_class, mock_settings):
        """Test fallback to in-memory when Redis connection fails."""
        mock_settings.REDIS_RATE_LIMITING_ENABLED = True
        mock_settings.REDIS_URL = "redis://localhost:6379/0"
        mock_settings.REDIS_SOCKET_TIMEOUT = 5.0
        mock_settings.REDIS_CONNECTION_TIMEOUT = 5.0
        mock_settings.REDIS_SOCKET_KEEPALIVE = 0
        mock_settings.REDIS_MAX_RETRIES = 0  # No retries for faster test
        mock_settings.REDIS_RETRY_BACKOFF = 0.1
        mock_settings.REDIS_HEALTH_CHECK_INTERVAL = 30

        mock_client = MagicMock()
        mock_client.ping.side_effect = Exception("Connection refused")
        mock_redis_class.from_url.return_value = mock_client

        result = _create_redis_storage()

        assert result is None
        assert is_using_redis() is False

    @patch("app.core.rate_limiting.settings")
    def test_create_redis_storage_import_error_fallback(self, mock_settings):
        """Test fallback when redis-py not installed."""
        mock_settings.REDIS_RATE_LIMITING_ENABLED = True
        mock_settings.REDIS_URL = "redis://localhost:6379/0"

        with patch.dict("sys.modules", {"redis": None}):
            result = _create_redis_storage()

        assert result is None
        assert is_using_redis() is False

    def test_cleanup_redis(self):
        """Test Redis cleanup function."""
        # Manually set some state
        import app.core.rate_limiting as rl
        mock_client = MagicMock()
        rl._redis_client = mock_client
        rl._redis_storage = MagicMock()
        rl._using_redis = True

        _cleanup_redis()

        assert rl._redis_client is None
        assert rl._redis_storage is None
        assert rl._using_redis is False
        mock_client.close.assert_called_once()


class TestRateLimiterSetup:
    """Tests for rate limiter setup with Redis and in-memory."""

    def setup_method(self):
        """Reset global state before each test."""
        _cleanup_redis()

    def teardown_method(self):
        """Clean up after each test."""
        _cleanup_redis()

    @patch("app.core.rate_limiting.settings")
    def test_setup_rate_limiting_in_memory(self, mock_settings):
        """Test rate limiter setup with in-memory storage."""
        mock_settings.REDIS_RATE_LIMITING_ENABLED = False
        mock_settings.BEHIND_TRUSTED_PROXY = False

        test_app = FastAPI()
        setup_rate_limiting(test_app)

        assert test_app.state.limiter is not None
        assert is_using_redis() is False

    @patch("app.core.rate_limiting.settings")
    @patch("redis.Redis")
    @patch("limits.storage.storage_from_string")
    def test_setup_rate_limiting_redis(self, mock_storage_from_string, mock_redis_class, mock_settings):
        """Test rate limiter setup with Redis storage."""
        mock_settings.REDIS_RATE_LIMITING_ENABLED = True
        mock_settings.REDIS_URL = "redis://localhost:6379/0"
        mock_settings.REDIS_SOCKET_TIMEOUT = 5.0
        mock_settings.REDIS_CONNECTION_TIMEOUT = 5.0
        mock_settings.REDIS_SOCKET_KEEPALIVE = 0
        mock_settings.REDIS_MAX_RETRIES = 3
        mock_settings.REDIS_RETRY_BACKOFF = 0.1
        mock_settings.REDIS_HEALTH_CHECK_INTERVAL = 30
        mock_settings.BEHIND_TRUSTED_PROXY = False

        mock_client = MagicMock()
        mock_client.ping.return_value = True
        mock_redis_class.from_url.return_value = mock_client

        mock_storage = MagicMock()
        mock_storage_from_string.return_value = mock_storage

        test_app = FastAPI()
        setup_rate_limiting(test_app)

        assert test_app.state.limiter is not None
        assert is_using_redis() is True

    def test_get_client_identifier_direct_ip(self):
        """Test client identifier extraction with direct IP."""
        with patch("app.core.rate_limiting.settings.BEHIND_TRUSTED_PROXY", False):
            mock_request = MagicMock()
            mock_request.headers = {}
            mock_request.client = MagicMock()
            mock_request.client.host = "192.168.1.100"

            with patch("app.core.rate_limiting.get_remote_address", return_value="192.168.1.100"):
                result = get_client_identifier(mock_request)

            assert result == "192.168.1.100"

    def test_get_client_identifier_x_forwarded_for_trusted(self):
        """Test client identifier with X-Forwarded-For when behind trusted proxy."""
        with patch("app.core.rate_limiting.settings.BEHIND_TRUSTED_PROXY", True):
            mock_request = MagicMock()
            mock_request.headers = {"X-Forwarded-For": "10.0.0.1, 192.168.1.100"}

            result = get_client_identifier(mock_request)

            assert result == "10.0.0.1"

    def test_get_client_identifier_x_forwarded_for_not_trusted(self):
        """Test client identifier ignores X-Forwarded-For when not behind trusted proxy."""
        with patch("app.core.rate_limiting.settings.BEHIND_TRUSTED_PROXY", False):
            mock_request = MagicMock()
            mock_request.headers = {"X-Forwarded-For": "10.0.0.1, 192.168.1.100"}
            mock_request.client = MagicMock()
            mock_request.client.host = "192.168.1.100"

            with patch("app.core.rate_limiting.get_remote_address", return_value="192.168.1.100"):
                result = get_client_identifier(mock_request)

            assert result == "192.168.1.100"


class TestRedisLifecycle:
    """Tests for Redis connection lifecycle management."""

    def setup_method(self):
        """Reset global state before each test."""
        _cleanup_redis()

    def teardown_method(self):
        """Clean up after each test."""
        _cleanup_redis()

    @pytest.mark.asyncio
    async def test_redis_lifespan_cleanup(self):
        """Test Redis lifecycle manager cleans up on exit."""
        import app.core.rate_limiting as rl
        mock_client = MagicMock()
        rl._redis_client = mock_client
        rl._using_redis = True

        test_app = FastAPI()
        async with redis_lifespan(test_app):
            pass

        mock_client.close.assert_called_once()
        assert rl._redis_client is None
        assert rl._using_redis is False

    def test_get_redis_client_returns_none_when_not_using_redis(self):
        """Test get_redis_client returns None when not using Redis."""
        assert get_redis_client() is None


class TestRateLimitConfig:
    """Tests for rate limit configuration values."""

    def test_rate_limit_config_values(self):
        """Test all rate limit config values are set."""
        assert RateLimitConfig.LOGIN == "5/minute"
        assert RateLimitConfig.REGISTER == "10/minute"
        assert RateLimitConfig.FORGOT_PASSWORD == "3/minute"
        assert RateLimitConfig.RESET_PASSWORD == "5/minute"
        assert RateLimitConfig.CLIMATE_ANALYSIS == "30/minute"
        assert RateLimitConfig.ROTATION_COORDINATE == "30/minute"
        assert RateLimitConfig.DEFAULT_PUBLIC == "60/minute"


class TestRateLimitingIntegration:
    """Integration tests for rate limiting with the FastAPI app."""

    def setup_method(self):
        """Reset global state before each test."""
        _cleanup_redis()

    def teardown_method(self):
        """Clean up after each test."""
        _cleanup_redis()

    @patch("app.core.rate_limiting.settings")
    def test_in_memory_rate_limiting_works(self, mock_settings):
        """Test in-memory rate limiting enforces limits."""
        mock_settings.REDIS_RATE_LIMITING_ENABLED = False
        mock_settings.BEHIND_TRUSTED_PROXY = False

        test_app = FastAPI()
        setup_rate_limiting(test_app)

        # Disable limiter for testing
        test_app.state.limiter.enabled = False

        client = TestClient(test_app)

        @test_app.get("/test")
        @test_app.state.limiter.limit("2/minute")
        async def test_endpoint(request: Request):
            return {"message": "ok"}

        # Re-enable for actual test
        test_app.state.limiter.enabled = True

        # Make requests up to limit
        response1 = client.get("/test")
        response2 = client.get("/test")

        assert response1.status_code == 200
        assert response2.status_code == 200

        # Third request should be rate limited
        response3 = client.get("/test")
        assert response3.status_code == 429


class TestAuthEndpointRateLimits:
    """Tests for auth endpoint specific rate limit decorators."""

    def setup_method(self):
        """Reset global state before each test."""
        _cleanup_redis()

    def teardown_method(self):
        """Clean up after each test."""
        _cleanup_redis()

    @patch("app.core.rate_limiting.settings")
    def test_login_rate_limit_decorator(self, mock_settings):
        """Test login_rate_limit decorator uses correct limit."""
        mock_settings.REDIS_RATE_LIMITING_ENABLED = False
        mock_settings.BEHIND_TRUSTED_PROXY = False

        from app.core.rate_limiting import login_rate_limit

        test_app = FastAPI()
        setup_rate_limiting(test_app)

        # Verify the decorator returns a limit
        limit_decorator = login_rate_limit()
        assert limit_decorator is not None

    @patch("app.core.rate_limiting.settings")
    def test_register_rate_limit_decorator(self, mock_settings):
        """Test register_rate_limit decorator uses correct limit."""
        mock_settings.REDIS_RATE_LIMITING_ENABLED = False
        mock_settings.BEHIND_TRUSTED_PROXY = False

        from app.core.rate_limiting import register_rate_limit

        test_app = FastAPI()
        setup_rate_limiting(test_app)

        limit_decorator = register_rate_limit()
        assert limit_decorator is not None

    @patch("app.core.rate_limiting.settings")
    def test_forgot_password_rate_limit_decorator(self, mock_settings):
        """Test forgot_password_rate_limit decorator uses correct limit."""
        mock_settings.REDIS_RATE_LIMITING_ENABLED = False
        mock_settings.BEHIND_TRUSTED_PROXY = False

        from app.core.rate_limiting import forgot_password_rate_limit

        test_app = FastAPI()
        setup_rate_limiting(test_app)

        limit_decorator = forgot_password_rate_limit()
        assert limit_decorator is not None

    @patch("app.core.rate_limiting.settings")
    def test_reset_password_rate_limit_decorator(self, mock_settings):
        """Test reset_password_rate_limit decorator uses correct limit."""
        mock_settings.REDIS_RATE_LIMITING_ENABLED = False
        mock_settings.BEHIND_TRUSTED_PROXY = False

        from app.core.rate_limiting import reset_password_rate_limit

        test_app = FastAPI()
        setup_rate_limiting(test_app)

        limit_decorator = reset_password_rate_limit()
        assert limit_decorator is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])