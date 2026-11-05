"""Comprehensive tests for Account Lockout functionality (Phase 4.8C.3)."""

import os
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import settings
from app.core.security import hash_password
from app.models.login_attempt import LoginAttempt
from app.models.user import User
from app.services.user_service import user_service
from app.scripts.cleanup_auth_artifacts import cleanup_auth_artifacts


class TestLoginAttemptModel:
    """Tests for LoginAttempt model creation and indexes."""

    @pytest.fixture
    def db_session(self, setup_test_db):
        from tests.conftest import TestingSessionLocal
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    def test_login_attempt_creation(self, db_session):
        """Test creating a LoginAttempt record."""
        attempt = LoginAttempt(
            email="test@example.com",
            ip_address="192.168.1.1",
            success=False,
            user_agent="Mozilla/5.0 Test Browser",
        )
        db_session.add(attempt)
        db_session.commit()
        db_session.refresh(attempt)

        assert attempt.id is not None
        assert len(attempt.id) == 36  # UUID v4
        assert attempt.email == "test@example.com"
        assert attempt.ip_address == "192.168.1.1"
        assert attempt.success is False
        assert attempt.user_agent == "Mozilla/5.0 Test Browser"
        assert attempt.attempted_at is not None
        # SQLite stores naive datetime; timezone is handled at application level

    def test_login_attempt_defaults(self, db_session):
        """Test LoginAttempt default values."""
        attempt = LoginAttempt(
            email="test@example.com",
            ip_address="192.168.1.1",
        )
        db_session.add(attempt)
        db_session.commit()

        assert attempt.success is False
        assert attempt.user_agent is None
        assert attempt.attempted_at is not None

    def test_login_attempt_indexes_exist(self, db_session):
        """Test that composite indexes are created."""
        from sqlalchemy import inspect
        inspector = inspect(db_session.bind)
        indexes = inspector.get_indexes("login_attempts")
        index_names = {idx["name"] for idx in indexes}

        expected_indexes = {
            "ix_login_attempts_email_ip",
            "ix_login_attempts_email_ip_attempted_at",
            "ix_login_attempts_attempted_at",
            "ix_login_attempts_id",  # Primary key index
        }
        for expected in expected_indexes:
            assert expected in index_names, f"Missing index: {expected}"

    def test_login_attempt_ipv6_support(self, db_session):
        """Test that IPv6 addresses are supported (45 char limit)."""
        ipv6 = "2001:0db8:85a3:0000:0000:8a2e:0370:7334"
        attempt = LoginAttempt(
            email="test@example.com",
            ip_address=ipv6,
            success=True,
        )
        db_session.add(attempt)
        db_session.commit()

        assert attempt.ip_address == ipv6


