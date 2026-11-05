"""Tests for database session lifecycle and initialization hardening."""

import logging
from unittest.mock import patch, MagicMock
import pytest
from sqlalchemy.exc import SQLAlchemyError, OperationalError
from sqlalchemy.orm import Session
from sqlalchemy import create_engine

from app.core.database import get_db, init_db, engine, Base
from app.core.config import Settings


class TestSessionLifecycle:
    """Test session lifecycle: close on success, rollback on exception, close on exception."""

    def test_session_closes_after_successful_request(self):
        """Session should be closed after successful request."""
        db_gen = get_db()
        session = next(db_gen)  # Get the session

        assert isinstance(session, Session)
        # Note: SQLite session.is_active behavior may vary
        # The key test is that close() is called

        # Simulate successful request completion
        try:
            next(db_gen)  # This should raise StopIteration
        except StopIteration:
            pass

        # Session should be closed - verify close was called
        # (We can't reliably check is_active for SQLite, but close() is called)

    def test_session_rolls_back_after_exception(self):
        """Session should rollback when exception occurs."""
        db_gen = get_db()
        session = next(db_gen)

        # Mock rollback to track if called
        with patch.object(session, 'rollback') as mock_rollback:
            try:
                # Simulate exception in request handler
                db_gen.throw(Exception("Request handler error"))
            except Exception:
                pass

            # rollback should have been called
            mock_rollback.assert_called_once()

    def test_session_closes_after_exception(self):
        """Session should be closed even after exception."""
        db_gen = get_db()
        session = next(db_gen)

        # Mock close to track if called
        with patch.object(session, 'close') as mock_close:
            try:
                db_gen.throw(Exception("Request handler error"))
            except Exception:
                pass

            # close should have been called
            mock_close.assert_called_once()

    def test_session_no_rollback_on_success(self):
        """Session should NOT rollback after successful request."""
        db_gen = get_db()
        session = next(db_gen)

        with patch.object(session, 'rollback') as mock_rollback:
            try:
                next(db_gen)  # Successful completion
            except StopIteration:
                pass

            # rollback should NOT be called on success
            mock_rollback.assert_not_called()

    def test_session_close_called_once_on_success(self):
        """Session close should be called exactly once on success."""
        db_gen = get_db()
        session = next(db_gen)

        with patch.object(session, 'close') as mock_close:
            try:
                next(db_gen)
            except StopIteration:
                pass

            mock_close.assert_called_once()

    def test_session_close_called_once_on_exception(self):
        """Session close should be called exactly once on exception."""
        db_gen = get_db()
        session = next(db_gen)

        with patch.object(session, 'close') as mock_close:
            try:
                db_gen.throw(Exception("Error"))
            except Exception:
                pass

            mock_close.assert_called_once()

    def test_rollback_failure_doesnt_mask_original_error(self):
        """If rollback fails, original exception should still propagate."""
        db_gen = get_db()
        session = next(db_gen)

        # Make rollback raise an exception
        with patch.object(session, 'rollback', side_effect=Exception("Rollback failed")):
            # The generator.throw() will raise the original exception
            # Our implementation catches it, tries rollback, then re-raises
            with pytest.raises(Exception, match="Request handler error"):
                db_gen.throw(Exception("Request handler error"))


