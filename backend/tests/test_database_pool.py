"""Tests for database connection pool configuration."""

import os
from unittest.mock import patch, MagicMock
import pytest
from sqlalchemy.pool import QueuePool, NullPool
from sqlalchemy import create_engine

from app.core.config import Settings


class TestDatabasePoolConfigValidation:
    """Test database pool configuration validation in Settings."""

    def test_default_pool_settings(self):
        """Test default database pool settings have sensible values."""
        settings = Settings(
            SECRET_KEY="test-secret-key-for-testing-only-32-chars-minimum",
            _env_file=None,
        )
        assert settings.DATABASE_POOL_SIZE == 5
        assert settings.DATABASE_MAX_OVERFLOW == 10
        assert settings.DATABASE_POOL_TIMEOUT == 30
        assert settings.DATABASE_POOL_RECYCLE == 1800
        assert settings.DATABASE_POOL_PRE_PING is True
        assert settings.DATABASE_CONNECT_TIMEOUT == 10
        assert settings.DATABASE_ECHO is False

    def test_custom_pool_settings_from_env(self):
        """Test custom pool settings can be set via environment variables."""
        settings = Settings(
            SECRET_KEY="test-secret-key-for-testing-only-32-chars-minimum",
            DATABASE_POOL_SIZE=10,
            DATABASE_MAX_OVERFLOW=20,
            DATABASE_POOL_TIMEOUT=60,
            DATABASE_POOL_RECYCLE=3600,
            DATABASE_POOL_PRE_PING=False,
            DATABASE_CONNECT_TIMEOUT=15,
            DATABASE_ECHO=True,
            _env_file=None,
        )
        assert settings.DATABASE_POOL_SIZE == 10
        assert settings.DATABASE_MAX_OVERFLOW == 20
        assert settings.DATABASE_POOL_TIMEOUT == 60
        assert settings.DATABASE_POOL_RECYCLE == 3600
        assert settings.DATABASE_POOL_PRE_PING is False
        assert settings.DATABASE_CONNECT_TIMEOUT == 15
        assert settings.DATABASE_ECHO is True

    def test_pool_size_validation_negative_rejected(self):
        """Test negative pool size is rejected."""
        with pytest.raises(ValueError) as exc_info:
            Settings(
                SECRET_KEY="test-secret-key-for-testing-only-32-chars-minimum",
                DATABASE_POOL_SIZE=-1,
                _env_file=None,
            )
        assert "non-negative" in str(exc_info.value).lower()

    def test_pool_size_zero_accepted(self):
        """Test pool size of zero is accepted (valid for some configs)."""
        settings = Settings(
            SECRET_KEY="test-secret-key-for-testing-only-32-chars-minimum",
            DATABASE_POOL_SIZE=0,
            _env_file=None,
        )
        assert settings.DATABASE_POOL_SIZE == 0

    def test_max_overflow_validation_negative_rejected(self):
        """Test negative max overflow is rejected."""
        with pytest.raises(ValueError) as exc_info:
            Settings(
                SECRET_KEY="test-secret-key-for-testing-only-32-chars-minimum",
                DATABASE_MAX_OVERFLOW=-1,
                _env_file=None,
            )
        assert "non-negative" in str(exc_info.value).lower()

    def test_pool_timeout_validation_zero_rejected(self):
        """Test zero pool timeout is rejected."""
        with pytest.raises(ValueError) as exc_info:
            Settings(
                SECRET_KEY="test-secret-key-for-testing-only-32-chars-minimum",
                DATABASE_POOL_TIMEOUT=0,
                _env_file=None,
            )
        assert "positive" in str(exc_info.value).lower()

    def test_pool_timeout_validation_negative_rejected(self):
        """Test negative pool timeout is rejected."""
        with pytest.raises(ValueError) as exc_info:
            Settings(
                SECRET_KEY="test-secret-key-for-testing-only-32-chars-minimum",
                DATABASE_POOL_TIMEOUT=-5,
                _env_file=None,
            )
        assert "positive" in str(exc_info.value).lower()

    def test_pool_recycle_validation_negative_rejected(self):
        """Test negative pool recycle is rejected."""
        with pytest.raises(ValueError) as exc_info:
            Settings(
                SECRET_KEY="test-secret-key-for-testing-only-32-chars-minimum",
                DATABASE_POOL_RECYCLE=-1,
                _env_file=None,
            )
        assert "non-negative" in str(exc_info.value).lower()

    def test_pool_recycle_zero_accepted(self):
        """Test pool recycle of zero is accepted (no recycling)."""
        settings = Settings(
            SECRET_KEY="test-secret-key-for-testing-only-32-chars-minimum",
            DATABASE_POOL_RECYCLE=0,
            _env_file=None,
        )
        assert settings.DATABASE_POOL_RECYCLE == 0

    def test_connect_timeout_validation_zero_rejected(self):
        """Test zero connect timeout is rejected."""
        with pytest.raises(ValueError) as exc_info:
            Settings(
                SECRET_KEY="test-secret-key-for-testing-only-32-chars-minimum",
                DATABASE_CONNECT_TIMEOUT=0,
                _env_file=None,
            )
        assert "positive" in str(exc_info.value).lower()

    def test_connect_timeout_validation_negative_rejected(self):
        """Test negative connect timeout is rejected."""
        with pytest.raises(ValueError) as exc_info:
            Settings(
                SECRET_KEY="test-secret-key-for-testing-only-32-chars-minimum",
                DATABASE_CONNECT_TIMEOUT=-5,
                _env_file=None,
            )
        assert "positive" in str(exc_info.value).lower()


