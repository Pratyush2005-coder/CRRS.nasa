"""Tests for the health check endpoint."""

from unittest.mock import patch
from fastapi.testclient import TestClient


def test_health_check_returns_200(client: TestClient):
    """GET /api/health should return HTTP 200 with service details when DB is healthy."""
    response = client.get("/api/health")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "AGROVERSE AI Backend"
    assert data["version"] == "0.1.0"
    assert "timestamp" in data
    assert "environment" in data


def test_health_check_returns_503_when_database_unavailable(client: TestClient):
    """GET /api/health should return HTTP 503 when database is unreachable."""
    with patch("app.api.routes.health.check_database_connectivity", return_value=False):
        response = client.get("/api/health")
        assert response.status_code == 503

        data = response.json()
        assert data["status"] == "unhealthy"
        assert data["service"] == "AGROVERSE AI Backend"
        assert data["version"] == "0.1.0"
        assert "timestamp" in data
        assert "environment" in data


def test_health_check_no_sensitive_info_on_failure(client: TestClient):
    """Health check failure response must not expose database credentials or internal errors."""
    with patch("app.api.routes.health.check_database_connectivity", return_value=False):
        response = client.get("/api/health")
        assert response.status_code == 503

        data = response.json()
        # Ensure no sensitive information leaked
        response_text = str(data).lower()
        assert "password" not in response_text
        assert "credential" not in response_text
        assert "connection" not in response_text
        assert "url" not in response_text
        assert "traceback" not in response_text
        assert "exception" not in response_text
        assert "sqlalchemy" not in response_text
        assert "engine" not in response_text


def test_health_check_connection_exception_safe_response(client: TestClient):
    """Health check handles connection exceptions safely without exposing details."""
    with patch("app.api.routes.health.check_database_connectivity", side_effect=Exception("connection refused")):
        response = client.get("/api/health")
        # Should not crash, should return 503
        assert response.status_code == 503

        data = response.json()
        assert data["status"] == "unhealthy"
        # No internal exception details
        assert "connection refused" not in str(data).lower()


def test_root_endpoint_returns_links(client: TestClient):
    """GET / should return links to API docs and health endpoints."""
    response = client.get("/")
    assert response.status_code == 200

    data = response.json()
    assert "docs" in data
    assert data["api_health"] == "/api/health"
    assert data["climate_endpoint"] == "/api/climate"