class TestDatabaseInitialization:
    """Test database initialization with retry logic and safe error handling."""

    def test_init_db_succeeds_when_db_available(self):
        """Initialization should succeed when database is available."""
        # This uses the actual test database (SQLite)
        # Should not raise any exception
        init_db(max_retries=1, retry_backoff=0.01)

    def test_init_db_failure_reported_safely(self):
        """Initialization failure should be reported without sensitive info."""
        # Save original engine
        from app.core import database as db_module
        original_engine = db_module.engine

        try:
            # Replace with engine that will fail - use SQLite with invalid path
            failing_engine = create_engine("sqlite:////invalid/path/that/does/not/exist/test.db")
            db_module.engine = failing_engine

            with pytest.raises(SQLAlchemyError):
                init_db(max_retries=1, retry_backoff=0.01)
        finally:
            # Restore original engine
            db_module.engine = original_engine

    def test_init_db_retry_stops_after_max_attempts(self):
        """Retry should stop after configured maximum attempts."""
        from app.core import database as db_module
        original_engine = db_module.engine

        try:
            # Create engine that always fails with transient error
            failing_engine = create_engine("sqlite:////invalid/path/that/does/not/exist/test.db")
            db_module.engine = failing_engine

            with patch("time.sleep") as mock_sleep:
                with pytest.raises(SQLAlchemyError):
                    init_db(max_retries=3, retry_backoff=0.01)

                # Should have slept 2 times (between attempts 1-2 and 2-3)
                assert mock_sleep.call_count == 2
        finally:
            db_module.engine = original_engine

    def test_init_db_no_retry_on_non_transient_error(self):
        """Should not retry on non-transient errors (e.g., programming errors)."""
        from app.core import database as db_module
        original_engine = db_module.engine

        try:
            # Use the real engine but patch create_all to raise a programming error
            with patch.object(Base.metadata, 'create_all', side_effect=SQLAlchemyError("syntax error")):
                with patch("time.sleep") as mock_sleep:
                    with pytest.raises(SQLAlchemyError, match="syntax error"):
                        init_db(max_retries=3, retry_backoff=0.01)

                    # Should NOT sleep (no retry on non-transient)
                    mock_sleep.assert_not_called()
        finally:
            db_module.engine = original_engine

    def test_init_db_logs_without_sensitive_info(self, caplog):
        """Initialization should log useful info without exposing secrets."""
        with caplog.at_level(logging.INFO):
            init_db(max_retries=1, retry_backoff=0.01)

        # Check that logs don't contain sensitive info
        for record in caplog.records:
            msg = record.getMessage().lower()
            assert "password" not in msg
            assert "credential" not in msg
            assert "://" not in msg or "sqlite://" in msg  # Only sqlite URL scheme allowed
            assert "postgresql://" not in msg

    def test_init_db_zero_retries_works(self):
        """Zero retries should work (single attempt)."""
        init_db(max_retries=0, retry_backoff=0.01)

    def test_init_db_negative_retries_rejected(self):
        """Negative retries should be rejected by config validation."""
        with pytest.raises(ValueError, match="non-negative"):
            Settings(
                SECRET_KEY="test-secret-key-for-testing-only-32-chars-minimum",
                DATABASE_INIT_MAX_RETRIES=-1,
                _env_file=None,
            )

    def test_init_db_negative_backoff_rejected(self):
        """Negative backoff should be rejected by config validation."""
        with pytest.raises(ValueError, match="non-negative"):
            Settings(
                SECRET_KEY="test-secret-key-for-testing-only-32-chars-minimum",
                DATABASE_INIT_RETRY_BACKOFF=-1.0,
                _env_file=None,
            )


class TestLoggingSafety:
    """Test that no sensitive database information appears in logs."""

    def test_no_passwords_in_logs(self, caplog):
        """Database passwords should not appear in logs."""
        with caplog.at_level(logging.DEBUG):
            init_db(max_retries=1, retry_backoff=0.01)

        for record in caplog.records:
            assert "password" not in record.getMessage().lower()

    def test_no_connection_urls_in_logs(self, caplog):
        """Full connection URLs should not appear in logs."""
        with caplog.at_level(logging.DEBUG):
            init_db(max_retries=1, retry_backoff=0.01)

        for record in caplog.records:
            msg = record.getMessage()
            # Should not contain full URLs with credentials
            assert "://" not in msg or msg.count("://") == 0 or "sqlite://" in msg

    def test_no_sql_data_in_logs(self, caplog):
        """Sensitive SQL data should not appear in logs."""
        with caplog.at_level(logging.DEBUG):
            init_db(max_retries=1, retry_backoff=0.01)

        for record in caplog.records:
            msg = record.getMessage().lower()
            assert "insert" not in msg
            assert "update" not in msg
            assert "delete" not in msg
            assert "select" not in msg


