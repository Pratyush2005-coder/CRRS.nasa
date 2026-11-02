"""Comprehensive tests for NASA Climate Intelligence Analyzer service and endpoints."""

from datetime import date
from typing import Any, Dict, List
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
import httpx
import pytest

from app.schemas.climate import (
    ClimateMetadata,
    ClimateResponse,
    ClimateSummary,
    Coordinates,
    DailyClimateRecord,
    DateRange,
)
from app.schemas.climate_analyzer import (
    CompletenessCategory,
    HeatRiskLevel,
    ColdRiskLevel,
    ThermalCompatibility,
    WaterCompatibility,
)
from app.services.climate_analyzer import climate_analyzer_service
from app.services.nasa_power import nasa_power_service


def get_mock_climate_response() -> ClimateResponse:
    """Create a structured ClimateResponse spanning 10 distinct days with known weather events."""
    # 10 days of January 2023:
    # Days 1-3: Normal winter weather in West Bengal (Tmax ~24, Tmin ~13, dry)
    # Days 4-5: Cold wave (Day 4: Tmin 4.5 -> cold stress; Day 5: Tmin 1.8 -> near-freezing hazard)
    # Days 6-7: Unseasonal rain (Day 6: 12.0 mm, Day 7: 35.5 mm)
    # Day 8: Heat spike (Tmax 36.0 -> heat stress)
    # Day 9: Extreme heat spike (Tmax 41.0 -> extreme heat stress)
    # Day 10: Missing temperature (null / -999.0)
    records = [
        DailyClimateRecord(
            date="2023-01-01",
            temperature_mean_c=18.5,
            temperature_max_c=24.0,
            temperature_min_c=13.0,
            precipitation_mm=0.0,
            solar_radiation_mj_m2=14.5,
            relative_humidity_pct=65.0,
            missing_parameters=[],
        ),
        DailyClimateRecord(
            date="2023-01-02",
            temperature_mean_c=17.8,
            temperature_max_c=23.5,
            temperature_min_c=12.1,
            precipitation_mm=0.0,
            solar_radiation_mj_m2=15.0,
            relative_humidity_pct=62.0,
            missing_parameters=[],
        ),
        DailyClimateRecord(
            date="2023-01-03",
            temperature_mean_c=16.0,
            temperature_max_c=22.0,
            temperature_min_c=10.0,
            precipitation_mm=0.0,
            solar_radiation_mj_m2=13.8,
            relative_humidity_pct=60.0,
            missing_parameters=[],
        ),
        DailyClimateRecord(
            date="2023-01-04",
            temperature_mean_c=12.0,
            temperature_max_c=19.5,
            temperature_min_c=4.5,  # Cold stress (<= 5°C)
            precipitation_mm=0.0,
            solar_radiation_mj_m2=16.2,
            relative_humidity_pct=55.0,
            missing_parameters=[],
        ),
        DailyClimateRecord(
            date="2023-01-05",
            temperature_mean_c=10.5,
            temperature_max_c=19.2,
            temperature_min_c=1.8,  # Near-freezing hazard (<= 2°C)
            precipitation_mm=0.0,
            solar_radiation_mj_m2=16.5,
            relative_humidity_pct=50.0,
            missing_parameters=[],
        ),
        DailyClimateRecord(
            date="2023-01-06",
            temperature_mean_c=18.0,
            temperature_max_c=22.0,
            temperature_min_c=14.0,
            precipitation_mm=12.0,  # Rainy day
            solar_radiation_mj_m2=8.5,
            relative_humidity_pct=88.0,
            missing_parameters=[],
        ),
        DailyClimateRecord(
            date="2023-01-07",
            temperature_mean_c=17.5,
            temperature_max_c=21.0,
            temperature_min_c=14.0,
            precipitation_mm=35.5,  # Heavy rainy day (wet spell = 2)
            solar_radiation_mj_m2=6.2,
            relative_humidity_pct=92.0,
            missing_parameters=[],
        ),
        DailyClimateRecord(
            date="2023-01-08",
            temperature_mean_c=28.5,
            temperature_max_c=36.0,  # Heat stress (>= 35°C)
            temperature_min_c=21.0,
            precipitation_mm=0.0,
            solar_radiation_mj_m2=18.0,
            relative_humidity_pct=58.0,
            missing_parameters=[],
        ),
        DailyClimateRecord(
            date="2023-01-09",
            temperature_mean_c=32.0,
            temperature_max_c=41.0,  # Extreme heat stress (>= 40°C)
            temperature_min_c=23.0,
            precipitation_mm=0.0,
            solar_radiation_mj_m2=19.5,
            relative_humidity_pct=45.0,
            missing_parameters=[],
        ),
        DailyClimateRecord(
            date="2023-01-10",
            temperature_mean_c=None,  # Missing parameter (-999.0 converted to None)
            temperature_max_c=None,
            temperature_min_c=None,
            precipitation_mm=0.0,
            solar_radiation_mj_m2=14.0,
            relative_humidity_pct=60.0,
            missing_parameters=["T2M", "T2M_MAX", "T2M_MIN"],
        ),
    ]

    metadata = ClimateMetadata(
        data_source="NASA Langley Research Center POWER Project - AG Community",
        retrieval_timestamp="2026-11-02T12:00:00Z",
        coordinates=Coordinates(latitude=22.5726, longitude=88.3639),
        date_range=DateRange(start_date="2023-01-01", end_date="2023-01-10"),
        parameters_info={},
        data_limitations="MERRA-2 0.5° x 0.625° reanalysis",
        is_simulated=False,
    )

    summary = ClimateSummary(
        avg_temperature_c=18.98,
        min_temperature_c=1.8,
        max_temperature_c=41.0,
        total_precipitation_mm=47.5,
        avg_precipitation_daily_mm=4.75,
        avg_solar_radiation_mj_m2=14.22,
        avg_relative_humidity_pct=65.0,
        total_days=10,
        valid_data_days=10,
    )

    return ClimateResponse(
        metadata=metadata,
        summary=summary,
        records=records,
    )