class TestUserServiceLockoutMethods:
    """Tests for UserService account lockout methods."""

    @pytest.fixture
    def test_db(self):
        from tests.conftest import TestingSessionLocal
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    def test_check_login_attempts_no_attempts(self, test_db):
        """check_login_attempts returns not locked for new email+IP."""
        is_locked, count, cooldown = user_service.check_login_attempts(
            test_db, "new@example.com", "192.168.1.100"
        )
        assert is_locked is False
        assert count == 0
        assert cooldown is None

    def test_check_login_attempts_below_threshold(self, test_db):
        """check_login_attempts returns not locked when below max attempts."""
        for i in range(3):
            user_service.record_login_attempt(
                test_db, "test@example.com", "192.168.1.1", success=False
            )

        is_locked, count, cooldown = user_service.check_login_attempts(
            test_db, "test@example.com", "192.168.1.1"
        )
        assert is_locked is False
        assert count == 3
        assert cooldown is None

    def test_check_login_attempts_at_threshold_triggers_lockout(self, test_db):
        """check_login_attempts returns locked when at max attempts."""
        for i in range(5):
            user_service.record_login_attempt(
                test_db, "test@example.com", "192.168.1.1", success=False
            )

        is_locked, count, cooldown = user_service.check_login_attempts(
            test_db, "test@example.com", "192.168.1.1"
        )
        assert is_locked is True
        assert count == 5
        assert cooldown is not None
        assert cooldown > 0
        assert cooldown <= settings.LOGIN_ATTEMPT_COOLDOWN_MINUTES

    def test_check_login_attempts_different_email_independent(self, test_db):
        """Different emails are tracked independently."""
        for i in range(5):
            user_service.record_login_attempt(
                test_db, "victim@example.com", "192.168.1.1", success=False
            )

        # Attacker's attempts shouldn't lock victim
        is_locked, count, cooldown = user_service.check_login_attempts(
            test_db, "attacker@example.com", "192.168.1.1"
        )
        assert is_locked is False
        assert count == 0

    def test_check_login_attempts_different_ip_independent(self, test_db):
        """Different IPs are tracked independently for same email."""
        for i in range(5):
            user_service.record_login_attempt(
                test_db, "test@example.com", "192.168.1.1", success=False
            )

        # Same email, different IP should not be locked
        is_locked, count, cooldown = user_service.check_login_attempts(
            test_db, "test@example.com", "192.168.1.2"
        )
        assert is_locked is False
        assert count == 0

    def test_check_login_attempts_sliding_window_expiration(self, test_db):
        """Old failed attempts outside window don't count."""
        # Manually create old attempts outside the window
        old_time = datetime.now(timezone.utc) - timedelta(minutes=settings.LOGIN_ATTEMPT_WINDOW_MINUTES + 10)
        for i in range(5):
            attempt = LoginAttempt(
                email="test@example.com",
                ip_address="192.168.1.1",
                success=False,
                attempted_at=old_time,
            )
            test_db.add(attempt)
        test_db.commit()

        # Should not be locked - old attempts expired
        is_locked, count, cooldown = user_service.check_login_attempts(
            test_db, "test@example.com", "192.168.1.1"
        )
        assert is_locked is False
        assert count == 0

    def test_check_login_attempts_cooldown_expiration(self, test_db):
        """Lockout expires after cooldown period."""
        # Create 5 failed attempts
        for i in range(5):
            user_service.record_login_attempt(
                test_db, "test@example.com", "192.168.1.1", success=False
            )

        # Verify locked
        is_locked, _, cooldown = user_service.check_login_attempts(
            test_db, "test@example.com", "192.168.1.1"
        )
        assert is_locked is True
        assert cooldown is not None

        # Manually set attempts to be old enough that cooldown expired
        attempts = test_db.execute(
            select(LoginAttempt).where(
                LoginAttempt.email == "test@example.com",
                LoginAttempt.ip_address == "192.168.1.1",
            )
        ).scalars().all()

        old_time = datetime.now(timezone.utc) - timedelta(
            minutes=settings.LOGIN_ATTEMPT_WINDOW_MINUTES + settings.LOGIN_ATTEMPT_COOLDOWN_MINUTES + 5
        )
        for attempt in attempts:
            attempt.attempted_at = old_time
        test_db.commit()

        # Should not be locked anymore
        is_locked, count, cooldown = user_service.check_login_attempts(
            test_db, "test@example.com", "192.168.1.1"
        )
        assert is_locked is False
        assert cooldown is None

    def test_record_login_attempt_creates_record(self, test_db):
        """record_login_attempt creates a new record."""
        attempt = user_service.record_login_attempt(
            test_db, "test@example.com", "192.168.1.1", success=False, user_agent="Test Agent"
        )

        assert attempt.id is not None
        assert attempt.email == "test@example.com"
        assert attempt.ip_address == "192.168.1.1"
        assert attempt.success is False
        assert attempt.user_agent == "Test Agent"

    def test_record_login_attempt_normalizes_email(self, test_db):
        """record_login_attempt normalizes email to lowercase."""
        attempt = user_service.record_login_attempt(
            test_db, "  TEST@EXAMPLE.COM  ", "192.168.1.1", success=True
        )
        assert attempt.email == "test@example.com"

    def test_record_login_attempt_success_tracks_correctly(self, test_db):
        """Successful attempts are recorded but don't trigger lockout."""
        # Record 5 failures
        for i in range(5):
            user_service.record_login_attempt(test_db, "test@example.com", "192.168.1.1", success=False)

        is_locked, _, _ = user_service.check_login_attempts(test_db, "test@example.com", "192.168.1.1")
        assert is_locked is True

        # Record a success - should not reset the lockout
        user_service.record_login_attempt(test_db, "test@example.com", "192.168.1.1", success=True)

        is_locked, _, _ = user_service.check_login_attempts(test_db, "test@example.com", "192.168.1.1")
        assert is_locked is True

    def test_cleanup_login_attempts_removes_old_records(self, test_db):
        """cleanup_login_attempts removes records older than retention period."""
        # Create old records beyond retention
        retention_minutes = (
            settings.LOGIN_ATTEMPT_WINDOW_MINUTES
            + settings.LOGIN_ATTEMPT_COOLDOWN_MINUTES
            + 60
        )
        old_time = datetime.now(timezone.utc) - timedelta(minutes=retention_minutes + 10)

        for i in range(3):
            attempt = LoginAttempt(
                email="old@example.com",
                ip_address="192.168.1.1",
                success=False,
                attempted_at=old_time,
            )
            test_db.add(attempt)

        # Create recent records
        for i in range(2):
            attempt = LoginAttempt(
                email="recent@example.com",
                ip_address="192.168.1.1",
                success=False,
                attempted_at=datetime.now(timezone.utc),
            )
            test_db.add(attempt)
        test_db.commit()

        # Run cleanup
        deleted = user_service.cleanup_login_attempts(test_db)

        assert deleted == 3

        # Verify old records gone, recent remain
        remaining = test_db.execute(select(LoginAttempt)).scalars().all()
        assert len(remaining) == 2
        assert all(a.email == "recent@example.com" for a in remaining)

    def test_cleanup_login_attempts_batching(self, test_db, monkeypatch):
        """cleanup_login_attempts respects batch size."""
        monkeypatch.setattr(settings, "AUTH_CLEANUP_BATCH_SIZE", 2)

        retention_minutes = (
            settings.LOGIN_ATTEMPT_WINDOW_MINUTES
            + settings.LOGIN_ATTEMPT_COOLDOWN_MINUTES
            + 60
        )
        old_time = datetime.now(timezone.utc) - timedelta(minutes=retention_minutes + 10)

        for i in range(5):
            attempt = LoginAttempt(
                email=f"old{i}@example.com",
                ip_address="192.168.1.1",
                success=False,
                attempted_at=old_time,
            )
            test_db.add(attempt)
        test_db.commit()

        deleted = user_service.cleanup_login_attempts(test_db)
        assert deleted == 5

        remaining = test_db.execute(select(LoginAttempt)).scalars().all()
        assert len(remaining) == 0

    def test_cleanup_login_attempts_idempotent(self, test_db):
        """Running cleanup twice produces same result."""
        retention_minutes = (
            settings.LOGIN_ATTEMPT_WINDOW_MINUTES
            + settings.LOGIN_ATTEMPT_COOLDOWN_MINUTES
            + 60
        )
        old_time = datetime.now(timezone.utc) - timedelta(minutes=retention_minutes + 10)

        for i in range(3):
            attempt = LoginAttempt(
                email=f"old{i}@example.com",
                ip_address="192.168.1.1",
                success=False,
                attempted_at=old_time,
            )
            test_db.add(attempt)
        test_db.commit()

        deleted1 = user_service.cleanup_login_attempts(test_db)
        deleted2 = user_service.cleanup_login_attempts(test_db)

        assert deleted1 == 3
        assert deleted2 == 0