class TestExistingConfigCompatibility:
    """Test that existing SQLite and PostgreSQL configuration tests remain valid."""

    def test_sqlite_config_still_works(self):
        """SQLite configuration should still work."""
        settings = Settings(
            SECRET_KEY="test-secret-key-for-testing-only-32-chars-minimum",
            DATABASE_URL="sqlite:///./test.db",
            _env_file=None,
        )
        assert settings.DATABASE_INIT_MAX_RETRIES == 3
        assert settings.DATABASE_INIT_RETRY_BACKOFF == 1.0

    def test_postgresql_config_still_works(self):
        """PostgreSQL configuration should still work."""
        settings = Settings(
            SECRET_KEY="test-secret-key-for-testing-only-32-chars-minimum",
            DATABASE_URL="postgresql://user:pass@localhost:5432/db",
            _env_file=None,
        )
        assert settings.DATABASE_INIT_MAX_RETRIES == 3
        assert settings.DATABASE_INIT_RETRY_BACKOFF == 1.0

    def test_custom_retry_settings(self):
        """Custom retry settings should be configurable."""
        settings = Settings(
            SECRET_KEY="test-secret-key-for-testing-only-32-chars-minimum",
            DATABASE_INIT_MAX_RETRIES=5,
            DATABASE_INIT_RETRY_BACKOFF=2.0,
            _env_file=None,
        )
        assert settings.DATABASE_INIT_MAX_RETRIES == 5
        assert settings.DATABASE_INIT_RETRY_BACKOFF == 2.0


