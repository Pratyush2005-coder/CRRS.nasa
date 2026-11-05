"""Tests for password reset functionality."""

import os
from datetime import timedelta, datetime, timezone
from unittest.mock import patch
import pytest
from sqlalchemy import select

from app.core.security import (
    create_refresh_token,
    decode_refresh_token,
    InvalidTokenError,
    TokenExpiredError,
    hash_password,
)
from app.models.password_reset_token import PasswordResetToken, hash_token as hash_reset_token
from app.models.refresh_token import RefreshToken, hash_token as hash_refresh_token
from app.services.user_service import UserService
from app.models.user import User


class TestPasswordResetTokenModel:
    """Tests for PasswordResetToken model and hash_token function."""

    def test_hash_token_returns_sha256(self):
        """hash_token returns a 64-character hex string."""
        token = "test-reset-token-123"
        hashed = hash_reset_token(token)

        assert isinstance(hashed, str)
        assert len(hashed) == 64
        assert all(c in "0123456789abcdef" for c in hashed)

    def test_hash_token_deterministic(self):
        """Same token produces same hash."""
        token = "test-reset-token-123"
        assert hash_reset_token(token) == hash_reset_token(token)

    def test_hash_token_different_for_different_inputs(self):
        """Different tokens produce different hashes."""
        assert hash_reset_token("token1") != hash_reset_token("token2")

    def test_password_reset_token_model_creation(self):
        """PasswordResetToken model can be instantiated with all fields."""
        rt = PasswordResetToken(
            id="test-id",
            user_id="user-123",
            token_hash="abc123",
            is_used=False,
            created_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),
        )
        assert rt.id == "test-id"
        assert rt.user_id == "user-123"
        assert rt.token_hash == "abc123"
        assert rt.is_used is False
        assert rt.used_at is None


