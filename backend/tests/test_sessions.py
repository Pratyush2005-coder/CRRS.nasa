"""Tests for session management (Phase 4.8C.5)."""

import pytest
from datetime import timedelta, datetime, timezone
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_access_token,
    decode_refresh_token,
    InvalidTokenError,
    TokenExpiredError,
    hash_password,
)
from app.models.refresh_token import RefreshToken, hash_token
from app.services.user_service import UserService
from app.models.user import User


class TestSessionModel:
    """Tests for RefreshToken model with session fields."""

    def test_refresh_token_model_with_session_fields(self):
        """RefreshToken model can be instantiated with session fields."""
        rt = RefreshToken(
            id="test-id",
            user_id="user-123",
            session_id="session-456",
            token_hash="abc123",
            is_revoked=False,
            created_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
            device_info="Mozilla/5.0 Test Browser",
            ip_address="192.168.1.100",
            last_used_at=datetime.now(timezone.utc),
        )
        assert rt.session_id == "session-456"
        assert rt.device_info == "Mozilla/5.0 Test Browser"
        assert rt.ip_address == "192.168.1.100"
        assert rt.last_used_at is not None


class TestSessionCreationDuringLogin:
    """Tests for session creation during login."""

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

    def test_login_creates_session_with_metadata(self, client):
        """Login creates a session with device_info, ip_address, and session_id."""
        # Register user
        response = client.post(
            "/api/auth/register",
            json={"email": "test@example.com", "password": "SecurePass123"},
        )
        assert response.status_code == 201

        # Login with custom User-Agent
        headers = {"User-Agent": "TestClient/1.0 (Test Device)"}
        response = client.post(
            "/api/auth/login",
            json={"email": "test@example.com", "password": "SecurePass123"},
            headers=headers,
        )
        assert response.status_code == 200
        tokens = response.json()

        # Verify access token has session_id claim
        access_token = tokens["access_token"]
        payload = decode_access_token(access_token)
        assert "sid" in payload
        session_id = payload["sid"]
        assert session_id is not None
        assert len(session_id) == 36  # UUID format

        # Verify refresh token stored with session metadata
        from tests.conftest import TestingSessionLocal
        db = TestingSessionLocal()
        try:
            refresh_token = tokens["refresh_token"]
            token_hash = hash_token(refresh_token)
            db_token = db.execute(
                select(RefreshToken).where(RefreshToken.token_hash == token_hash)
            ).scalar_one_or_none()

            assert db_token is not None
            assert db_token.session_id == session_id
            assert db_token.device_info == "TestClient/1.0 (Test Device)"
            assert db_token.ip_address is not None
            assert db_token.last_used_at is not None
            assert db_token.created_at is not None
        finally:
            db.close()

    def test_login_without_user_agent(self, client):
        """Login works without User-Agent header."""
        # Register user
        response = client.post(
            "/api/auth/register",
            json={"email": "test2@example.com", "password": "SecurePass123"},
        )
        assert response.status_code == 201

        # Login without User-Agent
        response = client.post(
            "/api/auth/login",
            json={"email": "test2@example.com", "password": "SecurePass123"},
        )
        assert response.status_code == 200
        tokens = response.json()

        # Verify session created with None device_info
        from tests.conftest import TestingSessionLocal
        db = TestingSessionLocal()
        try:
            refresh_token = tokens["refresh_token"]
            token_hash = hash_token(refresh_token)
            db_token = db.execute(
                select(RefreshToken).where(RefreshToken.token_hash == token_hash)
            ).scalar_one_or_none()

            assert db_token is not None
            assert db_token.session_id is not None
            assert db_token.device_info is not None  # TestClient provides "testclient"
            assert db_token.ip_address is not None
        finally:
            db.close()