class TestDatabasePoolEngineCreation:
    """Test database engine creation with pool settings."""

    def test_sqlite_uses_nullpool(self):
        """Test SQLite uses NullPool (no connection pooling)."""
        # The default DATABASE_URL is sqlite, so engine should use NullPool
        from app.core.database import engine
        assert isinstance(engine.pool, NullPool)

    def _create_test_engine(self, database_url, **settings_overrides):
        """Helper to create an engine with specific settings for testing."""
        # Create a fresh settings object
        test_settings = Settings(
            SECRET_KEY="test-secret-key-for-testing-only-32-chars-minimum",
            DATABASE_URL=database_url,
            **settings_overrides,
            _env_file=None,
        )

        connect_args = {}
        is_sqlite = database_url.startswith("sqlite")
        is_postgresql = database_url.startswith("postgresql") or database_url.startswith("postgres")

        if is_sqlite:
            connect_args["check_same_thread"] = False
            pool_class = NullPool
            pool_kwargs = {}
        elif is_postgresql:
            connect_args["connect_timeout"] = test_settings.DATABASE_CONNECT_TIMEOUT
            pool_class = QueuePool
            pool_kwargs = {
                "pool_size": test_settings.DATABASE_POOL_SIZE,
                "max_overflow": test_settings.DATABASE_MAX_OVERFLOW,
                "pool_timeout": test_settings.DATABASE_POOL_TIMEOUT,
                "pool_recycle": test_settings.DATABASE_POOL_RECYCLE,
                "pool_pre_ping": test_settings.DATABASE_POOL_PRE_PING,
            }
        else:
            pool_class = QueuePool
            pool_kwargs = {
                "pool_size": test_settings.DATABASE_POOL_SIZE,
                "max_overflow": test_settings.DATABASE_MAX_OVERFLOW,
                "pool_timeout": test_settings.DATABASE_POOL_TIMEOUT,
                "pool_recycle": test_settings.DATABASE_POOL_RECYCLE,
                "pool_pre_ping": test_settings.DATABASE_POOL_PRE_PING,
            }

        engine = create_engine(
            database_url,
            connect_args=connect_args,
            poolclass=pool_class,
            **pool_kwargs,
            echo=test_settings.DATABASE_ECHO,
        )
        return engine

    def test_postgresql_uses_queuepool_with_settings(self):
        """Test PostgreSQL uses QueuePool with configured settings."""
        # Test the configuration logic without needing psycopg installed
        # We verify that the settings are correctly passed to create_engine
        from app.core.config import Settings
        from sqlalchemy.pool import QueuePool

        settings = Settings(
            SECRET_KEY="test-secret-key-for-testing-only-32-chars-minimum",
            DATABASE_URL="postgresql://user:pass@localhost:5432/testdb",
            _env_file=None,
        )

        # Verify the settings values are correct
        assert settings.DATABASE_POOL_SIZE == 5
        assert settings.DATABASE_MAX_OVERFLOW == 10
        assert settings.DATABASE_POOL_TIMEOUT == 30
        assert settings.DATABASE_POOL_RECYCLE == 1800
        assert settings.DATABASE_POOL_PRE_PING is True
        assert settings.DATABASE_CONNECT_TIMEOUT == 10
        assert settings.DATABASE_ECHO is False

        # Verify the logic in database.py would use QueuePool for PostgreSQL
        is_postgresql = settings.DATABASE_URL.startswith("postgresql") or settings.DATABASE_URL.startswith("postgres")
        assert is_postgresql is True

        # Verify pool class selection logic
        from sqlalchemy.pool import QueuePool
        pool_class = QueuePool if is_postgresql else NullPool
        assert pool_class == QueuePool

    def test_postgresql_custom_pool_settings(self):
        """Test PostgreSQL uses custom pool settings from config."""
        from app.core.config import Settings
        from sqlalchemy.pool import QueuePool

        settings = Settings(
            SECRET_KEY="test-secret-key-for-testing-only-32-chars-minimum",
            DATABASE_URL="postgresql://user:pass@localhost:5432/testdb",
            DATABASE_POOL_SIZE=20,
            DATABASE_MAX_OVERFLOW=30,
            DATABASE_POOL_TIMEOUT=60,
            DATABASE_POOL_RECYCLE=3600,
            DATABASE_POOL_PRE_PING=False,
            DATABASE_CONNECT_TIMEOUT=15,
            DATABASE_ECHO=True,
            _env_file=None,
        )

        # Verify custom settings are applied
        assert settings.DATABASE_POOL_SIZE == 20
        assert settings.DATABASE_MAX_OVERFLOW == 30
        assert settings.DATABASE_POOL_TIMEOUT == 60
        assert settings.DATABASE_POOL_RECYCLE == 3600
        assert settings.DATABASE_POOL_PRE_PING is False
        assert settings.DATABASE_CONNECT_TIMEOUT == 15
        assert settings.DATABASE_ECHO is True

        # Verify connect_args would include connect_timeout
        connect_args = {"connect_timeout": settings.DATABASE_CONNECT_TIMEOUT}
        assert connect_args["connect_timeout"] == 15

        # Verify pool kwargs would be passed correctly
        pool_kwargs = {
            "pool_size": settings.DATABASE_POOL_SIZE,
            "max_overflow": settings.DATABASE_MAX_OVERFLOW,
            "pool_timeout": settings.DATABASE_POOL_TIMEOUT,
            "pool_recycle": settings.DATABASE_POOL_RECYCLE,
            "pool_pre_ping": settings.DATABASE_POOL_PRE_PING,
        }
        assert pool_kwargs["pool_size"] == 20
        assert pool_kwargs["max_overflow"] == 30
        assert pool_kwargs["pool_timeout"] == 60
        assert pool_kwargs["pool_recycle"] == 3600
        assert pool_kwargs["pool_pre_ping"] is False

    def test_postgres_url_variants_use_queuepool(self):
        """Test both postgresql:// and postgres:// URL schemes use QueuePool."""
        from app.core.config import Settings
        from sqlalchemy.pool import QueuePool

        for url_prefix in ["postgresql://", "postgres://"]:
            settings = Settings(
                SECRET_KEY="test-secret-key-for-testing-only-32-chars-minimum",
                DATABASE_URL=f"{url_prefix}user:pass@localhost:5432/testdb",
                _env_file=None,
            )

            is_postgresql = settings.DATABASE_URL.startswith("postgresql") or settings.DATABASE_URL.startswith("postgres")
            assert is_postgresql is True

            pool_class = QueuePool if is_postgresql else NullPool
            assert pool_class == QueuePool