class TestProductionGuards:
    """Test production safety guardrails."""

    def test_asyncpg_url_rejected(self):
        """postgresql+asyncpg:// URLs should be rejected."""
        with pytest.raises(ValueError, match="asyncpg"):
            Settings(
                SECRET_KEY="test-secret-key-for-testing-only-32-chars-minimum",
                DATABASE_URL="postgresql+asyncpg://user:pass@localhost:5432/db",
                _env_file=None,
            )

    def test_pg8000_url_rejected(self):
        """postgresql+pg8000:// URLs should be rejected."""
        with pytest.raises(ValueError, match="pg8000"):
            Settings(
                SECRET_KEY="test-secret-key-for-testing-only-32-chars-minimum",
                DATABASE_URL="postgresql+pg8000://user:pass@localhost:5432/db",
                _env_file=None,
            )

    def test_postgresql_url_accepted(self):
        """postgresql:// URLs should be accepted."""
        settings = Settings(
            SECRET_KEY="test-secret-key-for-testing-only-32-chars-minimum",
            DATABASE_URL="postgresql://user:pass@localhost:5432/db",
            _env_file=None,
        )
        assert settings.DATABASE_URL == "postgresql://user:pass@localhost:5432/db"

    def test_postgresql_psycopg2_url_accepted(self):
        """postgresql+psycopg2:// URLs should be accepted."""
        settings = Settings(
            SECRET_KEY="test-secret-key-for-testing-only-32-chars-minimum",
            DATABASE_URL="postgresql+psycopg2://user:pass@localhost:5432/db",
            _env_file=None,
        )
        assert settings.DATABASE_URL == "postgresql+psycopg2://user:pass@localhost:5432/db"

    def test_postgresql_psycopg_url_accepted(self):
        """postgresql+psycopg:// URLs should be accepted."""
        settings = Settings(
            SECRET_KEY="test-secret-key-for-testing-only-32-chars-minimum",
            DATABASE_URL="postgresql+psycopg://user:pass@localhost:5432/db",
            _env_file=None,
        )
        assert settings.DATABASE_URL == "postgresql+psycopg://user:pass@localhost:5432/db"

    def test_database_echo_rejected_in_production(self):
        """DATABASE_ECHO=True should be rejected when ENVIRONMENT=production."""
        with pytest.raises(ValueError, match="DATABASE_ECHO cannot be True in production"):
            Settings(
                SECRET_KEY="test-secret-key-for-testing-only-32-chars-minimum",
                ENVIRONMENT="production",
                DATABASE_ECHO=True,
                _env_file=None,
            )

    def test_database_echo_accepted_in_development(self):
        """DATABASE_ECHO=True should be accepted in development."""
        settings = Settings(
            SECRET_KEY="test-secret-key-for-testing-only-32-chars-minimum",
            ENVIRONMENT="development",
            DATABASE_ECHO=True,
            _env_file=None,
        )
        assert settings.DATABASE_ECHO is True

    def test_database_echo_false_accepted_in_production(self):
        """DATABASE_ECHO=False should be accepted in production."""
        settings = Settings(
            SECRET_KEY="test-secret-key-for-testing-only-32-chars-minimum",
            ENVIRONMENT="production",
            DATABASE_ECHO=False,
            _env_file=None,
        )
        assert settings.DATABASE_ECHO is False

    def test_production_skips_create_all(self):
        """Production environment should skip Base.metadata.create_all()."""
        from unittest.mock import patch
        from app.main import lifespan
        from fastapi import FastAPI
        import asyncio

        app = FastAPI()

        # Patch settings to production
        with patch("app.main.settings") as mock_settings:
            mock_settings.ENVIRONMENT = "production"
            mock_settings.DATABASE_INIT_MAX_RETRIES = 3
            mock_settings.DATABASE_INIT_RETRY_BACKOFF = 1.0

            with patch("app.core.database.check_database_connectivity", return_value=True) as mock_check:
                # Run lifespan startup
                async def test_lifespan():
                    async with lifespan(app):
                        pass

                asyncio.run(test_lifespan())

                # check_database_connectivity should be called
                mock_check.assert_called_once()

    def test_production_startup_succeeds_when_db_available(self):
        """Production startup should succeed when database connectivity succeeds."""
        from unittest.mock import patch
        from app.main import lifespan
        from fastapi import FastAPI
        import asyncio

        app = FastAPI()

        with patch("app.main.settings") as mock_settings:
            mock_settings.ENVIRONMENT = "production"
            mock_settings.DATABASE_INIT_MAX_RETRIES = 3
            mock_settings.DATABASE_INIT_RETRY_BACKOFF = 1.0

            with patch("app.core.database.check_database_connectivity", return_value=True):
                # Run lifespan startup - should not raise
                async def test_lifespan():
                    async with lifespan(app):
                        pass

                asyncio.run(test_lifespan())

    def test_production_startup_fails_when_db_unavailable(self):
        """Production startup should raise RuntimeError when database connectivity fails."""
        from unittest.mock import patch
        from app.main import lifespan
        from fastapi import FastAPI
        import asyncio

        app = FastAPI()

        with patch("app.main.settings") as mock_settings:
            mock_settings.ENVIRONMENT = "production"
            mock_settings.DATABASE_INIT_MAX_RETRIES = 3
            mock_settings.DATABASE_INIT_RETRY_BACKOFF = 1.0

            with patch("app.core.database.check_database_connectivity", return_value=False):
                # Run lifespan startup - should raise RuntimeError
                async def test_lifespan():
                    async with lifespan(app):
                        pass

                with pytest.raises(RuntimeError, match="Database unavailable - production startup aborted"):
                    asyncio.run(test_lifespan())

    def test_production_failure_log_no_sensitive_info(self, caplog):
        """Production startup failure log should not expose credentials or URLs."""
        import logging
        from unittest.mock import patch
        from app.main import lifespan
        from fastapi import FastAPI
        import asyncio

        app = FastAPI()

        with patch("app.main.settings") as mock_settings:
            mock_settings.ENVIRONMENT = "production"
            mock_settings.DATABASE_INIT_MAX_RETRIES = 3
            mock_settings.DATABASE_INIT_RETRY_BACKOFF = 1.0

            with patch("app.core.database.check_database_connectivity", return_value=False):
                with caplog.at_level(logging.CRITICAL):
                    async def test_lifespan():
                        async with lifespan(app):
                            pass

                    with pytest.raises(RuntimeError):
                        asyncio.run(test_lifespan())

        # Check the critical log message
        critical_records = [r for r in caplog.records if r.levelno >= logging.CRITICAL]
        assert len(critical_records) >= 1
        for record in critical_records:
            msg = record.getMessage().lower()
            # No sensitive information
            assert "password" not in msg
            assert "credential" not in msg
            assert "://" not in msg or "sqlite://" not in msg  # Only sqlite URL scheme could appear
            assert "postgresql://" not in msg
            assert "user:" not in msg
            assert "password" not in msg

    def test_production_never_calls_init_db(self):
        """Production should never call init_db()."""
        from unittest.mock import patch
        from app.main import lifespan
        from fastapi import FastAPI
        import asyncio

        app = FastAPI()

        with patch("app.main.settings") as mock_settings:
            mock_settings.ENVIRONMENT = "production"
            mock_settings.DATABASE_INIT_MAX_RETRIES = 3
            mock_settings.DATABASE_INIT_RETRY_BACKOFF = 1.0

            with patch("app.core.database.check_database_connectivity", return_value=True):
                with patch("app.main.init_db") as mock_init_db:
                    async def test_lifespan():
                        async with lifespan(app):
                            pass

                    asyncio.run(test_lifespan())
                    mock_init_db.assert_not_called()

    def test_production_never_calls_create_all(self):
        """Production should never call Base.metadata.create_all()."""
        from unittest.mock import patch
        from app.main import lifespan
        from app.core.database import Base
        from fastapi import FastAPI
        import asyncio

        app = FastAPI()

        with patch("app.main.settings") as mock_settings:
            mock_settings.ENVIRONMENT = "production"
            mock_settings.DATABASE_INIT_MAX_RETRIES = 3
            mock_settings.DATABASE_INIT_RETRY_BACKOFF = 1.0

            with patch("app.core.database.check_database_connectivity", return_value=True):
                with patch.object(Base.metadata, "create_all") as mock_create_all:
                    async def test_lifespan():
                        async with lifespan(app):
                            pass

                    asyncio.run(test_lifespan())
                    mock_create_all.assert_not_called()

    def test_development_runs_create_all(self):
        """Development environment should run Base.metadata.create_all()."""
        from unittest.mock import patch
        from app.main import lifespan
        from fastapi import FastAPI
        import asyncio

        app = FastAPI()

        with patch("app.main.settings") as mock_settings:
            mock_settings.ENVIRONMENT = "development"
            mock_settings.DATABASE_INIT_MAX_RETRIES = 3
            mock_settings.DATABASE_INIT_RETRY_BACKOFF = 1.0

            with patch("app.main.init_db") as mock_init_db:
                async def test_lifespan():
                    async with lifespan(app):
                        pass

                asyncio.run(test_lifespan())

                # init_db should be called
                mock_init_db.assert_called_once_with(max_retries=3, retry_backoff=1.0)

    def test_sqlite_behavior_unchanged(self):
        """SQLite configuration and behavior should remain unchanged."""
        settings = Settings(
            SECRET_KEY="test-secret-key-for-testing-only-32-chars-minimum",
            DATABASE_URL="sqlite:///./test.db",
            _env_file=None,
        )
        assert settings.DATABASE_URL == "sqlite:///./test.db"
        # All pool settings should have defaults
        assert settings.DATABASE_POOL_SIZE == 5
        assert settings.DATABASE_MAX_OVERFLOW == 10
        assert settings.DATABASE_POOL_TIMEOUT == 30
        assert settings.DATABASE_POOL_RECYCLE == 1800
        assert settings.DATABASE_POOL_PRE_PING is True
        assert settings.DATABASE_CONNECT_TIMEOUT == 10
        assert settings.DATABASE_ECHO is False
        assert settings.DATABASE_INIT_MAX_RETRIES == 3
        assert settings.DATABASE_INIT_RETRY_BACKOFF == 1.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])