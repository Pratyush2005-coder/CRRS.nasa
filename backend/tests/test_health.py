"""Tests for the health check endpoint."""

from fastapi.testclient import TestClient


def test_health_check_returns_200(client: TestClient):
    """GET /api/health should return HTTP 200 with service details."""
    response = client.get("/api/health")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "AGROVERSE AI Backend"
    assert data["version"] == "0.1.0"
    assert "timestamp" in data
    assert "environment" in data


def test_root_endpoint_returns_links(client: TestClient):
    """GET / should return links to API docs and health endpoints."""
    response = client.get("/")
    assert response.status_code == 200

    data = response.json()
    assert "docs" in data
    assert data["api_health"] == "/api/health"
    assert data["climate_endpoint"] == "/api/climate"