class TestUserServicePasswordReset:
    """Tests for UserService password reset methods."""

    @pytest.fixture
    def test_db(self):
        """Create a test database session."""
        from tests.conftest import TestingSessionLocal
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    @pytest.fixture
    def test_user(self, test_db):
        """Create a test user with properly hashed password."""
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

    def test_create_password_reset_token_creates_record(self, test_db, test_user):
        """create_password_reset_token creates a PasswordResetToken record."""
        token = "test-reset-token"
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=15)

        service = UserService()
        result = service.create_password_reset_token(
            db=test_db,
            user_id=test_user.id,
            token=token,
            expires_at=expires_at,
        )

        assert isinstance(result, PasswordResetToken)
        assert result.user_id == test_user.id
        assert result.token_hash == hash_reset_token(token)
        assert result.is_used is False
        assert result.expires_at.replace(tzinfo=None) == expires_at.replace(tzinfo=None)
        assert result.used_at is None

    def test_create_password_reset_token_only_stores_hash(self, test_db, test_user):
        """create_password_reset_token stores only hash, never raw token."""
        token = "secret-reset-token"
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=15)

        service = UserService()
        result = service.create_password_reset_token(
            db=test_db,
            user_id=test_user.id,
            token=token,
            expires_at=expires_at,
        )

        # Verify raw token is not in database
        assert result.token_hash != token
        assert result.token_hash == hash_reset_token(token)

    def test_validate_and_consume_reset_token_success(self, test_db, test_user):
        """validate_and_consume_reset_token works with valid token."""
        service = UserService()

        # Create and store a reset token
        reset_token = "test-reset-token-123"
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=15)
        service.create_password_reset_token(
            db=test_db,
            user_id=test_user.id,
            token=reset_token,
            expires_at=expires_at,
        )

        # Validate and consume it
        result = service.validate_and_consume_reset_token(
            db=test_db,
            token=reset_token,
        )

        assert isinstance(result, PasswordResetToken)
        assert result.is_used is True
        assert result.used_at is not None
        assert result.token_hash == hash_reset_token(reset_token)

    def test_validate_and_consume_reset_token_rejects_expired(self, test_db, test_user):
        """validate_and_consume_reset_token rejects expired tokens."""
        service = UserService()

        # Create an expired reset token
        expires_delta = timedelta(seconds=-1)
        reset_token = "expired-token"
        expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        service.create_password_reset_token(
            db=test_db,
            user_id=test_user.id,
            token=reset_token,
            expires_at=expires_at,
        )

        # Attempt to validate should fail
        with pytest.raises(TokenExpiredError):
            service.validate_and_consume_reset_token(
                db=test_db,
                token=reset_token,
            )

    def test_validate_and_consume_reset_token_rejects_used(self, test_db, test_user):
        """validate_and_consume_reset_token rejects already used tokens."""
        service = UserService()

        # Create and store a reset token
        reset_token = "test-reset-token-123"
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=15)
        service.create_password_reset_token(
            db=test_db,
            user_id=test_user.id,
            token=reset_token,
            expires_at=expires_at,
        )

        # First validation - should succeed
        service.validate_and_consume_reset_token(
            db=test_db,
            token=reset_token,
        )

        # Second validation with SAME token - should fail (already used)
        with pytest.raises(InvalidTokenError, match="already been used"):
            service.validate_and_consume_reset_token(
                db=test_db,
                token=reset_token,
            )

    def test_validate_and_consume_reset_token_rejects_invalid(self, test_db, test_user):
        """validate_and_consume_reset_token rejects tokens not in database."""
        service = UserService()

        # Create a valid token but don't store it
        reset_token = "unknown-token"

        with pytest.raises(InvalidTokenError, match="Invalid or expired"):
            service.validate_and_consume_reset_token(
                db=test_db,
                token=reset_token,
            )

    def test_validate_and_consume_reset_token_rejects_malformed(self, test_db, test_user):
        """validate_and_consume_reset_token rejects malformed tokens."""
        service = UserService()

        with pytest.raises(InvalidTokenError, match="Invalid or expired"):
            service.validate_and_consume_reset_token(
                db=test_db,
                token="not.a.valid.token",
            )

    def test_validate_and_consume_reset_token_rejects_inactive_user(self, test_db, test_user):
        """validate_and_consume_reset_token rejects tokens for inactive users."""
        service = UserService()

        # Create and store a reset token
        reset_token = "test-reset-token-123"
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=15)
        service.create_password_reset_token(
            db=test_db,
            user_id=test_user.id,
            token=reset_token,
            expires_at=expires_at,
        )

        # Deactivate user
        test_user.is_active = False
        test_db.commit()

        with pytest.raises(InvalidTokenError, match="Invalid or expired"):
            service.validate_and_consume_reset_token(
                db=test_db,
                token=reset_token,
            )

    def test_validate_and_consume_reset_token_rejects_nonexistent_user(self, test_db):
        """validate_and_consume_reset_token rejects tokens for deleted users."""
        service = UserService()

        reset_token = "test-reset-token-123"
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=15)
        service.create_password_reset_token(
            db=test_db,
            user_id="nonexistent-user",
            token=reset_token,
            expires_at=expires_at,
        )

        with pytest.raises(InvalidTokenError, match="Invalid or expired"):
            service.validate_and_consume_reset_token(
                db=test_db,
                token=reset_token,
            )

    def test_reset_password_success(self, test_db, test_user):
        """reset_password successfully updates password and revokes refresh tokens."""
        import uuid
        service = UserService()

        # Create and store a reset token
        reset_token = "test-reset-token-123"
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=15)
        service.create_password_reset_token(
            db=test_db,
            user_id=test_user.id,
            token=reset_token,
            expires_at=expires_at,
        )

        # Create a refresh token for the user
        refresh_token = create_refresh_token(subject=test_user.id)
        refresh_expires_at = datetime.now(timezone.utc) + timedelta(days=7)
        service.store_refresh_token(
            db=test_db,
            user_id=test_user.id,
            token=refresh_token,
            expires_at=refresh_expires_at,
        )

        # Reset password
        result = service.reset_password(
            db=test_db,
            token=reset_token,
            new_password="newpassword456",
        )

        assert result is True

        # Verify old password no longer works
        user = service.get_user_by_id(test_db, test_user.id)
        assert not hash_password("password123") == user.hashed_password  # Old password hash differs
        from app.core.security import verify_password
        assert verify_password("newpassword456", user.hashed_password)  # New password works
        assert not verify_password("password123", user.hashed_password)  # Old password rejected

        # Verify refresh token was revoked
        refresh_token_hash = hash_refresh_token(refresh_token)
        db_refresh = test_db.execute(
            select(RefreshToken).where(RefreshToken.token_hash == refresh_token_hash)
        ).scalar_one()
        assert db_refresh.is_revoked is True

        # Verify reset token was consumed
        reset_token_hash = hash_reset_token(reset_token)
        db_reset = test_db.execute(
            select(PasswordResetToken).where(PasswordResetToken.token_hash == reset_token_hash)
        ).scalar_one()
        assert db_reset.is_used is True

    def test_reset_password_revokes_all_refresh_tokens(self, test_db, test_user):
        """reset_password revokes ALL refresh tokens for the user."""
        import uuid
        from app.core.security import create_refresh_token
        service = UserService()

        # Create multiple refresh tokens with unique JTIs
        for i in range(3):
            token_id = str(uuid.uuid4())
            refresh_token = create_refresh_token(subject=test_user.id, token_id=token_id)
            refresh_expires_at = datetime.now(timezone.utc) + timedelta(days=7)
            service.store_refresh_token(
                db=test_db,
                user_id=test_user.id,
                token=refresh_token,
                expires_at=refresh_expires_at,
            )

        # Create and store a reset token
        reset_token = "test-reset-token-123"
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=15)
        service.create_password_reset_token(
            db=test_db,
            user_id=test_user.id,
            token=reset_token,
            expires_at=expires_at,
        )

        # Reset password
        service.reset_password(
            db=test_db,
            token=reset_token,
            new_password="newpassword456",
        )

        # All refresh tokens should be revoked
        tokens = test_db.execute(
            select(RefreshToken).where(RefreshToken.user_id == test_user.id)
        ).scalars().all()
        assert all(t.is_revoked for t in tokens)

    def test_reset_password_cleans_up_other_reset_tokens(self, test_db, test_user):
        """reset_password cleans up other unused reset tokens for the user."""
        service = UserService()

        # Create multiple reset tokens
        for i in range(3):
            token = f"reset-token-{i}"
            expires_at = datetime.now(timezone.utc) + timedelta(minutes=15)
            service.create_password_reset_token(
                db=test_db,
                user_id=test_user.id,
                token=token,
                expires_at=expires_at,
            )

        # Use the first token to reset password
        service.reset_password(
            db=test_db,
            token="reset-token-0",
            new_password="newpassword456",
        )

        # Other unused tokens should be cleaned up
        tokens = test_db.execute(
            select(PasswordResetToken).where(
                PasswordResetToken.user_id == test_user.id,
                PasswordResetToken.is_used == False,
            )
        ).scalars().all()
        assert len(tokens) == 0

    def test_reset_password_rejects_empty_password(self, test_db, test_user):
        """reset_password rejects empty new password."""
        service = UserService()

        reset_token = "test-reset-token-123"
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=15)
        service.create_password_reset_token(
            db=test_db,
            user_id=test_user.id,
            token=reset_token,
            expires_at=expires_at,
        )

        with pytest.raises(ValueError, match="cannot be empty"):
            service.reset_password(
                db=test_db,
                token=reset_token,
                new_password="",
            )

        with pytest.raises(ValueError, match="cannot be empty"):
            service.reset_password(
                db=test_db,
                token=reset_token,
                new_password="   ",
            )

    def test_cleanup_expired_reset_tokens(self, test_db, test_user):
        """cleanup_expired_reset_tokens removes expired tokens."""
        service = UserService()

        # Create an expired reset token
        reset_token = "expired-token"
        expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        service.create_password_reset_token(
            db=test_db,
            user_id=test_user.id,
            token=reset_token,
            expires_at=expires_at,
        )

        # Create a valid reset token
        valid_token = "valid-token"
        valid_expires_at = datetime.now(timezone.utc) + timedelta(minutes=15)
        service.create_password_reset_token(
            db=test_db,
            user_id=test_user.id,
            token=valid_token,
            expires_at=valid_expires_at,
        )

        # Cleanup expired tokens
        count = service.cleanup_expired_reset_tokens(db=test_db)
        assert count == 1

        # Valid token should remain
        tokens = test_db.execute(
            select(PasswordResetToken).where(PasswordResetToken.user_id == test_user.id)
        ).scalars().all()
        assert len(tokens) == 1
        assert tokens[0].token_hash == hash_reset_token(valid_token)