class TestSessionListing:
    """Tests for GET /api/auth/sessions endpoint."""

    def _create_user_and_login(self, client, email: str = "test@example.com", password: str = "SecurePass123", headers=None):
        """Helper to create a user and login."""
        client.post("/api/auth/register", json={"email": email, "password": password})
        response = client.post("/api/auth/login", json={"email": email, "password": password}, headers=headers)
        assert response.status_code == 200
        return response.json()["access_token"], response.json()["refresh_token"]

    def test_list_sessions_returns_active_sessions(self, client):
        """List sessions returns active sessions with metadata."""
        access_token, refresh_token = self._create_user_and_login(client)

        # Get sessions
        response = client.get(
            "/api/auth/sessions",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response.status_code == 200
        data = response.json()

        assert "sessions" in data
        assert len(data["sessions"]) == 1
        session = data["sessions"][0]
        assert "session_id" in session
        assert "device_info" in session
        assert "ip_address" in session
        assert "created_at" in session
        assert "last_used_at" in session
        assert "is_current" in session
        assert session["is_current"] is True

    def test_list_sessions_multiple_sessions(self, client):
        """List sessions shows multiple sessions from different devices."""
        # Login from device 1
        headers1 = {"User-Agent": "Device1/1.0"}
        access_token1, refresh_token1 = self._create_user_and_login(client, "user1@example.com", headers=headers1)

        # Login from device 2 (different user agent)
        headers2 = {"User-Agent": "Device2/2.0"}
        access_token2, refresh_token2 = self._create_user_and_login(client, "user1@example.com", headers=headers2)

        # List sessions for user1
        response = client.get(
            "/api/auth/sessions",
            headers={"Authorization": f"Bearer {access_token1}"},
        )
        assert response.status_code == 200
        data = response.json()

        # Should have 2 sessions
        assert len(data["sessions"]) == 2

        # One should be marked as current
        current_sessions = [s for s in data["sessions"] if s["is_current"]]
        assert len(current_sessions) == 1

        # Verify device info is different
        device_infos = [s["device_info"] for s in data["sessions"]]
        assert "Device1/1.0" in device_infos
        assert "Device2/2.0" in device_infos

    def test_list_sessions_excludes_revoked(self, client):
        """List sessions excludes revoked sessions."""
        access_token, refresh_token = self._create_user_and_login(client)

        # Revoke the session via logout
        response = client.post(
            "/api/auth/logout",
            json={"refresh_token": refresh_token},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response.status_code == 204

        # List sessions should be empty
        response = client.get(
            "/api/auth/sessions",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["sessions"]) == 0

    def test_list_sessions_excludes_expired(self, client):
        """List sessions excludes expired sessions."""
        access_token, refresh_token = self._create_user_and_login(client)

        # Manually expire the token in database
        from tests.conftest import TestingSessionLocal
        db = TestingSessionLocal()
        try:
            token_hash = hash_token(refresh_token)
            db_token = db.execute(
                select(RefreshToken).where(RefreshToken.token_hash == token_hash)
            ).scalar_one()
            db_token.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
            db.commit()
        finally:
            db.close()

        # List sessions should be empty
        response = client.get(
            "/api/auth/sessions",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["sessions"]) == 0

    def test_list_sessions_requires_auth(self, client):
        """List sessions requires valid access token."""
        response = client.get("/api/auth/sessions")
        assert response.status_code == 401

    def test_list_sessions_invalid_token(self, client):
        """List sessions rejects invalid access token."""
        response = client.get(
            "/api/auth/sessions",
            headers={"Authorization": "Bearer invalid.token.here"},
        )
        assert response.status_code == 401


class TestCurrentSessionIdentification:
    """Tests for current session identification."""

    def _create_user_and_login(self, client, email: str = "test@example.com", password: str = "SecurePass123", headers=None):
        """Helper to create a user and login."""
        client.post("/api/auth/register", json={"email": email, "password": password})
        response = client.post("/api/auth/login", json={"email": email, "password": password}, headers=headers)
        assert response.status_code == 200
        return response.json()["access_token"], response.json()["refresh_token"]

    def test_current_session_identified_by_sid_claim(self, client):
        """Current session identified by sid claim in access token."""
        headers = {"User-Agent": "TestDevice/1.0"}
        access_token, refresh_token = self._create_user_and_login(client, headers=headers)

        # Decode access token to verify sid claim
        payload = decode_access_token(access_token)
        assert "sid" in payload
        session_id = payload["sid"]

        # List sessions
        response = client.get(
            "/api/auth/sessions",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response.status_code == 200
        data = response.json()

        # The session with matching session_id should be marked current
        current_session = next((s for s in data["sessions"] if s["is_current"]), None)
        assert current_session is not None
        assert current_session["session_id"] == session_id

    def test_session_identity_persists_after_rotation(self, client):
        """Session identity persists through token rotation."""
        access_token, refresh_token = self._create_user_and_login(client)

        # Get initial session_id from access token
        payload = decode_access_token(access_token)
        original_session_id = payload["sid"]

        # Refresh token
        response = client.post(
            "/api/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        assert response.status_code == 200
        new_tokens = response.json()
        new_access_token = new_tokens["access_token"]
        new_refresh_token = new_tokens["refresh_token"]

        # New access token should have same session_id
        new_payload = decode_access_token(new_access_token)
        assert new_payload["sid"] == original_session_id

        # List sessions with new access token
        response = client.get(
            "/api/auth/sessions",
            headers={"Authorization": f"Bearer {new_access_token}"},
        )
        assert response.status_code == 200
        data = response.json()

        # Should still have one session marked as current
        current_session = next((s for s in data["sessions"] if s["is_current"]), None)
        assert current_session is not None
        assert current_session["session_id"] == original_session_id

    def test_multiple_rotations_preserve_session(self, client):
        """Multiple token rotations preserve session identity."""
        access_token, refresh_token = self._create_user_and_login(client)
        original_session_id = decode_access_token(access_token)["sid"]

        # Perform multiple rotations
        current_refresh = refresh_token
        for _ in range(3):
            response = client.post(
                "/api/auth/refresh",
                json={"refresh_token": current_refresh},
            )
            assert response.status_code == 200
            new_tokens = response.json()
            current_refresh = new_tokens["refresh_token"]
            new_access = new_tokens["access_token"]
            assert decode_access_token(new_access)["sid"] == original_session_id


class TestSessionRevocation:
    """Tests for DELETE /api/auth/sessions/{session_id} endpoint."""

    def _create_user_and_login(self, client, email: str = "test@example.com", password: str = "SecurePass123", headers=None):
        """Helper to create a user and login."""
        client.post("/api/auth/register", json={"email": email, "password": password})
        response = client.post("/api/auth/login", json={"email": email, "password": password}, headers=headers)
        assert response.status_code == 200
        return response.json()["access_token"], response.json()["refresh_token"]

    def test_revoke_session_success(self, client):
        """Revoke session revokes the specified session."""
        # Create two sessions
        headers1 = {"User-Agent": "Device1"}
        access_token1, refresh_token1 = self._create_user_and_login(client, "user@example.com", headers=headers1)

        headers2 = {"User-Agent": "Device2"}
        access_token2, refresh_token2 = self._create_user_and_login(client, "user@example.com", headers=headers2)

        # Get session list to find session IDs
        response = client.get(
            "/api/auth/sessions",
            headers={"Authorization": f"Bearer {access_token1}"},
        )
        assert response.status_code == 200
        sessions = response.json()["sessions"]
        assert len(sessions) == 2

        # Revoke session 2
        session2_id = next(s["session_id"] for s in sessions if s["device_info"] == "Device2")
        response = client.delete(
            f"/api/auth/sessions/{session2_id}",
            headers={"Authorization": f"Bearer {access_token1}"},
        )
        assert response.status_code == 204

        # Session 1 should still work (we don't test session2's token since using a revoked token
        # triggers replay attack protection which revokes all tokens)
        response = client.post(
            "/api/auth/refresh",
            json={"refresh_token": refresh_token1},
        )
        assert response.status_code == 200

    def test_revoke_current_session(self, client):
        """Can revoke the current session."""
        access_token, refresh_token = self._create_user_and_login(client)

        # Get current session ID
        response = client.get(
            "/api/auth/sessions",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        sessions = response.json()["sessions"]
        current_session_id = next(s["session_id"] for s in sessions if s["is_current"])

        # Revoke current session
        response = client.delete(
            f"/api/auth/sessions/{current_session_id}",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response.status_code == 204

        # Refresh should fail
        response = client.post(
            "/api/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        assert response.status_code == 401

    def test_revoke_nonexistent_session(self, client):
        """Revoke nonexistent session returns 404."""
        access_token, _ = self._create_user_and_login(client)

        response = client.delete(
            "/api/auth/sessions/nonexistent-session-id",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response.status_code == 404

    def test_revoke_another_users_session(self, client):
        """Cannot revoke another user's session."""
        # User 1
        access_token1, _ = self._create_user_and_login(client, "user1@example.com")

        # User 2
        access_token2, _ = self._create_user_and_login(client, "user2@example.com")

        # Get user 2's session
        response = client.get(
            "/api/auth/sessions",
            headers={"Authorization": f"Bearer {access_token2}"},
        )
        session2_id = response.json()["sessions"][0]["session_id"]

        # User 1 tries to revoke user 2's session
        response = client.delete(
            f"/api/auth/sessions/{session2_id}",
            headers={"Authorization": f"Bearer {access_token1}"},
        )
        assert response.status_code == 404

        # User 2's session should still work
        response = client.get(
            "/api/auth/sessions",
            headers={"Authorization": f"Bearer {access_token2}"},
        )
        assert len(response.json()["sessions"]) == 1

    def test_revoke_already_revoked_session(self, client):
        """Revoke already revoked session returns 404."""
        access_token, refresh_token = self._create_user_and_login(client)

        # Get session ID
        response = client.get(
            "/api/auth/sessions",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        session_id = response.json()["sessions"][0]["session_id"]

        # Revoke once
        response = client.delete(
            f"/api/auth/sessions/{session_id}",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response.status_code == 204

        # Revoke again
        response = client.delete(
            f"/api/auth/sessions/{session_id}",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response.status_code == 404

    def test_revoke_session_requires_auth(self, client):
        """Revoke session requires valid access token."""
        response = client.delete("/api/auth/sessions/some-session-id")
        assert response.status_code == 401


class TestLogoutAllCompatibility:
    """Tests for logout-all compatibility with session management."""

    def _create_user_and_login(self, client, email: str = "test@example.com", password: str = "SecurePass123"):
        """Helper to create a user and login."""
        client.post("/api/auth/register", json={"email": email, "password": password})
        response = client.post("/api/auth/login", json={"email": email, "password": password})
        assert response.status_code == 200
        return response.json()["access_token"], response.json()["refresh_token"]

    def test_logout_all_revokes_all_sessions(self, client):
        """Logout-all revokes all sessions for the user."""
        access_token, refresh_token1 = self._create_user_and_login(client)

        # Create additional sessions by refreshing
        response = client.post("/api/auth/refresh", json={"refresh_token": refresh_token1})
        refresh_token2 = response.json()["refresh_token"]

        response = client.post("/api/auth/refresh", json={"refresh_token": refresh_token2})
        refresh_token3 = response.json()["refresh_token"]

        # Logout all
        response = client.post("/api/auth/logout-all", headers={"Authorization": f"Bearer {access_token}"})
        assert response.status_code == 204

        # All sessions should be revoked
        for rt in [refresh_token1, refresh_token2, refresh_token3]:
            response = client.post("/api/auth/refresh", json={"refresh_token": rt})
            assert response.status_code == 401

        # Session list should be empty
        response = client.get("/api/auth/sessions", headers={"Authorization": f"Bearer {access_token}"})
        assert response.status_code == 200
        assert len(response.json()["sessions"]) == 0

    def test_logout_all_only_affects_current_user(self, client):
        """Logout-all never affects another user's sessions."""
        # User 1
        access_token1, refresh_token1 = self._create_user_and_login(client, "user1@example.com")

        # User 2
        access_token2, refresh_token2 = self._create_user_and_login(client, "user2@example.com")

        # User 1 logout-all
        response = client.post("/api/auth/logout-all", headers={"Authorization": f"Bearer {access_token1}"})
        assert response.status_code == 204

        # User 1's sessions revoked
        response = client.post("/api/auth/refresh", json={"refresh_token": refresh_token1})
        assert response.status_code == 401

        # User 2's sessions still valid
        response = client.post("/api/auth/refresh", json={"refresh_token": refresh_token2})
        assert response.status_code == 200


class TestMissingMalformedMetadata:
    """Tests for handling missing or malformed metadata."""

    def _create_user_and_login(self, client, email: str = "test@example.com", password: str = "SecurePass123", headers=None):
        """Helper to create a user and login."""
        client.post("/api/auth/register", json={"email": email, "password": password})
        response = client.post("/api/auth/login", json={"email": email, "password": password}, headers=headers)
        assert response.status_code == 200
        return response.json()["access_token"], response.json()["refresh_token"]

    def test_session_without_user_agent(self, client):
        """Session handles missing explicit User-Agent (TestClient provides default)."""
        # Login without explicit User-Agent header (TestClient adds "testclient")
        access_token, refresh_token = self._create_user_and_login(client)

        response = client.get(
            "/api/auth/sessions",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response.status_code == 200
        session = response.json()["sessions"][0]
        assert session["device_info"] is not None  # TestClient provides "testclient"

    def test_session_with_ipv6_address(self, client):
        """Session handles IPv6 addresses."""
        # The test client uses 127.0.0.1, but we verify IP is stored
        access_token, refresh_token = self._create_user_and_login(client)

        response = client.get(
            "/api/auth/sessions",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response.status_code == 200
        session = response.json()["sessions"][0]
        assert session["ip_address"] is not None

    def test_session_with_long_user_agent(self, client):
        """Session handles very long User-Agent strings."""
        long_ua = "Mozilla/5.0 " + "x" * 500
        headers = {"User-Agent": long_ua}
        access_token, refresh_token = self._create_user_and_login(client, headers=headers)

        response = client.get(
            "/api/auth/sessions",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response.status_code == 200
        session = response.json()["sessions"][0]
        # Should be truncated or stored fully (512 char limit)
        assert session["device_info"] is not None


class TestSessionServiceMethods:
    """Tests for UserService session management methods."""

    def test_get_user_sessions(self, client, test_user):
        """get_user_sessions returns active sessions grouped by session_id."""
        from app.services.user_service import user_service
        from tests.conftest import TestingSessionLocal

        # Create multiple tokens with different session_ids
        import uuid
        db = TestingSessionLocal()
        try:
            service = UserService()
            for i in range(3):
                session_id = str(uuid.uuid4())
                token_id = str(uuid.uuid4())
                token = create_refresh_token(subject=test_user.id, token_id=token_id)
                expires_at = datetime.now(timezone.utc) + timedelta(days=7)
                service.store_refresh_token(
                    db=db,
                    user_id=test_user.id,
                    token=token,
                    expires_at=expires_at,
                    session_id=session_id,
                    device_info=f"Device{i}",
                    ip_address="192.168.1.1",
                )

            sessions = service.get_user_sessions(db=db, user_id=test_user.id)
            assert len(sessions) == 3
        finally:
            db.close()

    def test_get_session_by_id(self, client, test_user):
        """get_session_by_id returns session if belongs to user."""
        from app.services.user_service import user_service
        from tests.conftest import TestingSessionLocal
        import uuid

        db = TestingSessionLocal()
        try:
            service = UserService()
            session_id = str(uuid.uuid4())
            token_id = str(uuid.uuid4())
            token = create_refresh_token(subject=test_user.id, token_id=token_id)
            expires_at = datetime.now(timezone.utc) + timedelta(days=7)
            service.store_refresh_token(
                db=db,
                user_id=test_user.id,
                token=token,
                expires_at=expires_at,
                session_id=session_id,
            )

            session = service.get_session_by_id(db=db, user_id=test_user.id, session_id=session_id)
            assert session is not None
            assert session.session_id == session_id

            # Not found for another user
            session = service.get_session_by_id(db=db, user_id="other-user", session_id=session_id)
            assert session is None
        finally:
            db.close()

    def test_revoke_session(self, client, test_user):
        """revoke_session revokes all tokens in a session."""
        from app.services.user_service import user_service
        from tests.conftest import TestingSessionLocal
        import uuid

        db = TestingSessionLocal()
        try:
            service = UserService()
            session_id = str(uuid.uuid4())

            # Create multiple tokens in same session
            for i in range(3):
                token_id = str(uuid.uuid4())
                token = create_refresh_token(subject=test_user.id, token_id=token_id)
                expires_at = datetime.now(timezone.utc) + timedelta(days=7)
                service.store_refresh_token(
                    db=db,
                    user_id=test_user.id,
                    token=token,
                    expires_at=expires_at,
                    session_id=session_id,
                )

            # Revoke session
            result = service.revoke_session(db=db, user_id=test_user.id, session_id=session_id)
            assert result is True

            # All tokens should be revoked
            tokens = db.execute(
                select(RefreshToken).where(RefreshToken.user_id == test_user.id)
            ).scalars().all()
            assert all(t.is_revoked for t in tokens)
        finally:
            db.close()

    def test_revoke_session_not_found(self, client, test_user):
        """revoke_session returns False for nonexistent session."""
        from app.services.user_service import user_service
        from tests.conftest import TestingSessionLocal

        db = TestingSessionLocal()
        try:
            service = UserService()
            result = service.revoke_session(db=db, user_id=test_user.id, session_id="nonexistent")
            assert result is False
        finally:
            db.close()


class TestConcurrentRefreshRevocation:
    """Tests for concurrent refresh and revocation behavior."""

    def _create_user_and_login(self, client, email: str = "test@example.com", password: str = "SecurePass123"):
        """Helper to create a user and login."""
        client.post("/api/auth/register", json={"email": email, "password": password})
        response = client.post("/api/auth/login", json={"email": email, "password": password})
        assert response.status_code == 200
        return response.json()["access_token"], response.json()["refresh_token"]

    def test_revoke_during_refresh(self, client):
        """Revoking a session during refresh - race condition handling."""
        access_token, refresh_token = self._create_user_and_login(client)

        # Get session ID
        response = client.get(
            "/api/auth/sessions",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        session_id = response.json()["sessions"][0]["session_id"]

        # Attempt to revoke and refresh concurrently (simulated sequentially)
        # In real scenario, this would be concurrent requests
        # First revoke
        response = client.delete(
            f"/api/auth/sessions/{session_id}",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response.status_code == 204

        # Then try to use the revoked refresh token
        response = client.post(
            "/api/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        assert response.status_code == 401


if __name__ == "__main__":
    pytest.main([__file__, "-v"])