def test_climate_analysis_metric_calculations_unit():
    """Verify detailed statistical and agronomic calculations on structured records."""
    mock_response = get_mock_climate_response()
    report = climate_analyzer_service.analyze_climate_response(mock_response)

    # 1. Missing Data Analysis
    missing = report.missing_data
    assert missing.total_days_in_period == 10
    assert missing.valid_observation_days == 10
    assert missing.missing_observation_days == 0
    assert missing.data_completeness_pct == 100.0
    assert missing.completeness_category == CompletenessCategory.EXCELLENT
    assert missing.missing_parameters_summary.get("T2M") == 1
    assert missing.missing_parameters_summary.get("T2M_MAX") == 1

    # 2. Rainfall Analysis
    # Total precipitation: 12.0 + 35.5 = 47.5 mm
    rain = report.rainfall_analysis
    assert rain.total_rainfall_mm == 47.5
    assert rain.mean_daily_rainfall_mm == 4.75
    assert rain.max_single_day_rainfall_mm == 35.5
    assert rain.rainy_days_count == 2
    assert rain.dry_days_count == 8
    # Days 1-5 dry (5 days)
    assert rain.consecutive_dry_days_max == 5
    # Days 6-7 wet (2 days)
    assert rain.consecutive_wet_days_max == 2
    assert rain.rainfall_variance is not None
    assert rain.rainfall_std_dev is not None

    # 3. Monthly and Seasonal Breakdown
    assert len(report.monthly_rainfall) == 1
    assert report.monthly_rainfall[0].year_month == "2023-01"
    assert report.monthly_rainfall[0].total_mm == 47.5

    seasons = {s.season_name: s for s in report.seasonal_rainfall}
    assert "Rabi / Winter" in seasons
    assert seasons["Rabi / Winter"].total_rainfall_mm == 47.5
    assert seasons["Rabi / Winter"].percentage_of_total == 100.0

    # 4. Temperature Analysis
    temp = report.temperature_analysis
    assert temp.lowest_recorded_min_c == 1.8
    assert temp.highest_recorded_max_c == 41.0
    assert temp.mean_temperature_c is not None
    assert temp.mean_diurnal_range_c is not None

    # 5. Heat-Risk Indicators
    # Day 8: 36.0 (>= 35), Day 9: 41.0 (>= 35 and >= 40) -> 2 heat stress days, 1 extreme heat day
    heat = report.heat_risk
    assert heat.heat_stress_days_count == 2
    assert heat.extreme_heat_days_count == 1
    assert heat.heat_risk_level in (HeatRiskLevel.HIGH, HeatRiskLevel.EXTREME)
    assert "35.0°C" in heat.threshold_note

    # 6. Cold-Risk Indicators
    # Day 4: 4.5 (<= 5), Day 5: 1.8 (<= 5 and <= 2) -> 2 cold stress days, 1 near-freezing hazard day
    cold = report.cold_risk
    assert cold.cold_stress_days_count == 2
    assert cold.near_freezing_hazard_days_count == 1
    assert cold.frost_hazard_level == ColdRiskLevel.MODERATE
    assert "not direct field-level frost probabilities" in cold.scientific_caveat.lower()