class TestConfigurationValidation:
    """Tests for account lockout configuration validators."""

    def test_login_attempt_max_attempts_positive(self):
        """LOGIN_ATTEMPT_MAX_ATTEMPTS accepts positive values."""
        from app.core.config import Settings
        os.environ["SECRET_KEY"] = "test"
        os.environ["LOGIN_ATTEMPT_MAX_ATTEMPTS"] = "5"
        os.environ["LOGIN_ATTEMPT_WINDOW_MINUTES"] = "15"
        os.environ["LOGIN_ATTEMPT_COOLDOWN_MINUTES"] = "15"
        s = Settings()
        assert s.LOGIN_ATTEMPT_MAX_ATTEMPTS == 5

    def test_login_attempt_max_attempts_zero_rejected(self):
        """LOGIN_ATTEMPT_MAX_ATTEMPTS rejects zero."""
        from app.core.config import Settings
        os.environ["SECRET_KEY"] = "test"
        os.environ["LOGIN_ATTEMPT_MAX_ATTEMPTS"] = "0"
        with pytest.raises(ValueError, match="must be positive"):
            Settings()

    def test_login_attempt_max_attempts_negative_rejected(self):
        """LOGIN_ATTEMPT_MAX_ATTEMPTS rejects negative values."""
        from app.core.config import Settings
        os.environ["SECRET_KEY"] = "test"
        os.environ["LOGIN_ATTEMPT_MAX_ATTEMPTS"] = "-1"
        with pytest.raises(ValueError, match="must be positive"):
            Settings()

    def test_login_attempt_window_minutes_positive(self):
        """LOGIN_ATTEMPT_WINDOW_MINUTES accepts positive values."""
        from app.core.config import Settings
        os.environ["SECRET_KEY"] = "test"
        os.environ["LOGIN_ATTEMPT_WINDOW_MINUTES"] = "15"
        os.environ["LOGIN_ATTEMPT_MAX_ATTEMPTS"] = "5"
        os.environ["LOGIN_ATTEMPT_COOLDOWN_MINUTES"] = "15"
        s = Settings()
        assert s.LOGIN_ATTEMPT_WINDOW_MINUTES == 15

    def test_login_attempt_window_minutes_zero_rejected(self):
        """LOGIN_ATTEMPT_WINDOW_MINUTES rejects zero."""
        from app.core.config import Settings
        os.environ["SECRET_KEY"] = "test"
        os.environ["LOGIN_ATTEMPT_WINDOW_MINUTES"] = "0"
        with pytest.raises(ValueError, match="must be positive"):
            Settings()

    def test_login_attempt_cooldown_minutes_positive(self):
        """LOGIN_ATTEMPT_COOLDOWN_MINUTES accepts positive values."""
        from app.core.config import Settings
        os.environ["SECRET_KEY"] = "test"
        os.environ["LOGIN_ATTEMPT_COOLDOWN_MINUTES"] = "15"
        os.environ["LOGIN_ATTEMPT_MAX_ATTEMPTS"] = "5"
        os.environ["LOGIN_ATTEMPT_WINDOW_MINUTES"] = "15"
        s = Settings()
        assert s.LOGIN_ATTEMPT_COOLDOWN_MINUTES == 15

    def test_login_attempt_cooldown_minutes_zero_rejected(self):
        """LOGIN_ATTEMPT_COOLDOWN_MINUTES rejects zero."""
        from app.core.config import Settings
        os.environ["SECRET_KEY"] = "test"
        os.environ["LOGIN_ATTEMPT_COOLDOWN_MINUTES"] = "0"
        with pytest.raises(ValueError, match="must be positive"):
            Settings()