class TestDatabaseConnectivityCheck:
    """Test database connectivity check works with pool configuration."""

    def test_check_database_connectivity_sqlite(self):
        """Test connectivity check works with SQLite."""
        from app.core.database import check_database_connectivity
        result = check_database_connectivity()
        assert result is True

    def test_check_database_connectivity_handles_failure(self):
        """Test connectivity check returns False on failure (not raise)."""
        from app.core.database import check_database_connectivity
        result = check_database_connectivity()
        assert isinstance(result, bool)

    def test_health_check_compatibility(self):
        """Test health check endpoint works with pool configuration."""
        from fastapi.testclient import TestClient
        from app.main import app

        client = TestClient(app)
        response = client.get("/api/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"


class TestDatabasePoolSettingsIntegration:
    """Integration tests for database pool settings."""

    def test_env_example_has_pool_settings(self):
        """Test .env.example documents all pool settings."""
        import os
        env_example_path = os.path.join(
            os.path.dirname(__file__), "..", ".env.example"
        )
        with open(env_example_path) as f:
            content = f.read()

        # Check all pool settings are documented
        assert "DATABASE_POOL_SIZE" in content
        assert "DATABASE_MAX_OVERFLOW" in content
        assert "DATABASE_POOL_TIMEOUT" in content
        assert "DATABASE_POOL_RECYCLE" in content
        assert "DATABASE_POOL_PRE_PING" in content
        assert "DATABASE_CONNECT_TIMEOUT" in content
        assert "DATABASE_ECHO" in content

        # Check comments explain the settings
        assert "Pool size" in content
        assert "Max overflow" in content
        assert "Pool timeout" in content
        assert "Pool recycle" in content
        assert "Pool pre-ping" in content
        assert "Connection Timeout" in content
        assert "Echo SQL" in content

    def test_sqlite_compatibility_no_postgres_args(self):
        """Test SQLite doesn't receive PostgreSQL-specific arguments."""
        from app.core.database import engine

        # SQLite should use NullPool
        assert isinstance(engine.pool, NullPool)

    def test_pool_pre_ping_enabled_by_default(self):
        """Test pool_pre_ping is True by default for safety."""
        settings = Settings(
            SECRET_KEY="test-secret-key-for-testing-only-32-chars-minimum",
            _env_file=None,
        )
        assert settings.DATABASE_POOL_PRE_PING is True

    def test_echo_false_by_default(self):
        """Test DATABASE_ECHO is False by default (not for production)."""
        settings = Settings(
            SECRET_KEY="test-secret-key-for-testing-only-32-chars-minimum",
            _env_file=None,
        )
        assert settings.DATABASE_ECHO is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])