def test_gdd_calculation_verified_vs_unverified():
    """Verify that GDD sums accurately for verified crops and skips missing days."""
    mock_response = get_mock_climate_response()
    report = climate_analyzer_service.analyze_climate_response(mock_response)

    gdd_by_crop = {g.crop_id: g for g in report.gdd_summary}

    # Rice: Tbase = 10.0°C
    # Wheat: Tbase = 5.0°C
    # Both must be verified
    assert "wheat" in gdd_by_crop
    assert "rice" in gdd_by_crop

    wheat_gdd = gdd_by_crop["wheat"]
    assert wheat_gdd.is_verified_base is True
    assert wheat_gdd.gdd_base_temp_c == 5.0
    # Day 10 missing Tmax/Tmin -> valid days should be 9
    assert wheat_gdd.valid_gdd_days == 9
    assert wheat_gdd.accumulated_gdd is not None
    assert wheat_gdd.accumulated_gdd > 0.0

    rice_gdd = gdd_by_crop["rice"]
    assert rice_gdd.is_verified_base is True
    assert rice_gdd.gdd_base_temp_c == 10.0
    assert rice_gdd.valid_gdd_days == 9
    assert rice_gdd.accumulated_gdd is not None
    # Because Tbase for rice (10) > wheat (5), accumulated GDD for rice must be less than wheat
    assert rice_gdd.accumulated_gdd < wheat_gdd.accumulated_gdd


def test_crop_climate_suitability_evaluation():
    """Verify that thermal and hydrological suitability reflects crop benchmarks."""
    mock_response = get_mock_climate_response()
    report = climate_analyzer_service.analyze_climate_response(mock_response)

    suitability_by_crop = {s.crop_id: s for s in report.crop_suitability}

    # Rice has very high water demand (>900 mm). Total rainfall is 47.5 mm -> IRRIGATION_DEPENDENT
    rice_s = suitability_by_crop["rice"]
    assert rice_s.water_compatibility == WaterCompatibility.IRRIGATION_DEPENDENT
    assert any("irrigation" in c.lower() for c in rice_s.agronomic_caveats)

    # Wheat was exposed to 2 heat stress days -> should reflect in caveats
    wheat_s = suitability_by_crop["wheat"]
    assert any("heat" in c.lower() for c in wheat_s.agronomic_caveats)
    assert wheat_s.overall_climate_score is not None
    assert 0.0 <= wheat_s.overall_climate_score <= 100.0


def test_api_get_climate_analysis_success_with_mock(client: TestClient):
    """GET /api/climate/analysis should return complete report with mocked NASA response."""
    mock_resp = get_mock_climate_response()

    with patch.object(
        nasa_power_service,
        "fetch_climate_data",
        new_callable=AsyncMock,
    ) as mock_fetch:
        mock_fetch.return_value = mock_resp

        response = client.get(
            "/api/climate/analysis",
            params={
                "latitude": 22.5726,
                "longitude": 88.3639,
                "start_date": "2023-01-01",
                "end_date": "2023-01-10",
            },
        )
        assert response.status_code == 200
        data = response.json()

        assert data["date_range_days"] == 10
        assert data["metadata"]["is_simulated"] is False
        assert "rainfall_analysis" in data
        assert "temperature_analysis" in data
        assert "heat_risk" in data
        assert "cold_risk" in data
        assert "gdd_summary" in data
        assert "crop_suitability" in data
        assert "scientific_provenance" in data
        assert "MERRA-2" in data["scientific_provenance"]