class TestCleanupScriptIntegration:
    """Tests for cleanup_auth_artifacts script integration."""

    @pytest.fixture
    def test_db(self, setup_test_db):
        from tests.conftest import TestingSessionLocal
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    @pytest.fixture
    def test_user(self, test_db):
        user = User(
            id="test-user-123",
            email="test@example.com",
            hashed_password=hash_password("password123"),
            role="user",
            is_active=True,
        )
        test_db.add(user)
        test_db.commit()
        test_db.refresh(user)
        return user

    def test_cleanup_auth_artifacts_dry_run_includes_login_attempts(self, test_db, test_user):
        """cleanup_auth_artifacts dry_run reports login attempts."""
        # Create old login attempts
        retention_minutes = (
            settings.LOGIN_ATTEMPT_WINDOW_MINUTES
            + settings.LOGIN_ATTEMPT_COOLDOWN_MINUTES
            + 60
        )
        old_time = datetime.now(timezone.utc) - timedelta(minutes=retention_minutes + 10)

        for i in range(3):
            attempt = LoginAttempt(
                email="old@example.com",
                ip_address="192.168.1.1",
                success=False,
                attempted_at=old_time,
            )
            test_db.add(attempt)
        test_db.commit()

        results = cleanup_auth_artifacts(test_db, dry_run=True, verbose=False)

        assert "login_attempts" in results
        assert results["login_attempts"] == 3

        # Verify nothing was actually deleted
        remaining = test_db.execute(select(LoginAttempt)).scalars().all()
        assert len(remaining) == 3

    def test_cleanup_auth_artifacts_actual_deletion_includes_login_attempts(self, test_db, test_user):
        """cleanup_auth_artifacts actually deletes login attempts."""
        retention_minutes = (
            settings.LOGIN_ATTEMPT_WINDOW_MINUTES
            + settings.LOGIN_ATTEMPT_COOLDOWN_MINUTES
            + 60
        )
        old_time = datetime.now(timezone.utc) - timedelta(minutes=retention_minutes + 10)

        for i in range(3):
            attempt = LoginAttempt(
                email="old@example.com",
                ip_address="192.168.1.1",
                success=False,
                attempted_at=old_time,
            )
            test_db.add(attempt)
        test_db.commit()

        results = cleanup_auth_artifacts(test_db, dry_run=False, verbose=False)

        assert results["login_attempts"] == 3

        remaining = test_db.execute(select(LoginAttempt)).scalars().all()
        assert len(remaining) == 0

    def test_cleanup_auth_artifacts_preserves_recent_login_attempts(self, test_db, test_user):
        """cleanup_auth_artifacts preserves recent login attempts."""
        # Create recent login attempts
        for i in range(2):
            attempt = LoginAttempt(
                email="recent@example.com",
                ip_address="192.168.1.1",
                success=False,
                attempted_at=datetime.now(timezone.utc),
            )
            test_db.add(attempt)
        test_db.commit()

        results = cleanup_auth_artifacts(test_db, dry_run=False, verbose=False)

        assert results["login_attempts"] == 0

        remaining = test_db.execute(select(LoginAttempt)).scalars().all()
        assert len(remaining) == 2


