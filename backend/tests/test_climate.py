"""Tests for the climate endpoint and NASA POWER service."""

from datetime import date
from typing import Any, Dict
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
import httpx
import pytest

from app.services.nasa_power import nasa_power_service


def test_climate_missing_params_returns_422(client: TestClient):
    """Calling /api/climate without query params should return 422."""
    response = client.get("/api/climate")
    assert response.status_code == 422


def test_climate_invalid_latitude_returns_422(client: TestClient):
    """Latitude outside [-90, 90] must fail validation."""
    response = client.get(
        "/api/climate",
        params={
            "latitude": 95.0,
            "longitude": 77.2,
            "start_date": "2023-01-01",
            "end_date": "2023-01-05",
        },
    )
    assert response.status_code == 422
    assert "latitude" in str(response.json()).lower()


def test_climate_invalid_longitude_returns_422(client: TestClient):
    """Longitude outside [-180, 180] must fail validation."""
    response = client.get(
        "/api/climate",
        params={
            "latitude": 28.6,
            "longitude": -190.0,
            "start_date": "2023-01-01",
            "end_date": "2023-01-05",
        },
    )
    assert response.status_code == 422
    assert "longitude" in str(response.json()).lower()


def test_climate_inverted_dates_returns_422(client: TestClient):
    """start_date after end_date must return 422 error."""
    response = client.get(
        "/api/climate",
        params={
            "latitude": 28.6,
            "longitude": 77.2,
            "start_date": "2023-01-10",
            "end_date": "2023-01-05",
        },
    )
    assert response.status_code == 422
    assert "cannot be after end_date" in response.json()["detail"]


def test_climate_excessive_date_range_returns_422(client: TestClient):
    """Date span exceeding 366 days must return 422 error."""
    response = client.get(
        "/api/climate",
        params={
            "latitude": 28.6,
            "longitude": 77.2,
            "start_date": "2020-01-01",
            "end_date": "2022-01-01",
        },
    )
    assert response.status_code == 422
    assert "exceeds maximum allowed limit" in response.json()["detail"]


def test_climate_future_dates_returns_422(client: TestClient):
    """Dates in the future must return 422."""
    response = client.get(
        "/api/climate",
        params={
            "latitude": 28.6,
            "longitude": 77.2,
            "start_date": "2099-01-01",
            "end_date": "2099-01-05",
        },
    )
    assert response.status_code == 422
    assert "cannot be in the future" in response.json()["detail"]


def test_climate_success_with_mocked_nasa_response(
    client: TestClient, sample_nasa_power_payload: Dict[str, Any]
):
    """Verify data parsing, scientific metadata, null handling, and summary statistics."""
    # Directly test parse_nasa_response to verify scientific processing
    parsed = nasa_power_service.parse_nasa_response(
        raw_data=sample_nasa_power_payload,
        latitude=28.6139,
        longitude=77.2090,
        start_date=date(2023, 1, 1),
        end_date=date(2023, 1, 3),
    )

    # 1. Scientific integrity: is_simulated MUST be False
    assert parsed.metadata.is_simulated is False

    # 2. Distinct spatial resolutions per parameter
    t2m_info = parsed.metadata.parameters_info["T2M"]
    solar_info = parsed.metadata.parameters_info["ALLSKY_SFC_SW_DWN"]
    assert "0.5° latitude x 0.625° longitude" in t2m_info.spatial_resolution
    assert "1.0° latitude x 1.0° longitude" in solar_info.spatial_resolution
    assert "MERRA-2" in t2m_info.source
    assert "CERES" in solar_info.source

    # 3. Missing parameter handling (-999.0 converted to None)
    records = {r.date: r for r in parsed.records}
    assert "2023-01-02" in records
    day2 = records["2023-01-02"]
    assert day2.temperature_mean_c is None
    assert "T2M" in day2.missing_parameters

    assert "2023-01-03" in records
    day3 = records["2023-01-03"]
    assert day3.precipitation_mm is None
    assert "PRECTOTCORR" in day3.missing_parameters

    # 4. Correct statistical calculations ignoring nulls
    # T2M valid values: 13.5 and 14.8 -> mean 14.15
    assert parsed.summary.avg_temperature_c == 14.15
    # Min temperature: 6.8
    assert parsed.summary.min_temperature_c == 6.8
    # Max temperature: 21.0
    assert parsed.summary.max_temperature_c == 21.0
    # Total precipitation: 0.0 + 4.5 = 4.5
    assert parsed.summary.total_precipitation_mm == 4.5
    assert parsed.summary.total_days == 3
    assert parsed.summary.valid_data_days == 3


def test_climate_endpoint_full_flow_with_mock(
    client: TestClient, sample_nasa_power_payload: Dict[str, Any]
):
    """Test full HTTP GET /api/climate call with mocked NASA service."""
    with patch.object(
        nasa_power_service,
        "fetch_climate_data",
        new_callable=AsyncMock,
    ) as mock_fetch:
        mock_response = nasa_power_service.parse_nasa_response(
            raw_data=sample_nasa_power_payload,
            latitude=28.6139,
            longitude=77.2090,
            start_date=date(2023, 1, 1),
            end_date=date(2023, 1, 3),
        )
        mock_fetch.return_value = mock_response

        response = client.get(
            "/api/climate",
            params={
                "latitude": 28.6139,
                "longitude": 77.2090,
                "start_date": "2023-01-01",
                "end_date": "2023-01-03",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["metadata"]["is_simulated"] is False
        assert len(data["records"]) == 3
        assert data["summary"]["total_days"] == 3


def test_nasa_api_upstream_error_raises_502(client: TestClient):
    """When upstream NASA POWER API returns an error status code, return 502."""
    mock_resp = httpx.Response(status_code=500, text="Internal Server Error")

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_resp

        response = client.get(
            "/api/climate",
            params={
                "latitude": 28.6139,
                "longitude": 77.2090,
                "start_date": "2023-01-01",
                "end_date": "2023-01-03",
            },
        )
        assert response.status_code == 502
        assert "NASA POWER API error" in response.json()["detail"]


def test_nasa_api_timeout_raises_504(client: TestClient):
    """When upstream NASA POWER API times out, return 504."""
    with patch("httpx.AsyncClient.get", side_effect=httpx.TimeoutException("Timeout")):
        response = client.get(
            "/api/climate",
            params={
                "latitude": 28.6139,
                "longitude": 77.2090,
                "start_date": "2023-01-01",
                "end_date": "2023-01-03",
            },
        )
        assert response.status_code == 504
        assert "timed out" in response.json()["detail"]