def test_api_get_climate_analysis_alias_endpoint(client: TestClient):
    """GET /api/climate/intelligence should function identically as an alias."""
    mock_resp = get_mock_climate_response()

    with patch.object(
        nasa_power_service,
        "fetch_climate_data",
        new_callable=AsyncMock,
    ) as mock_fetch:
        mock_fetch.return_value = mock_resp

        response = client.get(
            "/api/climate/intelligence",
            params={
                "latitude": 22.5726,
                "longitude": 88.3639,
                "start_date": "2023-01-01",
                "end_date": "2023-01-10",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["rainfall_analysis"]["total_rainfall_mm"] == 47.5


def test_api_get_climate_analysis_filtered_by_crop(client: TestClient):
    """Specifying crop_id in query should narrow GDD and suitability output."""
    mock_resp = get_mock_climate_response()

    with patch.object(
        nasa_power_service,
        "fetch_climate_data",
        new_callable=AsyncMock,
    ) as mock_fetch:
        mock_fetch.return_value = mock_resp

        response = client.get(
            "/api/climate/analysis",
            params={
                "latitude": 22.5726,
                "longitude": 88.3639,
                "start_date": "2023-01-01",
                "end_date": "2023-01-10",
                "crop_id": "lentil",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["gdd_summary"]) == 1
        assert data["gdd_summary"][0]["crop_id"] == "lentil"
        assert len(data["crop_suitability"]) == 1
        assert data["crop_suitability"][0]["crop_id"] == "lentil"


def test_api_get_climate_analysis_validation_errors(client: TestClient):
    """Query parameter validation: dates, bounds, range limit."""
    # Inverted dates
    r_inv = client.get(
        "/api/climate/analysis",
        params={
            "latitude": 22.57,
            "longitude": 88.36,
            "start_date": "2023-01-10",
            "end_date": "2023-01-01",
        },
    )
    assert r_inv.status_code == 422
    assert "cannot be after end_date" in r_inv.json()["detail"]

    # Future dates
    r_fut = client.get(
        "/api/climate/analysis",
        params={
            "latitude": 22.57,
            "longitude": 88.36,
            "start_date": "2099-01-01",
            "end_date": "2099-01-10",
        },
    )
    assert r_fut.status_code == 422
    assert "cannot be in the future" in r_fut.json()["detail"]

    # Excessive range (> 366 days)
    r_range = client.get(
        "/api/climate/analysis",
        params={
            "latitude": 22.57,
            "longitude": 88.36,
            "start_date": "2020-01-01",
            "end_date": "2022-01-01",
        },
    )
    assert r_range.status_code == 422
    assert "exceeds maximum allowed limit" in r_range.json()["detail"]

    # Invalid latitude
    r_lat = client.get(
        "/api/climate/analysis",
        params={
            "latitude": 95.0,
            "longitude": 88.36,
            "start_date": "2023-01-01",
            "end_date": "2023-01-10",
        },
    )
    assert r_lat.status_code == 422


def test_api_get_farm_climate_analysis(client: TestClient):
    """GET /api/farms/{farm_id}/climate-analysis should fetch farm coords and compute report."""
    # 1. Create a test farm profile
    farm_payload = {
        "name": "Burdwan Seed Farm",
        "latitude": 23.2324,
        "longitude": 87.8615,
        "total_area_hectares": 18.0,
        "soil_type": "clay_loam",
        "primary_irrigation": "canal",
        "current_crop": "Wheat",
    }
    farm_resp = client.post("/api/farms", json=farm_payload)
    assert farm_resp.status_code == 201
    farm_id = farm_resp.json()["id"]

    mock_resp = get_mock_climate_response()

    with patch.object(
        nasa_power_service,
        "fetch_climate_data",
        new_callable=AsyncMock,
    ) as mock_fetch:
        mock_fetch.return_value = mock_resp

        response = client.get(
            f"/api/farms/{farm_id}/climate-analysis",
            params={
                "start_date": "2023-01-01",
                "end_date": "2023-01-10",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["date_range_days"] == 10
        # Check that current_crop ('wheat') was automatically selected
        assert len(data["gdd_summary"]) == 1
        assert data["gdd_summary"][0]["crop_id"] == "wheat"

    # Non-existent farm returns 404
    r_404 = client.get(
        "/api/farms/00000000-0000-0000-0000-000000000000/climate-analysis",
        params={"start_date": "2023-01-01", "end_date": "2023-01-10"},
    )
    assert r_404.status_code == 404


def test_upstream_nasa_failure_and_timeout(client: TestClient):
    """Verify proper 502 / 504 error propagation when upstream NASA API fails."""
    # Upstream 500
    mock_resp = httpx.Response(status_code=500, text="Internal Server Error")
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_resp
        response = client.get(
            "/api/climate/analysis",
            params={
                "latitude": 22.57,
                "longitude": 88.36,
                "start_date": "2023-01-01",
                "end_date": "2023-01-10",
            },
        )
        assert response.status_code == 502

    # Upstream Timeout
    with patch("httpx.AsyncClient.get", side_effect=httpx.TimeoutException("Timeout")):
        response = client.get(
            "/api/climate/analysis",
            params={
                "latitude": 22.57,
                "longitude": 88.36,
                "start_date": "2023-01-01",
                "end_date": "2023-01-10",
            },
        )
        assert response.status_code == 504



def test_climate_analyzer_caching():
    """Verify report caching avoids redundant computations."""

    climate_analyzer_service.clear_cache()

    mock_resp = get_mock_climate_response()

    # Pre-populate cache directly
    rep = climate_analyzer_service.analyze_climate_response(mock_resp)

    climate_analyzer_service.cache[
        (22.573, 88.364, "2023-01-01", "2023-01-10", None)
    ] = (
        mock_resp.metadata.retrieval_timestamp,
        rep,
    )

    # Calling clear_cache flushes it
    climate_analyzer_service.clear_cache()

    assert len(climate_analyzer_service.cache) == 0
