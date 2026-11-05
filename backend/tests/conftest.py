"""Pytest configuration and shared fixtures."""

import sys
from pathlib import Path
from typing import Any, Dict
import pytest
from fastapi.testclient import TestClient

# Ensure backend root is on sys.path for test imports
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.main import app  # noqa: E402

# Disable rate limiting for tests
from app.core.rate_limiting import get_limiter
get_limiter().enabled = False


# Import rate limiting fixtures
from tests.fixtures.rate_limiting import reset_rate_limiter  # noqa: F401

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.core.database import Base, get_db
from app.core.security import create_access_token, create_refresh_token
from app.models.user import User

# Isolated in-memory SQLite database for testing
SQLALCHEMY_TEST_DATABASE_URL = "sqlite:///:memory:"

test_engine = create_engine(
    SQLALCHEMY_TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(autouse=True)
def setup_test_db():
    """Create fresh database tables before each test and drop afterwards."""
    import app.models.farm  # noqa: F401
    import app.models.user  # noqa: F401
    import app.models.login_attempt  # noqa: F401
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


def _create_test_client(headers: Dict[str, str] = None) -> TestClient:
    """Create a TestClient with database dependency override."""
    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    test_client = TestClient(app)
    if headers:
        test_client.headers.update(headers)
    return test_client


@pytest.fixture
def client(setup_test_db) -> TestClient:
    """FastAPI TestClient fixture with isolated in-memory database."""
    return _create_test_client()


@pytest.fixture
def test_user(setup_test_db) -> User:
    """Create a test user in the database."""
    from app.core.security import hash_password
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
        db.refresh(user)
        return user
    finally:
        db.close()


@pytest.fixture
def test_admin(setup_test_db) -> User:
    """Create a test admin user in the database."""
    db = TestingSessionLocal()
    try:
        admin = User(
            id="test-admin-123",
            email="admin@example.com",
            hashed_password="hashed_password",
            role="admin",
            is_active=True,
        )
        db.add(admin)
        db.commit()
        db.refresh(admin)
        return admin
    finally:
        db.close()


@pytest.fixture
def auth_headers(test_user: User) -> Dict[str, str]:
    """Generate authentication headers for a test user."""
    access_token = create_access_token(test_user.id)
    return {"Authorization": f"Bearer {access_token}"}


@pytest.fixture
def admin_headers(test_admin: User) -> Dict[str, str]:
    """Generate authentication headers for a test admin."""
    access_token = create_access_token(test_admin.id)
    return {"Authorization": f"Bearer {access_token}"}


@pytest.fixture
def auth_client(auth_headers: Dict[str, str]) -> TestClient:
    """TestClient with authentication headers pre-configured."""
    return _create_test_client(auth_headers)


@pytest.fixture
def admin_client(admin_headers: Dict[str, str]) -> TestClient:
    """TestClient with admin authentication headers pre-configured."""
    return _create_test_client(admin_headers)


@pytest.fixture
def sample_nasa_power_payload() -> Dict[str, Any]:
    """Sample authentic-format NASA POWER API response including missing values (-999.0)."""
    return {
        "type": "Feature",
        "geometry": {
            "type": "Point",
            "coordinates": [77.2090, 28.6139, 216.0],
        },
        "properties": {
            "parameter": {
                "T2M": {
                    "20230101": 13.5,
                    "20230102": -999.0,  # Missing parameter
                    "20230103": 14.8,
                },
                "T2M_MAX": {
                    "20230101": 19.8,
                    "20230102": 18.5,
                    "20230103": 21.0,
                },
                "T2M_MIN": {
                    "20230101": 7.1,
                    "20230102": 6.8,
                    "20230103": 8.0,
                },
                "PRECTOTCORR": {
                    "20230101": 0.0,
                    "20230102": 4.5,
                    "20230103": -999.0,  # Missing precipitation
                },
                "ALLSKY_SFC_SW_DWN": {
                    "20230101": 12.45,
                    "20230102": 9.8,
                    "20230103": 13.1,
                },
                "RH2M": {
                    "20230101": 68.4,
                    "20230102": 82.1,
                    "20230103": 65.0,
                },
            }
        },
        "header": {
            "title": "NASA POWER Agroclimatology Daily",
            "api": {"version": "v2.0.0"},
        },
        "messages": [],
        "parameters": {
            "T2M": "Temperature at 2 Meters",
            "T2M_MAX": "Maximum Temperature at 2 Meters",
            "T2M_MIN": "Minimum Temperature at 2 Meters",
            "PRECTOTCORR": "Precipitation Corrected",
            "ALLSKY_SFC_SW_DWN": "All Sky Surface Shortwave Downward Irradiance",
            "RH2M": "Relative Humidity at 2 Meters",
        },
    }
