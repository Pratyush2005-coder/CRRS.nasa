"""Tests for refresh token management."""

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
    rotate_refresh_token,
    hash_password,
)
from app.models.refresh_token import RefreshToken, hash_token
from app.services.user_service import UserService
from app.models.user import User


class TestRefreshTokenModel:
    """Tests for RefreshToken model and hash_token function."""

    def test_hash_token_returns_sha256(self):
        """hash_token returns a 64-character hex string."""
        token = "test-refresh-token-123"
        hashed = hash_token(token)

        assert isinstance(hashed, str)
        assert len(hashed) == 64
        assert all(c in "0123456789abcdef" for c in hashed)

    def test_hash_token_deterministic(self):
        """Same token produces same hash."""
        token = "test-refresh-token-123"
        assert hash_token(token) == hash_token(token)

    def test_hash_token_different_for_different_inputs(self):
        """Different tokens produce different hashes."""
        assert hash_token("token1") != hash_token("token2")

    def test_refresh_token_model_creation(self):
        """RefreshToken model can be instantiated with all fields."""
        rt = RefreshToken(
            id="test-id",
            user_id="user-123",
            token_hash="abc123",
            is_revoked=False,
            created_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        )
        assert rt.id == "test-id"
        assert rt.user_id == "user-123"
        assert rt.token_hash == "abc123"
        assert rt.is_revoked is False
        assert rt.revoked_at is None


class TestRotateRefreshToken:
    """Tests for rotate_refresh_token security function."""

    def test_rotate_refresh_token_returns_new_pair(self):
        """rotate_refresh_token returns new token and new token ID."""
        new_token, new_token_id = rotate_refresh_token(
            subject="user-123",
            old_token_id="old-token-id",
        )

        assert isinstance(new_token, str)
        assert isinstance(new_token_id, str)
        assert len(new_token_id) == 36  # UUID format
        assert new_token != ""

    def test_rotate_refresh_token_includes_jti(self):
        """New refresh token includes jti claim."""
        new_token, new_token_id = rotate_refresh_token(
            subject="user-123",
            old_token_id="old-token-id",
        )

        payload = decode_refresh_token(new_token)
        assert payload["jti"] == new_token_id
        assert payload["sub"] == "user-123"
        assert payload["type"] == "refresh"

    def test_rotate_refresh_token_custom_expiry(self):
        """rotate_refresh_token respects custom expiry."""
        expires_delta = timedelta(hours=1)
        new_token, _ = rotate_refresh_token(
            subject="user-123",
            old_token_id="old-token-id",
            expires_delta=expires_delta,
        )

        payload = decode_refresh_token(new_token)
        now = datetime.now(timezone.utc)
        expected_exp = int((now + expires_delta).timestamp())
        assert payload["exp"] == expected_exp