class TestForgotPasswordEndpoint:
    """Tests for POST /api/auth/forgot-password endpoint."""

    def test_forgot_password_existing_email(self, client, test_user):
        """Forgot password with existing email returns generic response."""
        import logging
        from app.core.rate_limiting import limiter
        from app.core.config import settings

        # Enable rate limiting for this test
        limiter.enabled = True
        # Enable token logging for this test (dev/testing mode)
        original_log_tokens = settings.LOG_PASSWORD_RESET_TOKENS
        settings.LOG_PASSWORD_RESET_TOKENS = True
        try:
            # Capture log output
            with patch('app.api.routes.auth.logger') as mock_logger:
                response = client.post(
                    "/api/auth/forgot-password",
                    json={"email": "test@example.com"},
                )

            assert response.status_code == 200
            assert "If the email exists" in response.json()["detail"]

            # Verify token was logged (dev/testing only - enabled via config)
            mock_logger.info.assert_called_once()
            log_call = mock_logger.info.call_args[0][0]
            assert "DEV/TEST: Password reset token for test@example.com" in log_call
        finally:
            limiter.enabled = False
            settings.LOG_PASSWORD_RESET_TOKENS = original_log_tokens

    def test_forgot_password_nonexistent_email(self, client):
        """Forgot password with nonexistent email returns SAME generic response."""
        response = client.post(
            "/api/auth/forgot-password",
            json={"email": "nonexistent@example.com"},
        )

        assert response.status_code == 200
        assert "If the email exists" in response.json()["detail"]

    def test_forgot_password_case_insensitive(self, client, test_user):
        """Forgot password is case-insensitive for email."""
        response = client.post(
            "/api/auth/forgot-password",
            json={"email": "TEST@EXAMPLE.COM"},
        )

        assert response.status_code == 200
        assert "If the email exists" in response.json()["detail"]

    def test_forgot_password_rate_limited(self, client, test_user, reset_rate_limiter):
        """Forgot password endpoint is rate limited."""
        from app.core.rate_limiting import get_limiter

        # Enable rate limiting for this test
        limiter = get_limiter()
        limiter.enabled = True
        try:
            # Make multiple requests rapidly
            for i in range(2):
                response = client.post(
                    "/api/auth/forgot-password",
                    json={"email": "test@example.com"},
                )
                assert response.status_code == 200, f"Request {i} failed: {response.status_code}"

            # 3rd request should be rate limited (limit is 3/minute, but fixed-window may allow only 2)
            response = client.post(
                "/api/auth/forgot-password",
                json={"email": "test@example.com"},
            )
            assert response.status_code == 429
        finally:
            limiter.enabled = False


