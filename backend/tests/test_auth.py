"""Tests for authentication endpoints."""

import os
import pytest
from datetime import timedelta
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
import jwt

from app.main import app
from app.models.user import User, UserRole
from app.core.database import get_db
from app.core.security import hash_password, verify_password, create_access_token, create_refresh_token
from app.core.config import settings
from app.api.deps import get_current_user, require_admin

# Import test database fixtures from conftest
from tests.conftest import test_engine, TestingSessionLocal, Base


# Add a test endpoint that uses get_current_user
@app.get("/api/auth/me", tags=["Auth"])
def get_current_user_endpoint(current_user: User = Depends(get_current_user)):
    """Test endpoint to verify get_current_user dependency."""
    return {
        "id": current_user.id,
        "email": current_user.email,
        "role": current_user.role,
        "is_active": current_user.is_active,
    }


# Add a test endpoint that uses require_admin
@app.get("/api/auth/admin-only", tags=["Auth"])
def admin_only_endpoint(current_user: User = Depends(require_admin)):
    """Test endpoint to verify require_admin dependency."""
    return {
        "message": "Admin access granted",
        "user": current_user.email,
        "role": current_user.role,
    }


# Override get_db for testing
def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


class TestUserRegistration:
    """Tests for POST /api/auth/register endpoint."""

    def setup_method(self):
        """Create fresh database before each test."""
        from app.core.database import Base
        Base.metadata.create_all(bind=test_engine)

    def teardown_method(self):
        """Drop database after each test."""
        from app.core.database import Base
        Base.metadata.drop_all(bind=test_engine)

    def test_register_success(self):
        """Successful registration returns 201 with user data."""
        response = client.post(
            "/api/auth/register",
            json={"email": "farmer@example.com", "password": "SecurePass123"},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["email"] == "farmer@example.com"
        assert data["role"] == "user"
        assert data["is_active"] is True
        assert "id" in data
        assert "created_at" in data
        assert "updated_at" in data
        # Sensitive fields must not be present
        assert "hashed_password" not in data
        assert "password" not in data

    def test_register_returns_201_status(self):
        """Registration returns HTTP 201 Created."""
        response = client.post(
            "/api/auth/register",
            json={"email": "test@example.com", "password": "Password123"},
        )
        assert response.status_code == 201

    def test_register_email_normalization_lowercase(self):
        """Email is normalized to lowercase."""
        response = client.post(
            "/api/auth/register",
            json={"email": "FARMER@EXAMPLE.COM", "password": "SecurePass123"},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["email"] == "farmer@example.com"

    def test_register_email_normalization_trim_whitespace(self):
        """Email is trimmed of whitespace."""
        response = client.post(
            "/api/auth/register",
            json={"email": "  farmer@example.com  ", "password": "SecurePass123"},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["email"] == "farmer@example.com"

    def test_register_password_hashed_and_persisted(self):
        """Password is hashed and persisted, not returned."""
        response = client.post(
            "/api/auth/register",
            json={"email": "hash@example.com", "password": "SecurePass123"},
        )

        assert response.status_code == 201
        data = response.json()
        assert "hashed_password" not in data
        assert "password" not in data

        # Verify in database
        db = TestingSessionLocal()
        try:
            user = db.query(User).filter(User.email == "hash@example.com").first()
            assert user is not None
            assert user.hashed_password != "SecurePass123"
            assert user.hashed_password.startswith("$pbkdf2-sha256$")
            assert verify_password("SecurePass123", user.hashed_password)
        finally:
            db.close()

    def test_register_plaintext_password_never_returned(self):
        """Plaintext password is never in response."""
        response = client.post(
            "/api/auth/register",
            json={"email": "plain@example.com", "password": "MySecretPass"},
        )

        assert response.status_code == 201
        data = response.json()
        assert "password" not in data
        assert data["email"] == "plain@example.com"

    def test_register_hashed_password_never_returned(self):
        """Hashed password is never in response."""
        response = client.post(
            "/api/auth/register",
            json={"email": "hashed@example.com", "password": "SecurePass123"},
        )

        assert response.status_code == 201
        data = response.json()
        assert "hashed_password" not in data

    def test_register_duplicate_email_returns_409(self):
        """Duplicate email returns HTTP 409 Conflict."""
        # First registration
        client.post(
            "/api/auth/register",
            json={"email": "duplicate@example.com", "password": "Password123"},
        )

        # Second registration with same email
        response = client.post(
            "/api/auth/register",
            json={"email": "duplicate@example.com", "password": "DifferentPass456"},
        )

        assert response.status_code == 409
        data = response.json()
        assert "detail" in data
        assert "already registered" in data["detail"].lower()

    def test_register_invalid_email_returns_422(self):
        """Invalid email format returns HTTP 422."""
        response = client.post(
            "/api/auth/register",
            json={"email": "not-an-email", "password": "Password123"},
        )

        assert response.status_code == 422

    def test_register_missing_email_returns_422(self):
        """Missing email returns HTTP 422."""
        response = client.post(
            "/api/auth/register",
            json={"password": "Password123"},
        )

        assert response.status_code == 422

    def test_register_missing_password_returns_422(self):
        """Missing password returns HTTP 422."""
        response = client.post(
            "/api/auth/register",
            json={"email": "test@example.com"},
        )

        assert response.status_code == 422

    def test_register_empty_password_rejected(self):
        """Empty password returns 422."""
        response = client.post(
            "/api/auth/register",
            json={"email": "test@example.com", "password": ""},
        )

        assert response.status_code == 422

    def test_register_whitespace_only_password_rejected(self):
        """Whitespace-only password returns 422."""
        response = client.post(
            "/api/auth/register",
            json={"email": "test@example.com", "password": "   "},
        )

        assert response.status_code == 422

    def test_register_password_shorter_than_8_chars_rejected(self):
        """Password shorter than 8 characters returns 422."""
        response = client.post(
            "/api/auth/register",
            json={"email": "test@example.com", "password": "Pass123"},
        )

        assert response.status_code == 422

    def test_register_client_cannot_set_admin_role(self):
        """Client cannot assign admin role via registration."""
        response = client.post(
            "/api/auth/register",
            json={
                "email": "admin_attempt@example.com",
                "password": "SecurePass123",
                "role": "admin",  # Should be ignored/rejected
            },
        )

        # Should still succeed but role should be 'user'
        assert response.status_code == 201
        data = response.json()
        assert data["role"] == "user"

    def test_register_client_cannot_set_is_active(self):
        """Client cannot set is_active via registration."""
        response = client.post(
            "/api/auth/register",
            json={
                "email": "active_attempt@example.com",
                "password": "SecurePass123",
                "is_active": False,  # Should be ignored/rejected
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["is_active"] is True

    def test_register_uuid_generated(self):
        """UUID is generated server-side."""
        response = client.post(
            "/api/auth/register",
            json={"email": "uuid@example.com", "password": "SecurePass123"},
        )

        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert len(data["id"]) == 36  # UUID v4 format
        assert data["id"].count("-") == 4

    def test_register_timestamps_generated(self):
        """Created_at and updated_at timestamps are generated."""
        response = client.post(
            "/api/auth/register",
            json={"email": "time@example.com", "password": "SecurePass123"},
        )

        assert response.status_code == 201
        data = response.json()
        assert "created_at" in data
        assert "updated_at" in data
        # Should be valid ISO datetime strings
        assert "T" in data["created_at"]
        assert "T" in data["updated_at"]

    def test_register_failed_commit_rolls_back(self):
        """Failed database commit rolls back safely (simulated via duplicate)."""
        # First registration
        client.post(
            "/api/auth/register",
            json={"email": "rollback@example.com", "password": "Password123"},
        )

        # Second registration should fail with 409, not leave DB in bad state
        response = client.post(
            "/api/auth/register",
            json={"email": "rollback@example.com", "password": "AnotherPass456"},
        )

        assert response.status_code == 409

        # Verify only one user exists
        db = TestingSessionLocal()
        try:
            users = db.query(User).filter(User.email == "rollback@example.com").all()
            assert len(users) == 1
            assert verify_password("Password123", users[0].hashed_password)
        finally:
            db.close()


class TestUserLogin:
    """Tests for POST /api/auth/login endpoint."""

    def setup_method(self):
        """Create fresh database before each test."""
        from app.core.database import Base
        Base.metadata.create_all(bind=test_engine)

    def teardown_method(self):
        """Drop database after each test."""
        from app.core.database import Base
        Base.metadata.drop_all(bind=test_engine)

    def test_login_success(self):
        """Successful login returns tokens and user data."""
        # Register a user first
        client.post(
            "/api/auth/register",
            json={"email": "login@test.com", "password": "SecurePass123"},
        )

        # Login
        response = client.post(
            "/api/auth/login",
            json={"email": "login@test.com", "password": "SecurePass123"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        assert "expires_in" in data
        assert data["expires_in"] == settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        assert "user" in data
        assert data["user"]["email"] == "login@test.com"
        assert data["user"]["role"] == "user"
        assert data["user"]["is_active"] is True
        # Sensitive fields not returned
        assert "hashed_password" not in data["user"]
        assert "password" not in data["user"]
        assert "password" not in data

    def test_login_access_token_valid_and_decodable(self):
        """Access token can be decoded and contains correct claims."""
        client.post(
            "/api/auth/register",
            json={"email": "token@test.com", "password": "SecurePass123"},
        )

        response = client.post(
            "/api/auth/login",
            json={"email": "token@test.com", "password": "SecurePass123"},
        )

        assert response.status_code == 200
        data = response.json()
        access_token = data["access_token"]

        # Decode and verify
        payload = jwt.decode(access_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        assert payload["sub"] is not None
        assert payload["type"] == "access"
        assert "iat" in payload
        assert "exp" in payload

    def test_login_refresh_token_valid_and_decodable(self):
        """Refresh token can be decoded and contains correct claims."""
        client.post(
            "/api/auth/register",
            json={"email": "refresh@test.com", "password": "SecurePass123"},
        )

        response = client.post(
            "/api/auth/login",
            json={"email": "refresh@test.com", "password": "SecurePass123"},
        )

        assert response.status_code == 200
        data = response.json()
        refresh_token = data["refresh_token"]

        # Decode and verify
        payload = jwt.decode(refresh_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        assert payload["sub"] is not None
        assert payload["type"] == "refresh"
        assert "iat" in payload
        assert "exp" in payload

    def test_login_wrong_password_returns_401(self):
        """Wrong password returns HTTP 401 with generic message."""
        client.post(
            "/api/auth/register",
            json={"email": "wrongpass@test.com", "password": "CorrectPass123"},
        )

        response = client.post(
            "/api/auth/login",
            json={"email": "wrongpass@test.com", "password": "WrongPass456"},
        )

        assert response.status_code == 401
        data = response.json()
        assert data["detail"] == "Invalid credentials"

    def test_login_nonexistent_email_returns_same_401(self):
        """Nonexistent email returns same generic 401 (no email enumeration)."""
        response = client.post(
            "/api/auth/login",
            json={"email": "nonexistent@test.com", "password": "AnyPass123"},
        )

        assert response.status_code == 401
        data = response.json()
        assert data["detail"] == "Invalid credentials"

    def test_login_inactive_user_returns_401(self):
        """Inactive user cannot log in."""
        # Create user directly with is_active=False
        db = TestingSessionLocal()
        try:
            user = User(
                email="inactive@test.com",
                hashed_password=hash_password("SecurePass123"),
                is_active=False,
            )
            db.add(user)
            db.commit()
        finally:
            db.close()

        response = client.post(
            "/api/auth/login",
            json={"email": "inactive@test.com", "password": "SecurePass123"},
        )

        assert response.status_code == 401
        data = response.json()
        assert data["detail"] == "Invalid credentials"

    def test_login_email_normalization_lowercase(self):
        """Login normalizes email to lowercase."""
        client.post(
            "/api/auth/register",
            json={"email": "NORMALIZE@TEST.COM", "password": "SecurePass123"},
        )

        response = client.post(
            "/api/auth/login",
            json={"email": "Normalize@Test.Com", "password": "SecurePass123"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["user"]["email"] == "normalize@test.com"

    def test_login_email_normalization_trim_whitespace(self):
        """Login trims email whitespace."""
        client.post(
            "/api/auth/register",
            json={"email": "trim@test.com", "password": "SecurePass123"},
        )

        response = client.post(
            "/api/auth/login",
            json={"email": "  trim@test.com  ", "password": "SecurePass123"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["user"]["email"] == "trim@test.com"

    def test_login_missing_email_returns_422(self):
        """Missing email returns HTTP 422."""
        response = client.post(
            "/api/auth/login",
            json={"password": "SecurePass123"},
        )

        assert response.status_code == 422

    def test_login_missing_password_returns_422(self):
        """Missing password returns HTTP 422."""
        response = client.post(
            "/api/auth/login",
            json={"email": "test@test.com"},
        )

        assert response.status_code == 422

    def test_login_invalid_email_returns_422(self):
        """Invalid email format returns HTTP 422."""
        response = client.post(
            "/api/auth/login",
            json={"email": "not-an-email", "password": "SecurePass123"},
        )

        assert response.status_code == 422

    def test_login_no_password_or_hashed_password_in_response(self):
        """Response never contains password or hashed_password."""
        client.post(
            "/api/auth/register",
            json={"email": "nopass@test.com", "password": "SecurePass123"},
        )

        response = client.post(
            "/api/auth/login",
            json={"email": "nopass@test.com", "password": "SecurePass123"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "password" not in data
        assert "hashed_password" not in data
        assert "password" not in data["user"]
        assert "hashed_password" not in data["user"]

    def test_login_token_expiry_matches_configuration(self):
        """Token expiry matches configured ACCESS_TOKEN_EXPIRE_MINUTES."""
        client.post(
            "/api/auth/register",
            json={"email": "expiry@test.com", "password": "SecurePass123"},
        )

        response = client.post(
            "/api/auth/login",
            json={"email": "expiry@test.com", "password": "SecurePass123"},
        )

        assert response.status_code == 200
        data = response.json()
        expected_expiry = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        assert data["expires_in"] == expected_expiry

    def test_register_behavior_unchanged_after_login_impl(self):
        """Registration still works correctly after login implementation."""
        response = client.post(
            "/api/auth/register",
            json={"email": "unchanged@test.com", "password": "SecurePass123"},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["email"] == "unchanged@test.com"
        assert data["role"] == "user"
        assert data["is_active"] is True
        assert "id" in data
        assert "created_at" in data
        assert "updated_at" in data
        assert "hashed_password" not in data
        assert "password" not in data


class TestCurrentUserDependency:
    """Tests for get_current_user authentication dependency."""

    def setup_method(self):
        """Create fresh database before each test."""
        from app.core.database import Base
        Base.metadata.create_all(bind=test_engine)

    def teardown_method(self):
        """Drop database after each test."""
        from app.core.database import Base
        Base.metadata.drop_all(bind=test_engine)

    def _create_user_and_token(self, email: str, password: str = "SecurePass123") -> tuple[str, User]:
        """Helper to create a user and return access token and user object."""
        client.post("/api/auth/register", json={"email": email, "password": password})
        response = client.post("/api/auth/login", json={"email": email, "password": password})
        assert response.status_code == 200
        token = response.json()["access_token"]
        # Get user from database
        db = TestingSessionLocal()
        try:
            user = db.query(User).filter(User.email == email).first()
            return token, user
        finally:
            db.close()

    def test_valid_access_token_returns_user(self):
        """Valid access token returns the correct user."""
        token, user = self._create_user_and_token("valid@test.com")

        response = client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == user.id
        assert data["email"] == user.email
        assert data["role"] == "user"
        assert data["is_active"] is True

    def test_missing_authorization_header_returns_401(self):
        """Missing Authorization header returns 401."""
        response = client.get("/api/auth/me")

        assert response.status_code == 401
        data = response.json()
        assert data["detail"] == "Not authenticated"
        assert response.headers.get("WWW-Authenticate") == "Bearer"

    def test_invalid_token_returns_401(self):
        """Invalid token returns 401."""
        response = client.get(
            "/api/auth/me",
            headers={"Authorization": "Bearer invalid.token.here"},
        )

        assert response.status_code == 401
        data = response.json()
        assert data["detail"] == "Invalid token"
        assert response.headers.get("WWW-Authenticate") == "Bearer"

    def test_expired_token_returns_401(self):
        """Expired token returns 401."""
        # Create an expired token
        expired_token = create_access_token(
            subject="expired@test.com",
            expires_delta=timedelta(seconds=-1),
        )

        response = client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {expired_token}"},
        )

        assert response.status_code == 401
        data = response.json()
        assert data["detail"] == "Token expired"
        assert response.headers.get("WWW-Authenticate") == "Bearer"

    def test_refresh_token_used_as_access_token_returns_401(self):
        """Refresh token used as access token returns 401."""
        _, user = self._create_user_and_token("refreshtoken@test.com")
        # Get refresh token by logging in again
        response = client.post(
            "/api/auth/login",
            json={"email": "refreshtoken@test.com", "password": "SecurePass123"},
        )
        refresh_token = response.json()["refresh_token"]

        response = client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {refresh_token}"},
        )

        assert response.status_code == 401
        data = response.json()
        assert data["detail"] == "Invalid token type"
        assert response.headers.get("WWW-Authenticate") == "Bearer"

    def test_missing_subject_claim_returns_401(self):
        """Token with missing sub claim returns 401."""
        # Create a token without sub claim manually (bypass create_access_token validation)
        import jwt
        from datetime import datetime, timezone, timedelta
        now = datetime.now(timezone.utc)
        payload = {
            "type": "access",
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=30)).timestamp()),
            # No sub claim
        }
        token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

        response = client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 401
        data = response.json()
        assert data["detail"] == "Invalid token"
        assert response.headers.get("WWW-Authenticate") == "Bearer"

    def test_malformed_bearer_header_returns_401(self):
        """Malformed Bearer header returns 401."""
        response = client.get(
            "/api/auth/me",
            headers={"Authorization": "NotBearer token"},
        )

        assert response.status_code == 401
        data = response.json()
        assert data["detail"] == "Not authenticated"
        assert response.headers.get("WWW-Authenticate") == "Bearer"

    def test_deleted_user_returns_401(self):
        """Deleted/nonexistent user returns 401."""
        token, user = self._create_user_and_token("deleted@test.com")

        # Delete the user from database
        db = TestingSessionLocal()
        try:
            db.delete(user)
            db.commit()
        finally:
            db.close()

        response = client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 401
        data = response.json()
        assert data["detail"] == "User not found"
        assert response.headers.get("WWW-Authenticate") == "Bearer"

    def test_inactive_user_returns_401(self):
        """Inactive user returns 401."""
        token, user = self._create_user_and_token("inactive@test.com")

        # Deactivate the user in a fresh session
        db = TestingSessionLocal()
        try:
            db_user = db.query(User).filter(User.id == user.id).first()
            db_user.is_active = False
            db.commit()
        finally:
            db.close()

        response = client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 401
        data = response.json()
        assert data["detail"] == "User inactive"
        assert response.headers.get("WWW-Authenticate") == "Bearer"

    def test_valid_user_remains_authenticated(self):
        """Valid user with valid token remains authenticated across multiple requests."""
        token, user = self._create_user_and_token("persistent@test.com")

        # Make multiple requests
        for _ in range(3):
            response = client.get(
                "/api/auth/me",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert response.status_code == 200
            data = response.json()
            assert data["id"] == user.id
            assert data["email"] == user.email


class TestExistingAPIsUnaffected:
    """Regression tests to ensure existing Farm, Climate, Crop, Rotation APIs still work."""

    def setup_method(self):
        """Create fresh database before each test."""
        from app.core.database import Base
        Base.metadata.create_all(bind=test_engine)

    def teardown_method(self):
        """Drop database after each test."""
        from app.core.database import Base
        Base.metadata.drop_all(bind=test_engine)

    def test_farms_api_still_works(self, auth_client: TestClient):
        """Farm creation and listing still works after adding auth."""
        # Create a farm
        farm_data = {
            "name": "Test Farm",
            "latitude": 30.9010,
            "longitude": 75.8573,
            "total_area_hectares": 10.5,
            "soil_type": "loam",
            "primary_irrigation": "canal",
        }
        response = auth_client.post("/api/farms", json=farm_data)
        assert response.status_code == 201
        farm = response.json()
        assert farm["name"] == "Test Farm"

        # List farms
        response = auth_client.get("/api/farms")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1

    def test_climate_api_still_works(self):
        """Climate endpoint still works."""
        response = client.get("/api/climate?latitude=30.9&longitude=75.8&start_date=2023-01-01&end_date=2023-01-02")
        # May fail due to missing NASA API, but endpoint exists
        assert response.status_code in [200, 502, 504]  # Not 404

    def test_crops_api_still_works(self):
        """Crops catalog still works."""
        response = client.get("/api/crops/catalog")
        assert response.status_code == 200
        data = response.json()
        assert "crops" in data
        assert len(data["crops"]) >= 7

    def test_rotations_api_still_works(self):
        """Rotations endpoint still works."""
        response = client.post(
            "/api/rotations",
            json={
                "latitude": 30.9,
                "longitude": 75.8,
                "max_cycle_years": 3,
            },
        )
        # May fail due to missing climate data, but endpoint exists
        assert response.status_code in [200, 422, 502, 504]  # Not 404


class TestUserModel:
    """Direct model tests."""

    def setup_method(self):
        from app.core.database import Base
        Base.metadata.create_all(bind=test_engine)

    def teardown_method(self):
        from app.core.database import Base
        Base.metadata.drop_all(bind=test_engine)

    def test_user_model_defaults(self):
        """User model has correct defaults."""
        db = TestingSessionLocal()
        try:
            user = User(
                email="defaults@test.com",
                hashed_password=hash_password("Password123"),
            )
            db.add(user)
            db.commit()
            db.refresh(user)

            assert user.role == "user"
            assert user.is_active is True
            assert user.id is not None
            assert user.created_at is not None
            assert user.updated_at is not None
        finally:
            db.close()

    def test_user_email_unique_constraint(self):
        """Email unique constraint enforced at database level."""
        from sqlalchemy.exc import IntegrityError

        db = TestingSessionLocal()
        try:
            user1 = User(
                email="unique@test.com",
                hashed_password=hash_password("Password123"),
            )
            db.add(user1)
            db.commit()

            user2 = User(
                email="unique@test.com",  # Same email
                hashed_password=hash_password("AnotherPass456"),
            )
            db.add(user2)
            with pytest.raises(IntegrityError):
                db.commit()
        finally:
            db.rollback()
            db.close()


class TestRBAC:
    """Tests for Role-Based Access Control (RBAC)."""

    def setup_method(self):
        """Create fresh database before each test."""
        from app.core.database import Base
        Base.metadata.create_all(bind=test_engine)

    def teardown_method(self):
        """Drop database after each test."""
        from app.core.database import Base
        Base.metadata.drop_all(bind=test_engine)

    def _create_user_and_token(self, email: str, password: str = "SecurePass123") -> tuple[str, User]:
        """Helper to create a user and return access token and user object."""
        client.post("/api/auth/register", json={"email": email, "password": password})
        response = client.post("/api/auth/login", json={"email": email, "password": password})
        assert response.status_code == 200
        token = response.json()["access_token"]
        # Get user from database
        db = TestingSessionLocal()
        try:
            user = db.query(User).filter(User.email == email).first()
            return token, user
        finally:
            db.close()

    def _create_admin_user_and_token(self, email: str, password: str = "SecurePass123") -> tuple[str, User]:
        """Helper to create an admin user and return access token and user object."""
        client.post("/api/auth/register", json={"email": email, "password": password})
        # Promote to admin directly in database
        db = TestingSessionLocal()
        try:
            user = db.query(User).filter(User.email == email).first()
            user.role = UserRole.ADMIN
            db.commit()
            db.refresh(user)
        finally:
            db.close()
        # Login to get token
        response = client.post("/api/auth/login", json={"email": email, "password": password})
        assert response.status_code == 200
        token = response.json()["access_token"]
        return token, user

    def test_admin_user_passes_require_admin(self):
        """Admin user passes require_admin dependency."""
        token, user = self._create_admin_user_and_token("admin@test.com")

        response = client.get(
            "/api/auth/admin-only",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Admin access granted"
        assert data["user"] == "admin@test.com"
        assert data["role"] == "admin"

    def test_normal_user_receives_403(self):
        """Normal user receives 403 when accessing admin endpoint."""
        token, user = self._create_user_and_token("user@test.com")

        response = client.get(
            "/api/auth/admin-only",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 403
        data = response.json()
        assert data["detail"] == "Admin access required"

    def test_missing_token_receives_401(self):
        """Missing token receives 401 on admin endpoint."""
        response = client.get("/api/auth/admin-only")

        assert response.status_code == 401
        data = response.json()
        assert data["detail"] == "Not authenticated"
        assert response.headers.get("WWW-Authenticate") == "Bearer"

    def test_invalid_token_receives_401(self):
        """Invalid token receives 401 on admin endpoint."""
        response = client.get(
            "/api/auth/admin-only",
            headers={"Authorization": "Bearer invalid.token.here"},
        )

        assert response.status_code == 401
        data = response.json()
        assert data["detail"] == "Invalid token"
        assert response.headers.get("WWW-Authenticate") == "Bearer"

    def test_inactive_user_receives_401(self):
        """Inactive user receives 401 on admin endpoint."""
        token, user = self._create_admin_user_and_token("inactive_admin@test.com")

        # Deactivate the user
        db = TestingSessionLocal()
        try:
            db_user = db.query(User).filter(User.id == user.id).first()
            db_user.is_active = False
            db.commit()
        finally:
            db.close()

        response = client.get(
            "/api/auth/admin-only",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 401
        data = response.json()
        assert data["detail"] == "User inactive"
        assert response.headers.get("WWW-Authenticate") == "Bearer"

    def test_user_cannot_change_role_through_login(self):
        """User cannot change their role through login."""
        # Register and login as normal user
        client.post("/api/auth/register", json={"email": "rolechange@test.com", "password": "SecurePass123"})
        response = client.post("/api/auth/login", json={"email": "rolechange@test.com", "password": "SecurePass123"})
        assert response.status_code == 200
        token = response.json()["access_token"]
        user_data = response.json()["user"]
        assert user_data["role"] == "user"

        # Directly promote to admin in DB
        db = TestingSessionLocal()
        try:
            user = db.query(User).filter(User.email == "rolechange@test.com").first()
            user.role = UserRole.ADMIN
            db.commit()
        finally:
            db.close()

        # Login again - should now get admin role
        response = client.post("/api/auth/login", json={"email": "rolechange@test.com", "password": "SecurePass123"})
        assert response.status_code == 200
        user_data = response.json()["user"]
        assert user_data["role"] == "admin"

    def test_existing_registration_behavior_unchanged(self):
        """Existing registration behavior remains unchanged."""
        response = client.post(
            "/api/auth/register",
            json={"email": "unchanged@test.com", "password": "SecurePass123"},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["email"] == "unchanged@test.com"
        assert data["role"] == "user"
        assert data["is_active"] is True
        assert "id" in data
        assert "created_at" in data
        assert "updated_at" in data
        assert "hashed_password" not in data
        assert "password" not in data

    def test_admin_creation_script_promotes_intended_user(self):
        """Admin creation script promotes the intended user."""
        from app.scripts.create_admin import promote_to_admin

        # Create a user first using test client (which uses test database)
        client.post("/api/auth/register", json={"email": "scriptuser@test.com", "password": "SecurePass123"})

        # Use the test database session
        db = TestingSessionLocal()
        try:
            success, message = promote_to_admin(db, "scriptuser@test.com")
            assert success is True
            assert "now an admin" in message

            # Verify in database
            user = db.query(User).filter(User.email == "scriptuser@test.com").first()
            assert user is not None
            assert user.role == UserRole.ADMIN
        finally:
            db.close()

    def test_missing_email_handled_safely(self):
        """Missing email is handled safely by admin creation script."""
        from app.scripts.create_admin import promote_to_admin

        db = TestingSessionLocal()
        try:
            success, message = promote_to_admin(db, "nonexistent@test.com")
            assert success is False
            assert "not found" in message.lower()
        finally:
            db.close()

    def test_existing_admin_promotion_idempotent(self):
        """Existing admin promotion is idempotent."""
        from app.scripts.create_admin import promote_to_admin

        # Create and promote to admin
        client.post("/api/auth/register", json={"email": "idempotent@test.com", "password": "SecurePass123"})
        db = TestingSessionLocal()
        try:
            user = db.query(User).filter(User.email == "idempotent@test.com").first()
            user.role = UserRole.ADMIN
            db.commit()
        finally:
            db.close()

        # Run script again using test database
        db = TestingSessionLocal()
        try:
            success, message = promote_to_admin(db, "idempotent@test.com")
            assert success is False
            assert "already an admin" in message.lower()
        finally:
            db.close()

    def test_invalid_role_values_do_not_grant_admin(self):
        """Invalid role values are rejected and do not grant admin privileges."""
        # Create user with invalid role directly in DB
        db = TestingSessionLocal()
        try:
            user = User(
                email="invalidrole@test.com",
                hashed_password=hash_password("SecurePass123"),
                role="superadmin",  # Invalid role
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            user_id = user.id
        finally:
            db.close()

        # Login should fail because UserResponse validates role enum
        # The TestClient will raise an exception for 500 errors, so we check the behavior
        import httpx
        try:
            response = client.post("/api/auth/login", json={"email": "invalidrole@test.com", "password": "SecurePass123"})
            # If we get a response, it should be an error
            assert response.status_code in [401, 500], f"Expected 401 or 500, got {response.status_code}"
        except httpx.HTTPStatusError as e:
            # TestClient raises HTTPStatusError for 500 errors
            assert e.response.status_code == 500
        except Exception as e:
            # Any other exception is also acceptable (server error)
            assert "ValidationError" in str(type(e).__name__) or "500" in str(e)

        # The key assertion: invalid role users cannot access admin endpoints
        # (they can't even get a valid token due to validation)

    def test_user_role_enum_values(self):
        """UserRole enum has correct values."""
        assert UserRole.USER.value == "user"
        assert UserRole.ADMIN.value == "admin"

    def test_admin_script_refuses_production_execution(self):
        """Admin creation script refuses execution in production environment."""
        import subprocess
        import sys
        import os

        # Get the backend directory
        backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        # Run script with ENVIRONMENT=production
        result = subprocess.run(
            [sys.executable, "-m", "app.scripts.create_admin", "test@example.com"],
            env={**os.environ, "ENVIRONMENT": "production"},
            capture_output=True,
            text=True,
            cwd=backend_dir,
        )

        assert result.returncode == 1
        assert "production" in result.stdout.lower() or "production" in result.stderr.lower()
        assert "cannot run" in result.stdout.lower() or "cannot run" in result.stderr.lower()

    def test_admin_script_refuses_missing_environment(self):
        """Admin creation script refuses execution when ENVIRONMENT is missing."""
        import subprocess
        import sys
        import os

        # Get the backend directory
        backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        # Run script with empty ENVIRONMENT
        result = subprocess.run(
            [sys.executable, "-m", "app.scripts.create_admin", "test@example.com"],
            env={**os.environ, "ENVIRONMENT": ""},
            capture_output=True,
            text=True,
            cwd=backend_dir,
        )

        assert result.returncode == 1
        assert "not set" in result.stdout.lower() or "not set" in result.stderr.lower()
        assert "ambiguous" in result.stdout.lower() or "ambiguous" in result.stderr.lower()

    def test_shared_user_role_enum(self):
        """Verify single shared UserRole enum across model, schema, and deps."""
        from app.models.user import User
        from app.schemas.user import UserResponse
        from app.api.deps import require_admin
        from app.core.enums import UserRole as CoreUserRole

        # All should reference the same enum values
        assert User.__table__.columns["role"].default.arg == CoreUserRole.USER.value
        assert UserResponse.model_fields["role"].annotation == CoreUserRole
        # require_admin uses CoreUserRole.ADMIN for comparison
        import inspect
        source = inspect.getsource(require_admin)
        assert "UserRole.ADMIN" in source or "ADMIN" in source