class TestUserServiceRefreshTokens:
    """Tests for UserService refresh token methods."""

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

    def test_store_refresh_token_creates_record(self, test_db, test_user):
        """store_refresh_token creates a RefreshToken record."""
        token = "test-refresh-token"
        expires_at = datetime.now(timezone.utc) + timedelta(days=7)

        service = UserService()
        result = service.store_refresh_token(
            db=test_db,
            user_id=test_user.id,
            token=token,
            expires_at=expires_at,
        )

        assert isinstance(result, RefreshToken)
        assert result.user_id == test_user.id
        assert result.token_hash == hash_token(token)
        assert result.is_revoked is False
        # Compare naive datetimes (SQLite stores as naive UTC)
        assert result.expires_at.replace(tzinfo=None) == expires_at.replace(tzinfo=None)
        assert result.revoked_at is None

    def test_store_refresh_token_only_stores_hash(self, test_db, test_user):
        """store_refresh_token stores only hash, never raw token."""
        token = "secret-refresh-token"
        expires_at = datetime.now(timezone.utc) + timedelta(days=7)

        service = UserService()
        result = service.store_refresh_token(
            db=test_db,
            user_id=test_user.id,
            token=token,
            expires_at=expires_at,
        )

        # Verify raw token is not in database
        assert result.token_hash != token
        assert result.token_hash == hash_token(token)

    def test_validate_and_rotate_success(self, test_db, test_user):
        """validate_and_rotate_refresh_token works with valid token."""
        service = UserService()

        # Create and store a refresh token
        refresh_token = create_refresh_token(subject=test_user.id)
        expires_at = datetime.now(timezone.utc) + timedelta(days=7)
        service.store_refresh_token(
            db=test_db,
            user_id=test_user.id,
            token=refresh_token,
            expires_at=expires_at,
        )

        # Rotate it
        new_access, new_refresh, new_db_token = service.validate_and_rotate_refresh_token(
            db=test_db,
            token=refresh_token,
        )

        # Verify new tokens returned
        assert new_access != ""
        assert new_refresh != ""
        assert new_access != refresh_token
        assert new_refresh != refresh_token

        # Verify old token is revoked
        old_token = test_db.execute(
            select(RefreshToken).where(RefreshToken.token_hash == hash_token(refresh_token))
        ).scalar_one_or_none()
        assert old_token is not None
        assert old_token.is_revoked is True
        assert old_token.revoked_at is not None

        # Verify new token is stored
        assert new_db_token is not None
        assert new_db_token.is_revoked is False
        assert new_db_token.token_hash == hash_token(new_refresh)

    def test_validate_and_rotate_rejects_expired_token(self, test_db, test_user):
        """validate_and_rotate_refresh_token rejects expired tokens."""
        service = UserService()

        # Create an expired refresh token
        expires_delta = timedelta(seconds=-1)
        refresh_token = create_refresh_token(
            subject=test_user.id,
            expires_delta=expires_delta,
        )
        expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        service.store_refresh_token(
            db=test_db,
            user_id=test_user.id,
            token=refresh_token,
            expires_at=expires_at,
        )

        # Attempt to rotate should fail
        with pytest.raises(TokenExpiredError):
            service.validate_and_rotate_refresh_token(
                db=test_db,
                token=refresh_token,
            )

    def test_validate_and_rotate_rejects_revoked_token(self, test_db, test_user):
        """validate_and_rotate_refresh_token rejects revoked tokens."""
        service = UserService()

        # Create and store a refresh token
        refresh_token = create_refresh_token(subject=test_user.id)
        expires_at = datetime.now(timezone.utc) + timedelta(days=7)
        service.store_refresh_token(
            db=test_db,
            user_id=test_user.id,
            token=refresh_token,
            expires_at=expires_at,
        )

        # Manually revoke it
        token_hash = hash_token(refresh_token)
        db_token = test_db.execute(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        ).scalar_one()
        db_token.is_revoked = True
        db_token.revoked_at = datetime.now(timezone.utc)
        test_db.commit()

        # Attempt to rotate should fail
        with pytest.raises(InvalidTokenError, match="already used"):
            service.validate_and_rotate_refresh_token(
                db=test_db,
                token=refresh_token,
            )

    def test_validate_and_rotate_rejects_reused_token(self, test_db, test_user):
        """validate_and_rotate_refresh_token detects and rejects replay attacks."""
        service = UserService()

        # Create and store a refresh token
        refresh_token = create_refresh_token(subject=test_user.id)
        expires_at = datetime.now(timezone.utc) + timedelta(days=7)
        service.store_refresh_token(
            db=test_db,
            user_id=test_user.id,
            token=refresh_token,
            expires_at=expires_at,
        )

        # First rotation - should succeed
        new_access, new_refresh, _ = service.validate_and_rotate_refresh_token(
            db=test_db,
            token=refresh_token,
        )

        # Second rotation with SAME old token - should fail (replay attack)
        with pytest.raises(InvalidTokenError, match="already used"):
            service.validate_and_rotate_refresh_token(
                db=test_db,
                token=refresh_token,
            )

        # All user tokens should be revoked after replay attack
        tokens = test_db.execute(
            select(RefreshToken).where(RefreshToken.user_id == test_user.id)
        ).scalars().all()
        assert all(t.is_revoked for t in tokens)

    def test_validate_and_rotate_rejects_invalid_token(self, test_db, test_user):
        """validate_and_rotate_refresh_token rejects tokens not in database."""
        service = UserService()

        # Create a valid token but don't store it
        refresh_token = create_refresh_token(subject=test_user.id)

        with pytest.raises(InvalidTokenError, match="not found"):
            service.validate_and_rotate_refresh_token(
                db=test_db,
                token=refresh_token,
            )

    def test_validate_and_rotate_rejects_malformed_token(self, test_db, test_user):
        """validate_and_rotate_refresh_token rejects malformed tokens."""
        service = UserService()

        with pytest.raises(InvalidTokenError):
            service.validate_and_rotate_refresh_token(
                db=test_db,
                token="not.a.valid.token",
            )

    def test_validate_and_rotate_rejects_wrong_type(self, test_db, test_user):
        """validate_and_rotate_refresh_token rejects access tokens."""
        from app.core.security import create_access_token
        service = UserService()

        access_token = create_access_token(subject=test_user.id)

        with pytest.raises(InvalidTokenError):
            service.validate_and_rotate_refresh_token(
                db=test_db,
                token=access_token,
            )

    def test_validate_and_rotate_rejects_inactive_user(self, test_db, test_user):
        """validate_and_rotate_refresh_token rejects tokens for inactive users."""
        service = UserService()

        # Create and store a refresh token
        refresh_token = create_refresh_token(subject=test_user.id)
        expires_at = datetime.now(timezone.utc) + timedelta(days=7)
        service.store_refresh_token(
            db=test_db,
            user_id=test_user.id,
            token=refresh_token,
            expires_at=expires_at,
        )

        # Deactivate user
        test_user.is_active = False
        test_db.commit()

        with pytest.raises(InvalidTokenError, match="inactive"):
            service.validate_and_rotate_refresh_token(
                db=test_db,
                token=refresh_token,
            )

    def test_validate_and_rotate_rejects_nonexistent_user(self, test_db):
        """validate_and_rotate_refresh_token rejects tokens for deleted users."""
        service = UserService()

        refresh_token = create_refresh_token(subject="nonexistent-user")
        expires_at = datetime.now(timezone.utc) + timedelta(days=7)
        service.store_refresh_token(
            db=test_db,
            user_id="nonexistent-user",
            token=refresh_token,
            expires_at=expires_at,
        )

        with pytest.raises(InvalidTokenError, match="not found"):
            service.validate_and_rotate_refresh_token(
                db=test_db,
                token=refresh_token,
            )

    def test_revoke_refresh_token(self, test_db, test_user):
        """revoke_refresh_token marks token as revoked."""
        service = UserService()

        refresh_token = create_refresh_token(subject=test_user.id)
        expires_at = datetime.now(timezone.utc) + timedelta(days=7)
        service.store_refresh_token(
            db=test_db,
            user_id=test_user.id,
            token=refresh_token,
            expires_at=expires_at,
        )

        result = service.revoke_refresh_token(db=test_db, token=refresh_token)
        assert result is True

        # Verify revoked
        token_hash = hash_token(refresh_token)
        db_token = test_db.execute(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        ).scalar_one()
        assert db_token.is_revoked is True
        assert db_token.revoked_at is not None

    def test_revoke_refresh_token_returns_false_for_unknown(self, test_db, test_user):
        """revoke_refresh_token returns False for unknown tokens."""
        service = UserService()

        result = service.revoke_refresh_token(db=test_db, token="unknown-token")
        assert result is False

    def test_revoke_all_user_tokens(self, test_db, test_user):
        """revoke_all_user_tokens revokes all tokens for a user."""
        import uuid
        from app.core.security import create_refresh_token
        service = UserService()

        # Create multiple tokens with unique JTIs to ensure different hashes
        for i in range(3):
            token_id = str(uuid.uuid4())
            token = create_refresh_token(subject=test_user.id, token_id=token_id)
            expires_at = datetime.now(timezone.utc) + timedelta(days=7)
            service.store_refresh_token(
                db=test_db,
                user_id=test_user.id,
                token=token,
                expires_at=expires_at,
            )

        count = service.revoke_all_user_tokens(db=test_db, user_id=test_user.id)
        assert count == 3

        # All should be revoked
        tokens = test_db.execute(
            select(RefreshToken).where(RefreshToken.user_id == test_user.id)
        ).scalars().all()
        assert all(t.is_revoked for t in tokens)