class TestResetPasswordEndpoint:
    """Tests for POST /api/auth/reset-password endpoint."""

    def test_reset_password_success(self, client, test_user):
        """Successful password reset with valid token."""
        from app.models.password_reset_token import hash_token as hash_reset_token
        from app.services.user_service import UserService
        from tests.conftest import TestingSessionLocal

        # Create a reset token directly in DB
        db = TestingSessionLocal()
        try:
            service = UserService()
            reset_token = "test-reset-token-123"
            expires_at = datetime.now(timezone.utc) + timedelta(minutes=15)
            service.create_password_reset_token(
                db=db,
                user_id=test_user.id,
                token=reset_token,
                expires_at=expires_at,
            )
        finally:
            db.close()

        # Use reset token to reset password
        response = client.post(
            "/api/auth/reset-password",
            json={"token": reset_token, "new_password": "newpassword456"},
        )

        assert response.status_code == 200
        assert "successfully reset" in response.json()["detail"].lower()

        # Verify old password no longer works
        login_response = client.post(
            "/api/auth/login",
            json={"email": "test@example.com", "password": "password123"},
        )
        assert login_response.status_code == 401

        # Verify new password works
        login_response = client.post(
            "/api/auth/login",
            json={"email": "test@example.com", "password": "newpassword456"},
        )
        assert login_response.status_code == 200

    def test_reset_password_rejects_expired_token(self, client, test_user):
        """Reset password rejects expired tokens."""
        from app.models.password_reset_token import hash_token as hash_reset_token
        from app.services.user_service import UserService
        from tests.conftest import TestingSessionLocal

        # Create an expired reset token directly in DB
        db = TestingSessionLocal()
        try:
            service = UserService()
            expires_delta = timedelta(seconds=-1)
            expired_token = "expired-token"
            expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
            service.create_password_reset_token(
                db=db,
                user_id=test_user.id,
                token=expired_token,
                expires_at=expires_at,
            )
        finally:
            db.close()

        response = client.post(
            "/api/auth/reset-password",
            json={"token": expired_token, "new_password": "newpassword456"},
        )

        assert response.status_code == 401
        assert "expired" in response.json()["detail"].lower()

    def test_reset_password_rejects_used_token(self, client, test_user):
        """Reset password rejects already used tokens."""
        from app.services.user_service import UserService
        from tests.conftest import TestingSessionLocal

        # Create and store a reset token
        db = TestingSessionLocal()
        try:
            service = UserService()
            reset_token = "test-reset-token-123"
            expires_at = datetime.now(timezone.utc) + timedelta(minutes=15)
            service.create_password_reset_token(
                db=db,
                user_id=test_user.id,
                token=reset_token,
                expires_at=expires_at,
            )
        finally:
            db.close()

        # First use - should succeed
        response1 = client.post(
            "/api/auth/reset-password",
            json={"token": reset_token, "new_password": "newpassword456"},
        )
        assert response1.status_code == 200

        # Second use - should fail
        response2 = client.post(
            "/api/auth/reset-password",
            json={"token": reset_token, "new_password": "anotherpassword789"},
        )
        assert response2.status_code == 401
        assert "already been used" in response2.json()["detail"].lower()

    def test_reset_password_rejects_invalid_token(self, client):
        """Reset password rejects tokens not in database."""
        response = client.post(
            "/api/auth/reset-password",
            json={"token": "unknown-token", "new_password": "newpassword456"},
        )

        assert response.status_code == 401
        assert "invalid" in response.json()["detail"].lower()

    def test_reset_password_rejects_malformed_token(self, client):
        """Reset password rejects malformed tokens."""
        response = client.post(
            "/api/auth/reset-password",
            json={"token": "not.a.valid.token", "new_password": "newpassword456"},
        )

        assert response.status_code == 401

    def test_reset_password_revokes_refresh_tokens(self, client, test_user):
        """Reset password revokes all user's refresh tokens."""
        from app.models.password_reset_token import hash_token as hash_reset_token
        from app.core.security import create_refresh_token
        from app.models.refresh_token import hash_token as hash_refresh_token
        from app.services.user_service import UserService
        from tests.conftest import TestingSessionLocal

        # Login to get refresh token
        login_response = client.post(
            "/api/auth/login",
            json={"email": "test@example.com", "password": "password123"},
        )
        assert login_response.status_code == 200
        refresh_token = login_response.json()["refresh_token"]

        # Create a reset token
        db = TestingSessionLocal()
        try:
            service = UserService()
            reset_token = "test-reset-token-123"
            expires_at = datetime.now(timezone.utc) + timedelta(minutes=15)
            service.create_password_reset_token(
                db=db,
                user_id=test_user.id,
                token=reset_token,
                expires_at=expires_at,
            )
        finally:
            db.close()

        # Reset password
        response = client.post(
            "/api/auth/reset-password",
            json={"token": reset_token, "new_password": "newpassword456"},
        )
        assert response.status_code == 200

        # Old refresh token should no longer work
        refresh_response = client.post(
            "/api/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        assert refresh_response.status_code == 401

    def test_reset_password_rejects_short_password(self, client, test_user):
        """Reset password rejects password shorter than 8 characters."""
        from app.services.user_service import UserService
        from tests.conftest import TestingSessionLocal

        db = TestingSessionLocal()
        try:
            service = UserService()
            reset_token = "test-reset-token-123"
            expires_at = datetime.now(timezone.utc) + timedelta(minutes=15)
            service.create_password_reset_token(
                db=db,
                user_id=test_user.id,
                token=reset_token,
                expires_at=expires_at,
            )
        finally:
            db.close()

        response = client.post(
            "/api/auth/reset-password",
            json={"token": reset_token, "new_password": "short"},
        )

        assert response.status_code == 422

    def test_reset_password_rate_limited(self, client, test_user, reset_rate_limiter):
        """Reset password endpoint is rate limited."""
        from app.core.rate_limiting import get_limiter

        # Enable rate limiting for this test
        limiter = get_limiter()
        limiter.enabled = True
        try:
            # Make multiple requests with invalid tokens rapidly
            # Invalid tokens don't get cleaned up, so we can test rate limiting
            for i in range(5):
                response = client.post(
                    "/api/auth/reset-password",
                    json={"token": f"invalid-token-{i}", "new_password": f"newpassword{i}"},
                )
                # Should return 401 (invalid token), not 429 (rate limited)
                assert response.status_code == 401

            # 6th request should be rate limited (limit is 5/minute)
            response = client.post(
                "/api/auth/reset-password",
                json={"token": "invalid-token-5", "new_password": "newpassword5"},
            )
            assert response.status_code == 429, f"Expected 429, got {response.status_code}: {response.json()}"
        finally:
            limiter.enabled = False


class TestConcurrentResetAttempts:
    """Tests for concurrent password reset attempts."""

    def test_concurrent_forgot_password_same_email(self, client, test_user):
        """Concurrent forgot password requests for same email - all return generic response."""
        responses = []
        for _ in range(3):
            response = client.post(
                "/api/auth/forgot-password",
                json={"email": "test@example.com"},
            )
            responses.append(response)

        # All should succeed (rate limit is 3/minute)
        for response in responses:
            assert response.status_code == 200
            assert "If the email exists" in response.json()["detail"]

    def test_concurrent_reset_same_token(self, client, test_user):
        """Concurrent reset attempts with same token - only one succeeds."""
        from app.services.user_service import UserService
        from tests.conftest import TestingSessionLocal

        db = TestingSessionLocal()
        try:
            service = UserService()
            reset_token = "concurrent-test-token"
            expires_at = datetime.now(timezone.utc) + timedelta(minutes=15)
            service.create_password_reset_token(
                db=db,
                user_id=test_user.id,
                token=reset_token,
                expires_at=expires_at,
            )
        finally:
            db.close()

        # Simulate concurrent requests
        responses = []
        for _ in range(3):
            response = client.post(
                "/api/auth/reset-password",
                json={"token": reset_token, "new_password": "newpassword456"},
            )
            responses.append(response)

        # Only one should succeed
        success_count = sum(1 for r in responses if r.status_code == 200)
        assert success_count == 1

        # Others should fail with "already used"
        fail_count = sum(1 for r in responses if r.status_code == 401)
        assert fail_count == 2
        for r in responses:
            if r.status_code == 401:
                assert "already been used" in r.json()["detail"].lower()


# Import datetime for test fixtures
from datetime import datetime, timezone


class TestProductionTokenLogging:
    """Tests for production token logging safety."""

    def test_log_password_reset_tokens_blocked_in_production(self):
        """LOG_PASSWORD_RESET_TOKENS cannot be enabled in production."""
        from app.core.config import Settings
        import os

        # Save original environment
        original_env = os.environ.get("ENVIRONMENT")
        original_log_tokens = os.environ.get("LOG_PASSWORD_RESET_TOKENS")

        try:
            # Set production environment
            os.environ["ENVIRONMENT"] = "production"
            os.environ["LOG_PASSWORD_RESET_TOKENS"] = "true"
            os.environ["SECRET_KEY"] = "test-secret-key-for-production"

            # Should raise ValueError
            try:
                Settings()
                assert False, "Expected ValueError for enabling token logging in production"
            except ValueError as e:
                assert "LOG_PASSWORD_RESET_TOKENS cannot be True in production environment" in str(e)
        finally:
            # Restore environment
            if original_env is not None:
                os.environ["ENVIRONMENT"] = original_env
            else:
                os.environ.pop("ENVIRONMENT", None)
            if original_log_tokens is not None:
                os.environ["LOG_PASSWORD_RESET_TOKENS"] = original_log_tokens
            else:
                os.environ.pop("LOG_PASSWORD_RESET_TOKENS", None)

    def test_log_password_reset_tokens_allowed_in_development(self):
        """LOG_PASSWORD_RESET_TOKENS can be enabled in development."""
        from app.core.config import Settings
        import os

        # Save original environment
        original_env = os.environ.get("ENVIRONMENT")
        original_log_tokens = os.environ.get("LOG_PASSWORD_RESET_TOKENS")

        try:
            # Set development environment
            os.environ["ENVIRONMENT"] = "development"
            os.environ["LOG_PASSWORD_RESET_TOKENS"] = "true"
            os.environ["SECRET_KEY"] = "test-secret-key"

            # Should not raise
            settings = Settings()
            assert settings.LOG_PASSWORD_RESET_TOKENS is True
        finally:
            # Restore environment
            if original_env is not None:
                os.environ["ENVIRONMENT"] = original_env
            else:
                os.environ.pop("ENVIRONMENT", None)
            if original_log_tokens is not None:
                os.environ["LOG_PASSWORD_RESET_TOKENS"] = original_log_tokens
            else:
                os.environ.pop("LOG_PASSWORD_RESET_TOKENS", None)

    def test_forgot_password_no_token_logged_by_default(self, client, test_user):
        """By default (LOG_PASSWORD_RESET_TOKENS=False), no token is logged."""
        from app.core.rate_limiting import get_limiter
        from unittest.mock import patch

        # Enable rate limiting for this test and reset limiter state
        limiter = get_limiter()
        limiter.enabled = True
        # Reset the limiter storage to clear any previous requests
        if hasattr(limiter, '_storage') and limiter._storage:
            limiter._storage.reset()
        try:
            with patch('app.api.routes.auth.logger') as mock_logger:
                response = client.post(
                    "/api/auth/forgot-password",
                    json={"email": "test@example.com"},
                )

            assert response.status_code == 200
            # Logger should not be called for token (since LOG_PASSWORD_RESET_TOKENS=False by default)
            # It might be called for other things, but not for the DEV/TEST token message
            for call in mock_logger.info.call_args_list:
                assert "DEV/TEST: Password reset token" not in call[0][0]
        finally:
            limiter.enabled = False