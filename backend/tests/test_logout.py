"""Tests for logout and logout-all endpoints."""

import pytest
from datetime import timedelta, datetime, timezone
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    InvalidTokenError,
    TokenExpiredError,
    hash_password,
)
from app.models.refresh_token import RefreshToken, hash_token
from app.services.user_service import UserService
from app.models.user import User


class TestLogoutEndpoint:
    """Tests for POST /api/auth/logout endpoint."""

    def setup_method(self):
        """Create fresh database before each test."""
        from app.core.database import Base
        from tests.conftest import test_engine
        Base.metadata.create_all(bind=test_engine)

    def teardown_method(self):
        """Drop database after each test."""
        from app.core.database import Base
        from tests.conftest import test_engine
        Base.metadata.drop_all(bind=test_engine)

    def _create_user_and_tokens(self, client, email: str = "test@example.com", password: str = "SecurePass123"):
        """Helper to create a user and return access/refresh tokens."""
        # Register
        response = client.post(
            "/api/auth/register",
            json={"email": email, "password": password},
        )
        assert response.status_code == 201

        # Login to get tokens
        response = client.post(
            "/api/auth/login",
            json={"email": email, "password": password},
        )
        assert response.status_code == 200
        tokens = response.json()
        return tokens["access_token"], tokens["refresh_token"]

    def test_logout_success(self, client):
        """Successful logout revokes the specified refresh token."""
        access_token, refresh_token = self._create_user_and_tokens(client)

        # Logout with the refresh token
        response = client.post(
            "/api/auth/logout",
            json={"refresh_token": refresh_token},
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == 204

        # Verify the refresh token is revoked in database
        from tests.conftest import TestingSessionLocal
        db = TestingSessionLocal()
        try:
            token_hash = hash_token(refresh_token)
            db_token = db.execute(
                select(RefreshToken).where(RefreshToken.token_hash == token_hash)
            ).scalar_one_or_none()
            assert db_token is not None
            assert db_token.is_revoked is True
            assert db_token.revoked_at is not None
        finally:
            db.close()

    def test_logout_refresh_token_invalid_after_logout(self, client):
        """Refresh token cannot be used after logout."""
        access_token, refresh_token = self._create_user_and_tokens(client)

        # Logout
        response = client.post(
            "/api/auth/logout",
            json={"refresh_token": refresh_token},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response.status_code == 204

        # Try to use the revoked refresh token
        response = client.post(
            "/api/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        assert response.status_code == 401
        assert "invalid" in response.json()["detail"].lower() or "revoked" in response.json()["detail"].lower() or "already used" in response.json()["detail"].lower()

    def test_logout_other_users_token_fails(self, client):
        """Cannot revoke another user's refresh token - returns generic 401."""
        # Create user 1
        access_token1, refresh_token1 = self._create_user_and_tokens(client, "user1@example.com")

        # Create user 2
        access_token2, refresh_token2 = self._create_user_and_tokens(client, "user2@example.com")

        # User 1 tries to revoke user 2's refresh token
        response = client.post(
            "/api/auth/logout",
            json={"refresh_token": refresh_token2},
            headers={"Authorization": f"Bearer {access_token1}"},
        )

        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid refresh token"

        # Verify user 2's token is still valid
        response = client.post(
            "/api/auth/refresh",
            json={"refresh_token": refresh_token2},
        )
        assert response.status_code == 200

    def test_logout_invalid_refresh_token(self, client):
        """Logout rejects invalid/malformed refresh tokens."""
        access_token, _ = self._create_user_and_tokens(client)

        response = client.post(
            "/api/auth/logout",
            json={"refresh_token": "not.a.valid.token"},
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == 401
        assert "invalid" in response.json()["detail"].lower()

    def test_logout_expired_refresh_token(self, client):
        """Logout rejects expired refresh tokens with generic 401."""
        access_token, _ = self._create_user_and_tokens(client)

        # Create an expired refresh token
        from tests.conftest import TestingSessionLocal
        from app.services.user_service import UserService
        db = TestingSessionLocal()
        try:
            service = UserService()
            expired_token = create_refresh_token(
                subject="test-user-id",
                expires_delta=timedelta(seconds=-1),
            )
            expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
            service.store_refresh_token(
                db=db,
                user_id="test-user-id",
                token=expired_token,
                expires_at=expires_at,
            )
        finally:
            db.close()

        response = client.post(
            "/api/auth/logout",
            json={"refresh_token": expired_token},
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid refresh token"

    def test_logout_already_revoked_token(self, client):
        """Logout rejects already revoked refresh tokens."""
        access_token, refresh_token = self._create_user_and_tokens(client)

        # First logout
        response = client.post(
            "/api/auth/logout",
            json={"refresh_token": refresh_token},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response.status_code == 204

        # Second logout with same token
        response = client.post(
            "/api/auth/logout",
            json={"refresh_token": refresh_token},
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == 401
        assert "invalid" in response.json()["detail"].lower()

    def test_logout_access_token_required(self, client):
        """Logout requires valid access token."""
        _, refresh_token = self._create_user_and_tokens(client)

        # No Authorization header
        response = client.post(
            "/api/auth/logout",
            json={"refresh_token": refresh_token},
        )

        assert response.status_code == 401
        assert response.json()["detail"] == "Not authenticated"

    def test_logout_invalid_access_token(self, client):
        """Logout rejects invalid access token."""
        _, refresh_token = self._create_user_and_tokens(client)

        response = client.post(
            "/api/auth/logout",
            json={"refresh_token": refresh_token},
            headers={"Authorization": "Bearer invalid.token.here"},
        )

        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid token"

    def test_logout_access_token_used_as_refresh_token(self, client):
        """Access token cannot be used as refresh token in logout - returns generic 401."""
        access_token, _ = self._create_user_and_tokens(client)

        response = client.post(
            "/api/auth/logout",
            json={"refresh_token": access_token},  # Using access token as refresh token
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid refresh token"


class TestLogoutAllEndpoint:
    """Tests for POST /api/auth/logout-all endpoint."""

    def setup_method(self):
        """Create fresh database before each test."""
        from app.core.database import Base
        from tests.conftest import test_engine
        Base.metadata.create_all(bind=test_engine)

    def teardown_method(self):
        """Drop database after each test."""
        from app.core.database import Base
        from tests.conftest import test_engine
        Base.metadata.drop_all(bind=test_engine)

    def _create_user_and_login(self, client, email: str = "test@example.com", password: str = "SecurePass123"):
        """Helper to create a user and login."""
        client.post("/api/auth/register", json={"email": email, "password": password})
        response = client.post("/api/auth/login", json={"email": email, "password": password})
        assert response.status_code == 200
        return response.json()["access_token"], response.json()["refresh_token"]

    def test_logout_all_success(self, client):
        """Logout-all revokes all user's refresh tokens."""
        access_token, refresh_token1 = self._create_user_and_login(client)

        # Create additional refresh tokens by refreshing
        response = client.post(
            "/api/auth/refresh",
            json={"refresh_token": refresh_token1},
        )
        assert response.status_code == 200
        refresh_token2 = response.json()["refresh_token"]

        response = client.post(
            "/api/auth/refresh",
            json={"refresh_token": refresh_token2},
        )
        assert response.status_code == 200
        refresh_token3 = response.json()["refresh_token"]

        # Now logout-all
        response = client.post(
            "/api/auth/logout-all",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response.status_code == 204

        # All refresh tokens should be revoked
        for rt in [refresh_token1, refresh_token2, refresh_token3]:
            response = client.post(
                "/api/auth/refresh",
                json={"refresh_token": rt},
            )
            assert response.status_code == 401

    def test_logout_all_only_affects_current_user(self, client):
        """Logout-all never affects another user's sessions."""
        # User 1
        access_token1, refresh_token1 = self._create_user_and_login(client, "user1@example.com")

        # User 2
        access_token2, refresh_token2 = self._create_user_and_login(client, "user2@example.com")

        # User 1 logout-all
        response = client.post(
            "/api/auth/logout-all",
            headers={"Authorization": f"Bearer {access_token1}"},
        )
        assert response.status_code == 204

        # User 1's tokens should be revoked
        response = client.post(
            "/api/auth/refresh",
            json={"refresh_token": refresh_token1},
        )
        assert response.status_code == 401

        # User 2's tokens should still be valid
        response = client.post(
            "/api/auth/refresh",
            json={"refresh_token": refresh_token2},
        )
        assert response.status_code == 200

    def test_logout_all_access_token_required(self, client):
        """Logout-all requires valid access token."""
        self._create_user_and_login(client)

        response = client.post("/api/auth/logout-all")

        assert response.status_code == 401
        assert response.json()["detail"] == "Not authenticated"

    def test_logout_all_invalid_access_token(self, client):
        """Logout-all rejects invalid access token."""
        self._create_user_and_login(client)

        response = client.post(
            "/api/auth/logout-all",
            headers={"Authorization": "Bearer invalid.token.here"},
        )

        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid token"

    def test_logout_all_empty_body(self, client):
        """Logout-all accepts empty request body."""
        access_token, _ = self._create_user_and_login(client)

        response = client.post(
            "/api/auth/logout-all",
            json={},
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == 204


class TestLogoutIntegrationWithExistingAuth:
    """Integration tests to ensure logout doesn't break existing functionality."""

    def setup_method(self):
        from app.core.database import Base
        from tests.conftest import test_engine
        Base.metadata.create_all(bind=test_engine)

    def teardown_method(self):
        from app.core.database import Base
        from tests.conftest import test_engine
        Base.metadata.drop_all(bind=test_engine)

    def test_registration_still_works(self, client):
        """User registration still works after logout implementation."""
        response = client.post(
            "/api/auth/register",
            json={"email": "newuser@example.com", "password": "SecurePass123"},
        )
        assert response.status_code == 201

    def test_login_still_works(self, client):
        """User login still works after logout implementation."""
        client.post("/api/auth/register", json={"email": "logintest@example.com", "password": "SecurePass123"})
        response = client.post("/api/auth/login", json={"email": "logintest@example.com", "password": "SecurePass123"})
        assert response.status_code == 200
        assert "access_token" in response.json()
        assert "refresh_token" in response.json()

    def test_refresh_still_works(self, client):
        """Token refresh still works after logout implementation."""
        client.post("/api/auth/register", json={"email": "refreshtest@example.com", "password": "SecurePass123"})
        login_response = client.post("/api/auth/login", json={"email": "refreshtest@example.com", "password": "SecurePass123"})
        refresh_token = login_response.json()["refresh_token"]

        response = client.post("/api/auth/refresh", json={"refresh_token": refresh_token})
        assert response.status_code == 200
        assert "access_token" in response.json()
        assert "refresh_token" in response.json()

    def test_access_token_valid_after_logout(self, client):
        """Access token remains valid until expiry after logout (30 min default)."""
        access_token, refresh_token = self._create_user_and_login(client)

        # Logout
        response = client.post(
            "/api/auth/logout",
            json={"refresh_token": refresh_token},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response.status_code == 204

        # Access token should still work for authenticated endpoints
        # Use logout-all endpoint which requires valid access token
        response = client.post(
            "/api/auth/logout-all",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response.status_code == 204

    def _create_user_and_login(self, client, email: str = "test@example.com", password: str = "SecurePass123"):
        """Helper to create a user and login."""
        client.post("/api/auth/register", json={"email": email, "password": password})
        response = client.post("/api/auth/login", json={"email": email, "password": password})
        assert response.status_code == 200
        return response.json()["access_token"], response.json()["refresh_token"]


# Run the tests
if __name__ == "__main__":
    pytest.main([__file__, "-v"])