class TestRefreshTokenEndpoint:
    """Tests for POST /api/auth/refresh endpoint."""

    def test_refresh_success(self, client, test_user):
        """Successful token refresh returns new token pair."""
        # Debug: check if user exists in database
        from tests.conftest import TestingSessionLocal
        from app.services.user_service import user_service
        db = TestingSessionLocal()
        try:
            result = user_service.authenticate_user(db, "test@example.com", "password123")
            print(f"User found in direct session: {result is not None}")
        finally:
            db.close()

        # Login to get initial tokens
        login_response = client.post(
            "/api/auth/login",
            json={"email": "test@example.com", "password": "password123"},
        )
        print(f"Login response: {login_response.status_code}")
        if login_response.status_code != 200:
            print(f"Error: {login_response.json()}")
        assert login_response.status_code == 200
        tokens = login_response.json()
        refresh_token = tokens["refresh_token"]

        # Use refresh token
        response = client.post(
            "/api/auth/refresh",
            json={"refresh_token": refresh_token},
        )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        assert "expires_in" in data
        # New refresh token should be different (rotation)
        assert data["refresh_token"] != refresh_token

    def test_refresh_rejects_expired_token(self, client, test_user):
        """Refresh rejects expired refresh tokens."""
        from app.core.security import create_refresh_token
        from app.models.refresh_token import hash_token
        from datetime import timedelta
        from tests.conftest import TestingSessionLocal

        # Create an expired refresh token directly in DB
        expires_delta = timedelta(seconds=-1)
        expired_token = create_refresh_token(
            subject=test_user.id,
            expires_delta=expires_delta,
        )

        db = TestingSessionLocal()
        try:
            from app.services.user_service import UserService
            service = UserService()
            expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
            service.store_refresh_token(
                db=db,
                user_id=test_user.id,
                token=expired_token,
                expires_at=expires_at,
            )
        finally:
            db.close()

        response = client.post(
            "/api/auth/refresh",
            json={"refresh_token": expired_token},
        )

        assert response.status_code == 401
        assert "expired" in response.json()["detail"].lower()

    def test_refresh_rejects_revoked_token(self, client, test_user):
        """Refresh rejects revoked tokens."""
        from app.core.security import create_refresh_token
        from app.models.refresh_token import hash_token
        from tests.conftest import TestingSessionLocal

        # Create and store a refresh token
        refresh_token = create_refresh_token(subject=test_user.id)

        db = TestingSessionLocal()
        try:
            from app.services.user_service import UserService
            service = UserService()
            expires_at = datetime.now(timezone.utc) + timedelta(days=7)
            service.store_refresh_token(
                db=db,
                user_id=test_user.id,
                token=refresh_token,
                expires_at=expires_at,
            )
            # Revoke it
            token_hash = hash_token(refresh_token)
            db_token = db.execute(
                select(RefreshToken).where(RefreshToken.token_hash == token_hash)
            ).scalar_one()
            db_token.is_revoked = True
            db_token.revoked_at = datetime.now(timezone.utc)
            db.commit()
        finally:
            db.close()

        response = client.post(
            "/api/auth/refresh",
            json={"refresh_token": refresh_token},
        )

        assert response.status_code == 401
        assert "already used" in response.json()["detail"].lower()

    def test_refresh_rejects_reused_token(self, client, test_user):
        """Refresh rejects replay attacks (reused tokens)."""
        # Login to get initial tokens
        login_response = client.post(
            "/api/auth/login",
            json={"email": "test@example.com", "password": "password123"},
        )
        assert login_response.status_code == 200
        tokens = login_response.json()
        refresh_token = tokens["refresh_token"]

        # First refresh - should succeed
        response1 = client.post(
            "/api/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        assert response1.status_code == 200

        # Second refresh with SAME old token - should fail
        response2 = client.post(
            "/api/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        assert response2.status_code == 401
        assert "already used" in response2.json()["detail"].lower()

    def test_refresh_rejects_invalid_token(self, client):
        """Refresh rejects tokens not in database."""
        from app.core.security import create_refresh_token

        # Valid JWT but not stored in DB
        refresh_token = create_refresh_token(subject="user-123")

        response = client.post(
            "/api/auth/refresh",
            json={"refresh_token": refresh_token},
        )

        assert response.status_code == 401

    def test_refresh_rejects_malformed_token(self, client):
        """Refresh rejects malformed tokens."""
        response = client.post(
            "/api/auth/refresh",
            json={"refresh_token": "not.a.valid.token"},
        )

        assert response.status_code == 401

    def test_refresh_rejects_access_token(self, client, test_user):
        """Refresh rejects access tokens used as refresh tokens."""
        from app.core.security import create_access_token

        access_token = create_access_token(subject=test_user.id)

        response = client.post(
            "/api/auth/refresh",
            json={"refresh_token": access_token},
        )

        assert response.status_code == 401

    def test_refresh_rejects_missing_token(self, client):
        """Refresh rejects missing refresh_token field."""
        response = client.post(
            "/api/auth/refresh",
            json={},
        )

        assert response.status_code == 422  # Validation error

    def test_refresh_rejects_empty_token(self, client):
        """Refresh rejects empty refresh token."""
        response = client.post(
            "/api/auth/refresh",
            json={"refresh_token": ""},
        )

        assert response.status_code == 401

    def test_refresh_invalidates_old_token(self, client, test_user):
        """Old refresh token cannot be used after successful rotation.

        Note: When a replay attack is detected (old token reused), all user tokens
        are revoked as a security measure. This test verifies the old token is
        invalidated and that a NEW login is required after replay detection.
        """
        # Login
        login_response = client.post(
            "/api/auth/login",
            json={"email": "test@example.com", "password": "password123"},
        )
        refresh_token = login_response.json()["refresh_token"]

        # Refresh once
        response1 = client.post(
            "/api/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        assert response1.status_code == 200
        new_refresh = response1.json()["refresh_token"]

        # Try to use old token again - should fail (replay attack)
        response2 = client.post(
            "/api/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        assert response2.status_code == 401
        assert "already used" in response2.json()["detail"].lower()

        # After replay attack, all tokens are revoked, including the new one
        # User must login again to get new tokens
        response3 = client.post(
            "/api/auth/refresh",
            json={"refresh_token": new_refresh},
        )
        assert response3.status_code == 401

    def test_concurrent_refresh_attempts(self, client, test_user):
        """Concurrent refresh attempts with same token - only one succeeds."""
        # Login
        login_response = client.post(
            "/api/auth/login",
            json={"email": "test@example.com", "password": "password123"},
        )
        refresh_token = login_response.json()["refresh_token"]

        # Simulate concurrent requests
        responses = []
        for _ in range(3):
            response = client.post(
                "/api/auth/refresh",
                json={"refresh_token": refresh_token},
            )
            responses.append(response)

        # Only one should succeed, others should fail with replay detection
        success_count = sum(1 for r in responses if r.status_code == 200)
        assert success_count == 1, f"Expected 1 success, got {success_count}"


# Import datetime for test fixtures
from datetime import datetime, timezone