class TestLoginEndpointIntegration:
    """Tests for login endpoint account lockout integration."""

    @pytest.fixture
    def client(self):
        from tests.conftest import _create_test_client
        return _create_test_client()

    def test_login_success_records_attempt(self, client, setup_test_db):
        """Successful login records a success attempt."""
        from tests.conftest import TestingSessionLocal
        from app.models.login_attempt import LoginAttempt
        from app.core.security import hash_password
        from app.models.user import User

        db = TestingSessionLocal()
        try:
            user = User(
                id="test-user-123",
                email="test@example.com",
                hashed_password=hash_password("password123"),
                role="user",
                is_active=True,
            )
            db.add(user)
            db.commit()
        finally:
            db.close()

        response = client.post(
            "/api/auth/login",
            json={"email": "test@example.com", "password": "password123"},
        )
        assert response.status_code == 200

        # Verify success attempt recorded
        db = TestingSessionLocal()
        try:
            attempts = db.execute(
                select(LoginAttempt).where(
                    LoginAttempt.email == "test@example.com",
                    LoginAttempt.success == True,
                )
            ).scalars().all()
            assert len(attempts) == 1
            assert attempts[0].success is True
        finally:
            db.close()

    def test_login_wrong_password_records_failed_attempt(self, client, setup_test_db):
        """Wrong password records a failed attempt."""
        from tests.conftest import TestingSessionLocal
        from app.models.login_attempt import LoginAttempt
        from app.core.security import hash_password
        from app.models.user import User

        db = TestingSessionLocal()
        try:
            user = User(
                id="test-user-123",
                email="test@example.com",
                hashed_password=hash_password("password123"),
                role="user",
                is_active=True,
            )
            db.add(user)
            db.commit()
        finally:
            db.close()

        response = client.post(
            "/api/auth/login",
            json={"email": "test@example.com", "password": "wrongpassword"},
        )
        assert response.status_code == 401

        # Verify failed attempt recorded
        db = TestingSessionLocal()
        try:
            attempts = db.execute(
                select(LoginAttempt).where(
                    LoginAttempt.email == "test@example.com",
                    LoginAttempt.success == False,
                )
            ).scalars().all()
            assert len(attempts) == 1
            assert attempts[0].success is False
        finally:
            db.close()

    def test_login_nonexistent_email_records_failed_attempt(self, client, setup_test_db):
        """Non-existent email records a failed attempt (prevents email enumeration)."""
        from tests.conftest import TestingSessionLocal
        from app.models.login_attempt import LoginAttempt

        response = client.post(
            "/api/auth/login",
            json={"email": "nonexistent@example.com", "password": "password123"},
        )
        assert response.status_code == 401

        # Verify failed attempt recorded
        db = TestingSessionLocal()
        try:
            attempts = db.execute(
                select(LoginAttempt).where(
                    LoginAttempt.email == "nonexistent@example.com",
                    LoginAttempt.success == False,
                )
            ).scalars().all()
            assert len(attempts) == 1
            assert attempts[0].success is False
        finally:
            db.close()

    def test_login_generic_error_for_existing_and_nonexistent(self, client, setup_test_db):
        """Existing and non-existing emails return identical error responses."""
        from tests.conftest import TestingSessionLocal
        from app.core.security import hash_password
        from app.models.user import User

        db = TestingSessionLocal()
        try:
            user = User(
                id="test-user-123",
                email="existing@example.com",
                hashed_password=hash_password("password123"),
                role="user",
                is_active=True,
            )
            db.add(user)
            db.commit()
        finally:
            db.close()

        # Test existing email with wrong password
        resp_existing = client.post(
            "/api/auth/login",
            json={"email": "existing@example.com", "password": "wrongpassword"},
        )

        # Test non-existent email
        resp_nonexistent = client.post(
            "/api/auth/login",
            json={"email": "nonexistent@example.com", "password": "password123"},
        )

        assert resp_existing.status_code == resp_nonexistent.status_code == 401
        assert resp_existing.json()["detail"] == resp_nonexistent.json()["detail"] == "Invalid credentials"

    def test_lockout_after_max_failed_attempts(self, client, setup_test_db):
        """Account locked after max failed attempts."""
        from tests.conftest import TestingSessionLocal
        from app.core.security import hash_password
        from app.models.user import User

        db = TestingSessionLocal()
        try:
            user = User(
                id="test-user-123",
                email="test@example.com",
                hashed_password=hash_password("password123"),
                role="user",
                is_active=True,
            )
            db.add(user)
            db.commit()
        finally:
            db.close()

        # Make 5 failed attempts
        for i in range(5):
            response = client.post(
                "/api/auth/login",
                json={"email": "test@example.com", "password": "wrongpassword"},
            )
            assert response.status_code == 401

        # 6th attempt should be locked
        response = client.post(
            "/api/auth/login",
            json={"email": "test@example.com", "password": "wrongpassword"},
        )
        assert response.status_code == 429
        assert "temporarily locked" in response.json()["detail"]
        assert "Retry-After" in response.headers

    def test_lockout_returns_retry_after_header(self, client, setup_test_db):
        """Locked response includes Retry-After header in seconds."""
        from tests.conftest import TestingSessionLocal
        from app.core.security import hash_password
        from app.models.user import User

        db = TestingSessionLocal()
        try:
            user = User(
                id="test-user-123",
                email="test@example.com",
                hashed_password=hash_password("password123"),
                role="user",
                is_active=True,
            )
            db.add(user)
            db.commit()
        finally:
            db.close()

        # Make 5 failed attempts
        for i in range(5):
            client.post(
                "/api/auth/login",
                json={"email": "test@example.com", "password": "wrongpassword"},
            )

        # 6th attempt
        response = client.post(
            "/api/auth/login",
            json={"email": "test@example.com", "password": "wrongpassword"},
        )
        assert response.status_code == 429
        assert "Retry-After" in response.headers
        retry_after = int(response.headers["Retry-After"])
        assert retry_after > 0
        assert retry_after <= settings.LOGIN_ATTEMPT_COOLDOWN_MINUTES * 60

    def test_different_ips_independent_lockout(self, client, setup_test_db, monkeypatch):
        """Different IPs have independent lockout tracking."""
        from tests.conftest import TestingSessionLocal
        from app.core.security import hash_password
        from app.models.user import User

        # Enable trusted proxy to test X-Forwarded-For behavior
        monkeypatch.setattr(settings, "BEHIND_TRUSTED_PROXY", True)

        db = TestingSessionLocal()
        try:
            user = User(
                id="test-user-123",
                email="test@example.com",
                hashed_password=hash_password("password123"),
                role="user",
                is_active=True,
            )
            db.add(user)
            db.commit()
        finally:
            db.close()

        # Make 5 failed attempts from IP 1
        for i in range(5):
            response = client.post(
                "/api/auth/login",
                json={"email": "test@example.com", "password": "wrongpassword"},
                headers={"X-Forwarded-For": "192.168.1.1"},
            )
            assert response.status_code == 401

        # Same email from IP 2 should not be locked
        response = client.post(
            "/api/auth/login",
            json={"email": "test@example.com", "password": "wrongpassword"},
            headers={"X-Forwarded-For": "192.168.1.2"},
        )
        assert response.status_code == 401  # Not locked

    def test_different_emails_independent_lockout(self, client, setup_test_db):
        """Different emails have independent lockout tracking."""
        from tests.conftest import TestingSessionLocal
        from app.core.security import hash_password
        from app.models.user import User

        db = TestingSessionLocal()
        try:
            user1 = User(
                id="test-user-1",
                email="user1@example.com",
                hashed_password=hash_password("password123"),
                role="user",
                is_active=True,
            )
            user2 = User(
                id="test-user-2",
                email="user2@example.com",
                hashed_password=hash_password("password123"),
                role="user",
                is_active=True,
            )
            db.add_all([user1, user2])
            db.commit()
        finally:
            db.close()

        # Make 5 failed attempts for user1
        for i in range(5):
            client.post(
                "/api/auth/login",
                json={"email": "user1@example.com", "password": "wrongpassword"},
            )

        # user2 should not be locked
        response = client.post(
            "/api/auth/login",
            json={"email": "user2@example.com", "password": "wrongpassword"},
        )
        assert response.status_code == 401  # Not locked

    def test_successful_login_after_failures_below_threshold(self, client, setup_test_db):
        """Successful login works after failures below threshold."""
        from tests.conftest import TestingSessionLocal
        from app.core.security import hash_password
        from app.models.user import User

        db = TestingSessionLocal()
        try:
            user = User(
                id="test-user-123",
                email="test@example.com",
                hashed_password=hash_password("password123"),
                role="user",
                is_active=True,
            )
            db.add(user)
            db.commit()
        finally:
            db.close()

        # Make 3 failed attempts (below threshold of 5)
        for i in range(3):
            client.post(
                "/api/auth/login",
                json={"email": "test@example.com", "password": "wrongpassword"},
            )

        # Successful login should work
        response = client.post(
            "/api/auth/login",
            json={"email": "test@example.com", "password": "password123"},
        )
        assert response.status_code == 200
        assert "access_token" in response.json()

    def test_missing_user_agent_handled(self, client, setup_test_db):
        """Missing User-Agent header is handled safely."""
        from tests.conftest import TestingSessionLocal
        from app.core.security import hash_password
        from app.models.user import User

        db = TestingSessionLocal()
        try:
            user = User(
                id="test-user-123",
                email="test@example.com",
                hashed_password=hash_password("password123"),
                role="user",
                is_active=True,
            )
            db.add(user)
            db.commit()
        finally:
            db.close()

        # Request without User-Agent
        response = client.post(
            "/api/auth/login",
            json={"email": "test@example.com", "password": "password123"},
            headers={"User-Agent": ""},  # Empty User-Agent
        )
        assert response.status_code == 200

    def test_xff_not_trusted_by_default(self, client, setup_test_db):
        """X-Forwarded-For is not trusted when BEHIND_TRUSTED_PROXY=False."""
        from tests.conftest import TestingSessionLocal
        from app.core.security import hash_password
        from app.models.user import User
        from app.models.login_attempt import LoginAttempt

        db = TestingSessionLocal()
        try:
            user = User(
                id="test-user-123",
                email="test@example.com",
                hashed_password=hash_password("password123"),
                role="user",
                is_active=True,
            )
            db.add(user)
            db.commit()
        finally:
            db.close()

        # Make 5 failed attempts with spoofed XFF
        for i in range(5):
            client.post(
                "/api/auth/login",
                json={"email": "test@example.com", "password": "wrongpassword"},
                headers={"X-Forwarded-For": "10.0.0.1"},  # Spoofed IP
            )

        # Real client IP (test client) should be tracked, not spoofed
        # 6th attempt with same spoofed XFF should be locked
        response = client.post(
            "/api/auth/login",
            json={"email": "test@example.com", "password": "wrongpassword"},
            headers={"X-Forwarded-For": "10.0.0.1"},
        )
        assert response.status_code == 429

        # Verify attempts were recorded (check what IP was actually used)
        db = TestingSessionLocal()
        try:
            attempts = db.execute(
                select(LoginAttempt).where(
                    LoginAttempt.email == "test@example.com",
                )
            ).scalars().all()
            # Should have 6 attempts recorded under the actual client IP
            assert len(attempts) == 6
            # All should be the same IP (the test client's actual IP)
            ips = {a.ip_address for a in attempts}
            assert len(ips) == 1
            # The IP should be the test client's real IP, not the spoofed XFF
            assert "10.0.0.1" not in ips
        finally:
            db.close()

    def test_locked_attempt_records_failed_attempt(self, client, setup_test_db):
        """Blocked attempts due to lockout are recorded as failures."""
        from tests.conftest import TestingSessionLocal
        from app.core.security import hash_password
        from app.models.user import User
        from app.models.login_attempt import LoginAttempt

        db = TestingSessionLocal()
        try:
            user = User(
                id="test-user-123",
                email="test@example.com",
                hashed_password=hash_password("password123"),
                role="user",
                is_active=True,
            )
            db.add(user)
            db.commit()
        finally:
            db.close()

        # Make 5 failed attempts
        for i in range(5):
            client.post(
                "/api/auth/login",
                json={"email": "test@example.com", "password": "wrongpassword"},
            )

        # 6th attempt - locked
        client.post(
            "/api/auth/login",
            json={"email": "test@example.com", "password": "wrongpassword"},
        )

        # Verify 6 failed attempts recorded (5 + 1 blocked)
        db = TestingSessionLocal()
        try:
            attempts = db.execute(
                select(LoginAttempt).where(
                    LoginAttempt.email == "test@example.com",
                    LoginAttempt.success == False,
                )
            ).scalars().all()
            assert len(attempts) == 6
        finally:
            db.close()

    def test_inactive_user_records_failed_attempt(self, client, setup_test_db):
        """Inactive user login attempt records failure."""
        from tests.conftest import TestingSessionLocal
        from app.core.security import hash_password
        from app.models.user import User
        from app.models.login_attempt import LoginAttempt

        db = TestingSessionLocal()
        try:
            user = User(
                id="test-user-123",
                email="test@example.com",
                hashed_password=hash_password("password123"),
                role="user",
                is_active=False,  # Inactive user
            )
            db.add(user)
            db.commit()
        finally:
            db.close()

        response = client.post(
            "/api/auth/login",
            json={"email": "test@example.com", "password": "password123"},
        )
        assert response.status_code == 401

        # Verify failed attempt recorded
        db = TestingSessionLocal()
        try:
            attempts = db.execute(
                select(LoginAttempt).where(
                    LoginAttempt.email == "test@example.com",
                    LoginAttempt.success == False,
                )
            ).scalars().all()
            assert len(attempts) == 1
        finally:
            db.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])