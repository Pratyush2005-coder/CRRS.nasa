"""Integration tests for Rotation API endpoints (Phase 3B-3)."""

from datetime import date
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.rotation import RotationRecommendation, StrategyType
from app.schemas.farm import SoilType, IrrigationType


client = TestClient(app)


# -------------------------------------------------------------------------
# Fixtures
# -------------------------------------------------------------------------

@pytest.fixture
def valid_rotation_request():
    """Valid coordinate-based rotation request."""
    return {
        "latitude": 22.5726,
        "longitude": 88.3639,
        "max_cycle_years": 2,
        "irrigation_type": "canal",
        "exclude_crops": [],
        "previous_crops": [],
    }


@pytest.fixture
def mock_climate_report():
    """Create a mock climate intelligence report."""
    from app.schemas.climate_analyzer import (
        ClimateIntelligenceReport,
        MissingDataAnalysis,
        CompletenessCategory,
        RainfallAnalysis,
        TemperatureAnalysis,
        HeatRiskIndicators,
        HeatRiskLevel,
        ColdRiskIndicators,
        ColdRiskLevel,
        CropClimateSuitability,
        ThermalCompatibility,
        WaterCompatibility,
    )
    from app.schemas.climate import ClimateMetadata, Coordinates, DateRange

    return ClimateIntelligenceReport(
        metadata=ClimateMetadata(
            data_source="NASA POWER Test",
            retrieval_timestamp=date.today(),
            coordinates=Coordinates(latitude=22.57, longitude=88.36),
            date_range=DateRange(start_date="2023-01-01", end_date="2023-12-31"),
            parameters_info={},
            data_limitations="Test data",
            is_simulated=True,
        ),
        date_range_days=365,
        missing_data=MissingDataAnalysis(
            total_days_in_period=365,
            valid_observation_days=365,
            missing_observation_days=0,
            data_completeness_pct=100.0,
            completeness_category=CompletenessCategory.EXCELLENT,
            missing_parameters_summary={},
        ),
        rainfall_analysis=RainfallAnalysis(
            total_rainfall_mm=1200.0,
            mean_daily_rainfall_mm=3.3,
            max_single_day_rainfall_mm=50.0,
            rainy_days_count=80,
            dry_days_count=285,
            consecutive_dry_days_max=15,
            consecutive_wet_days_max=5,
            rainfall_variance=100.0,
            rainfall_std_dev=10.0,
        ),
        seasonal_rainfall=[],
        monthly_rainfall=[],
        temperature_analysis=TemperatureAnalysis(
            mean_temperature_c=26.0,
            lowest_recorded_min_c=12.0,
            highest_recorded_max_c=36.0,
            mean_daily_min_c=20.0,
            mean_daily_max_c=32.0,
            mean_diurnal_range_c=12.0,
        ),
        heat_risk=HeatRiskIndicators(
            heat_stress_days_count=0,
            extreme_heat_days_count=0,
            heat_risk_level=HeatRiskLevel.NONE,
            threshold_note="",
        ),
        cold_risk=ColdRiskIndicators(
            cold_stress_days_count=0,
            near_freezing_hazard_days_count=0,
            frost_hazard_level=ColdRiskLevel.NONE,
            scientific_caveat="",
        ),
        gdd_summary=[],
        crop_suitability=[
            CropClimateSuitability(
                crop_id="rice",
                crop_name="Rice (Paddy)",
                thermal_compatibility=ThermalCompatibility.OPTIMAL,
                water_compatibility=WaterCompatibility.OPTIMAL,
                overall_climate_score=90.0,
                observed_mean_temp_c=26.0,
                crop_optimal_temp_range="22 - 32 °C",
                observed_rainfall_mm=1200.0,
                crop_water_need_mm_range="900 - 1500 mm",
                agronomic_caveats=[],
            ),
            CropClimateSuitability(
                crop_id="wheat",
                crop_name="Wheat",
                thermal_compatibility=ThermalCompatibility.OPTIMAL,
                water_compatibility=WaterCompatibility.OPTIMAL,
                overall_climate_score=85.0,
                observed_mean_temp_c=26.0,
                crop_optimal_temp_range="15 - 25 °C",
                observed_rainfall_mm=1200.0,
                crop_water_need_mm_range="350 - 500 mm",
                agronomic_caveats=[],
            ),
            CropClimateSuitability(
                crop_id="lentil",
                crop_name="Lentil (Masoor)",
                thermal_compatibility=ThermalCompatibility.OPTIMAL,
                water_compatibility=WaterCompatibility.OPTIMAL,
                overall_climate_score=88.0,
                observed_mean_temp_c=26.0,
                crop_optimal_temp_range="15 - 22 °C",
                observed_rainfall_mm=1200.0,
                crop_water_need_mm_range="200 - 300 mm",
                agronomic_caveats=[],
            ),
            CropClimateSuitability(
                crop_id="mustard",
                crop_name="Indian Mustard (Sarson / Rai)",
                thermal_compatibility=ThermalCompatibility.OPTIMAL,
                water_compatibility=WaterCompatibility.OPTIMAL,
                overall_climate_score=87.0,
                observed_mean_temp_c=26.0,
                crop_optimal_temp_range="15 - 22 °C",
                observed_rainfall_mm=1200.0,
                crop_water_need_mm_range="240 - 350 mm",
                agronomic_caveats=[],
            ),
            CropClimateSuitability(
                crop_id="chickpea",
                crop_name="Chickpea (Bengal Gram / Chana)",
                thermal_compatibility=ThermalCompatibility.OPTIMAL,
                water_compatibility=WaterCompatibility.OPTIMAL,
                overall_climate_score=86.0,
                observed_mean_temp_c=26.0,
                crop_optimal_temp_range="18 - 26 °C",
                observed_rainfall_mm=1200.0,
                crop_water_need_mm_range="200 - 350 mm",
                agronomic_caveats=[],
            ),
            CropClimateSuitability(
                crop_id="green_gram",
                crop_name="Green Gram (Mung Bean / Moong)",
                thermal_compatibility=ThermalCompatibility.OPTIMAL,
                water_compatibility=WaterCompatibility.OPTIMAL,
                overall_climate_score=89.0,
                observed_mean_temp_c=26.0,
                crop_optimal_temp_range="25 - 35 °C",
                observed_rainfall_mm=1200.0,
                crop_water_need_mm_range="200 - 300 mm",
                agronomic_caveats=[],
            ),
            CropClimateSuitability(
                crop_id="maize",
                crop_name="Maize (Corn)",
                thermal_compatibility=ThermalCompatibility.OPTIMAL,
                water_compatibility=WaterCompatibility.OPTIMAL,
                overall_climate_score=84.0,
                observed_mean_temp_c=26.0,
                crop_optimal_temp_range="20 - 30 °C",
                observed_rainfall_mm=1200.0,
                crop_water_need_mm_range="450 - 650 mm",
                agronomic_caveats=[],
            ),
        ],
        scientific_provenance="Test",
    )


@pytest.fixture
def mock_farm():
    """Create a mock farm profile."""
    from app.schemas.farm import FarmResponse

    return FarmResponse(
        id="test-farm-id",
        name="Test Farm",
        latitude=22.5726,
        longitude=88.3639,
        total_area_hectares=10.0,
        soil_type=SoilType.CLAY_LOAM,
        soil_ph=6.5,
        organic_matter_pct=2.5,
        primary_irrigation=IrrigationType.CANAL,
        current_crop="Rice",
        crop_history=[],
        created_at=date.today(),
        updated_at=date.today(),
        owner_id="test-user-123",
    )


# -------------------------------------------------------------------------
# POST /api/rotations Tests
# -------------------------------------------------------------------------

def test_generate_rotation_success(valid_rotation_request, mock_climate_report):
    """Test successful rotation generation from coordinates."""
    with patch("app.api.routes.rotations.rotation_engine.generate_recommendation",
               new_callable=AsyncMock) as mock_gen:
        # Create a minimal valid strategy for primary_strategy (required field)
        from app.schemas.rotation import RotationStrategy, StrategyType, EvidenceLevel, EvidenceReport
        from app.schemas.rotation import FallowStep, FallowReason

        empty_strategy = RotationStrategy(
            strategy_type=StrategyType.COMPOSITE,
            name="Composite Multi-Factor",
            description="Test",
            evidence_level=EvidenceLevel.HEURISTIC,
            sequence=[FallowStep(step_type="fallow", slot="y1_aman", reason=FallowReason.NO_VALID_CROP)],
            total_years=2,
            planted_count=0,
            fallow_count=6,
            thermal_suitability_score=0.0,
            water_suitability_score=0.0,
            family_diversification_score=0.0,
            nitrogen_sequence_score=0.0,
            root_depth_score=0.0,
            irrigation_feasibility_score=0.0,
            composite_score=0.0,
            evidence_report=EvidenceReport(
                counts={r: {"verified": 0, "heuristic": 0, "insufficient_data": 0} for r in [
                    "thermal_suitability", "water_suitability", "botanical_family_diversification",
                    "nitrogen_role_sequence", "root_depth_alternation", "irrigation_feasibility"
                ]},
                verified_coverage_pct=0.0,
            ),
        )

        mock_gen.return_value = RotationRecommendation(
            farm_id=None,
            latitude=22.5726,
            longitude=88.3639,
            analysis_date=date.today(),
            climate_summary={},
            strategies=[],
            primary_strategy=empty_strategy,
            generated_at="2026-11-03T12:00:00Z",
        )

        response = client.post("/api/rotations", json=valid_rotation_request)

    assert response.status_code == 200
    data = response.json()
    assert data["latitude"] == 22.5726
    assert data["longitude"] == 88.3639


def test_generate_rotation_invalid_latitude():
    """Test invalid latitude rejected."""
    request = {
        "latitude": 95.0,  # Invalid
        "longitude": 88.3639,
        "max_cycle_years": 2,
    }
    response = client.post("/api/rotations", json=request)
    assert response.status_code == 422


def test_generate_rotation_invalid_longitude():
    """Test invalid longitude rejected."""
    request = {
        "latitude": 22.5726,
        "longitude": 200.0,  # Invalid
        "max_cycle_years": 2,
    }
    response = client.post("/api/rotations", json=request)
    assert response.status_code == 422


def test_generate_rotation_invalid_max_cycle_years():
    """Test invalid max_cycle_years rejected."""
    request = {
        "latitude": 22.5726,
        "longitude": 88.3639,
        "max_cycle_years": 1,  # Too low
    }
    response = client.post("/api/rotations", json=request)
    assert response.status_code == 422


def test_generate_rotation_invalid_climate_years(valid_rotation_request):
    """Test invalid climate years rejected."""
    request = {**valid_rotation_request, "climate_start_year": 1980}  # Too early
    response = client.post("/api/rotations", json=request)
    assert response.status_code == 422

    request = {**valid_rotation_request, "climate_end_year": 2030}  # Future
    response = client.post("/api/rotations", json=request)
    assert response.status_code == 422

    request = {**valid_rotation_request, "climate_start_year": 2020, "climate_end_year": 2019}  # Inverted
    response = client.post("/api/rotations", json=request)
    assert response.status_code == 422


def test_generate_rotation_invalid_excluded_crop(valid_rotation_request):
    """Test invalid excluded crop rejected."""
    request = {**valid_rotation_request, "exclude_crops": ["nonexistent_crop"]}
    response = client.post("/api/rotations", json=request)
    assert response.status_code == 422
    assert "not found in catalog" in response.json()["detail"]


def test_generate_rotation_invalid_previous_crop(valid_rotation_request):
    """Test invalid previous crop rejected."""
    request = {**valid_rotation_request, "previous_crops": ["nonexistent_crop"]}
    response = client.post("/api/rotations", json=request)
    assert response.status_code == 422
    assert "not found in catalog" in response.json()["detail"]


def test_generate_rotation_engine_error(valid_rotation_request):
    """Test engine error returns 502."""
    with patch("app.api.routes.rotations.rotation_engine.generate_recommendation",
               new_callable=AsyncMock) as mock_gen:
        mock_gen.side_effect = Exception("Upstream failure")

        response = client.post("/api/rotations", json=valid_rotation_request)

    assert response.status_code == 502
    assert "Upstream service error" in response.json()["detail"]


def test_generate_rotation_value_error(valid_rotation_request):
    """Test engine ValueError returns 422."""
    with patch("app.api.routes.rotations.rotation_engine.generate_recommendation",
               new_callable=AsyncMock) as mock_gen:
        mock_gen.side_effect = ValueError("Invalid request: no valid sequences")

        response = client.post("/api/rotations", json=valid_rotation_request)

    assert response.status_code == 422
    assert "no valid sequences" in response.json()["detail"]


# -------------------------------------------------------------------------
# POST /api/farms/{farm_id}/rotations Tests
# -------------------------------------------------------------------------

def test_generate_farm_rotation_success(auth_client: TestClient, mock_farm, mock_climate_report):
    """Test successful rotation generation from farm profile."""
    farm_id = mock_farm.id

    # Create a minimal valid strategy for primary_strategy (required field)
    from app.schemas.rotation import RotationStrategy, StrategyType, EvidenceLevel, EvidenceReport
    from app.schemas.rotation import FallowStep, FallowReason

    empty_strategy = RotationStrategy(
        strategy_type=StrategyType.COMPOSITE,
        name="Composite Multi-Factor",
        description="Test",
        evidence_level=EvidenceLevel.HEURISTIC,
        sequence=[FallowStep(step_type="fallow", slot="y1_aman", reason=FallowReason.NO_VALID_CROP)],
        total_years=2,
        planted_count=0,
        fallow_count=6,
        thermal_suitability_score=0.0,
        water_suitability_score=0.0,
        family_diversification_score=0.0,
        nitrogen_sequence_score=0.0,
        root_depth_score=0.0,
        irrigation_feasibility_score=0.0,
        composite_score=0.0,
        evidence_report=EvidenceReport(
            counts={r: {"verified": 0, "heuristic": 0, "insufficient_data": 0} for r in [
                "thermal_suitability", "water_suitability", "botanical_family_diversification",
                "nitrogen_role_sequence", "root_depth_alternation", "irrigation_feasibility"
            ]},
            verified_coverage_pct=0.0,
        ),
    )

    with patch("app.api.routes.rotations.farm_service.get_farm_by_id") as mock_get_farm:
        mock_get_farm.return_value = mock_farm

        # Patch the service module directly since import is local in the endpoint
        with patch("app.services.climate_analyzer.climate_analyzer_service.generate_report",
                   new_callable=AsyncMock) as mock_climate:
            mock_climate.return_value = mock_climate_report

            with patch("app.api.routes.rotations.rotation_engine.generate_recommendation_from_farm") as mock_gen:
                mock_gen.return_value = RotationRecommendation(
                    farm_id=farm_id,
                    latitude=mock_farm.latitude,
                    longitude=mock_farm.longitude,
                    analysis_date=date.today(),
                    climate_summary={},
                    strategies=[],
                    primary_strategy=empty_strategy,
                    generated_at="2026-11-03T12:00:00Z",
                )

                request = {
                    "farm_id": farm_id,
                    "max_cycle_years": 2,
                    "exclude_crops": [],
                }
                response = auth_client.post(f"/api/farms/{farm_id}/rotations", json=request)

    assert response.status_code == 200
    data = response.json()
    assert data["farm_id"] == farm_id
    assert data["latitude"] == mock_farm.latitude


def test_generate_farm_rotation_farm_not_found(auth_client: TestClient):
    """Test farm not found returns 404."""
    farm_id = "00000000-0000-0000-0000-000000000000"

    with patch("app.api.routes.rotations.farm_service.get_farm_by_id") as mock_get_farm:
        mock_get_farm.return_value = None

        request = {"farm_id": farm_id, "max_cycle_years": 2}
        response = auth_client.post(f"/api/farms/{farm_id}/rotations", json=request)

    assert response.status_code == 404
    assert "not found" in response.json()["detail"]


def test_generate_farm_rotation_mismatched_farm_id(auth_client: TestClient, mock_farm):
    """Test mismatched farm_id returns 422."""
    farm_id = mock_farm.id

    with patch("app.api.routes.rotations.farm_service.get_farm_by_id") as mock_get_farm:
        mock_get_farm.return_value = mock_farm

        request = {
            "farm_id": "different-farm-id",
            "max_cycle_years": 2,
        }
        response = auth_client.post(f"/api/farms/{farm_id}/rotations", json=request)

    assert response.status_code == 422
    assert "must match path parameter" in response.json()["detail"]


def test_generate_farm_rotation_invalid_climate_years(auth_client: TestClient, mock_farm):
    """Test invalid climate years for farm rotation."""
    farm_id = mock_farm.id

    with patch("app.api.routes.rotations.farm_service.get_farm_by_id") as mock_get_farm:
        mock_get_farm.return_value = mock_farm

        request = {
            "farm_id": farm_id,
            "max_cycle_years": 2,
            "climate_start_year": 1980,
        }
        response = auth_client.post(f"/api/farms/{farm_id}/rotations", json=request)

    assert response.status_code == 422


# -------------------------------------------------------------------------
# GET /api/rotations/catalog Tests
# -------------------------------------------------------------------------

def test_get_rotation_catalog_success():
    """Test rotation catalog endpoint returns expected structure."""
    response = client.get("/api/rotations/catalog")

    assert response.status_code == 200
    data = response.json()

    # Check all expected keys
    assert "strategy_templates" in data
    assert "verified_season_map" in data
    assert "unresolved_season_map" in data
    assert "boro_occupied_slots" in data
    assert "boro_irrigation_feasibility" in data
    assert "rule_weights" in data
    assert "thermal_score_map" in data
    assert "water_score_map" in data
    assert "scientific_disclaimer" in data
    assert "engine_version" in data

    # Check strategy templates
    strategies = data["strategy_templates"]
    assert len(strategies) == 4
    assert "nitrogen_sequence" in strategies
    assert "water_aligned" in strategies
    assert "family_diversification" in strategies
    assert "composite" in strategies

    for strategy in strategies.values():
        assert "name" in strategy
        assert "description" in strategy
        assert "evidence_level" in strategy

    # Check verified season map
    assert "rice" in data["verified_season_map"]
    assert "aman" in data["verified_season_map"]["rice"]
    assert "boro" in data["verified_season_map"]["rice"]
    assert "aus" in data["verified_season_map"]["rice"]

    # Check unresolved season map
    assert "green_gram" in data["unresolved_season_map"]
    assert "aman" in data["unresolved_season_map"]["green_gram"]
    assert "maize" in data["unresolved_season_map"]
    assert "aman" in data["unresolved_season_map"]["maize"]

    # Check Boro irrigation feasibility
    assert data["boro_irrigation_feasibility"]["canal"] == "supported"
    assert data["boro_irrigation_feasibility"]["rainfed"] == "not_supported"
    assert data["boro_irrigation_feasibility"]["drip"] == "requires_confirmation"

    # Check Boro occupied slots
    assert "y1_rabi" in data["boro_occupied_slots"]
    assert "y1_rabi" in data["boro_occupied_slots"]["y1_rabi"]
    assert "y1_summer" in data["boro_occupied_slots"]["y1_rabi"]


# -------------------------------------------------------------------------
# Schema Validation Tests
# -------------------------------------------------------------------------

def test_rotation_response_schema_compliance(valid_rotation_request, mock_climate_report):
    """Test rotation response conforms to RotationRecommendation schema."""
    with patch("app.api.routes.rotations.rotation_engine.generate_recommendation",
               new_callable=AsyncMock) as mock_gen:
        from app.schemas.rotation import (RotationStrategy, EvidenceReport, PlantedStep,
                                          StrategyType, EvidenceLevel, BotanicalFamily,
                                          NitrogenRole, WaterDemandClass,
                                          ThermalCompatibility, WaterCompatibility,
                                          IrrigationFeasibility, NormalizedSeason, SeasonSlot)
        from app.schemas.crop import RootingDepthClass

        # Create a valid strategy to use as primary_strategy
        primary_strategy = RotationStrategy(
            strategy_type=StrategyType.COMPOSITE,
            name="Composite Multi-Factor",
            description="Test",
            evidence_level=EvidenceLevel.HEURISTIC,
            sequence=[
                PlantedStep(
                    step_type="planted",
                    slot=SeasonSlot.Y1_AMAN,
                    crop_id="rice",
                    crop_name="Rice (Paddy)",
                    normalized_season=NormalizedSeason.AMAN,
                    duration_typical_days=125,
                    botanical_family=BotanicalFamily.POACEAE,
                    nitrogen_role=NitrogenRole.HEAVY_FEEDER,
                    root_depth_class=RootingDepthClass.SHALLOW,
                    water_demand_class=WaterDemandClass.VERY_HIGH,
                    thermal_compatibility=ThermalCompatibility.OPTIMAL,
                    water_compatibility=WaterCompatibility.OPTIMAL,
                    irrigation_feasibility=IrrigationFeasibility.SUPPORTED,
                )
            ],
            total_years=2,
            planted_count=1,
            fallow_count=5,
            thermal_suitability_score=90.0,
            water_suitability_score=90.0,
            family_diversification_score=75.0,
            nitrogen_sequence_score=75.0,
            root_depth_score=75.0,
            irrigation_feasibility_score=100.0,
            composite_score=84.0,
            evidence_report=EvidenceReport(
                counts={r: {"verified": 0, "heuristic": 0, "insufficient_data": 0} for r in [
                    "thermal_suitability", "water_suitability", "botanical_family_diversification",
                    "nitrogen_role_sequence", "root_depth_alternation", "irrigation_feasibility"
                ]},
                verified_coverage_pct=0.0,
            ),
        )

        mock_gen.return_value = RotationRecommendation(
            farm_id=None,
            latitude=22.5726,
            longitude=88.3639,
            analysis_date=date.today(),
            climate_summary={"period_days": 365},
            strategies=[primary_strategy],
            primary_strategy=primary_strategy,
            generated_at="2026-11-03T12:00:00Z",
        )

        response = client.post("/api/rotations", json=valid_rotation_request)

    assert response.status_code == 200
    data = response.json()

    # Verify required fields
    assert "farm_id" in data
    assert "latitude" in data
    assert "longitude" in data
    assert "analysis_date" in data
    assert "climate_summary" in data
    assert "strategies" in data
    assert "primary_strategy" in data
    assert "generated_at" in data
    assert "engine_version" in data
    assert "scientific_disclaimer" in data


def test_catalog_response_schema_compliance():
    """Test catalog response has all required fields with correct types."""
    response = client.get("/api/rotations/catalog")

    assert response.status_code == 200
    data = response.json()

    # Type checks
    assert isinstance(data["strategy_templates"], dict)
    assert isinstance(data["verified_season_map"], dict)
    assert isinstance(data["unresolved_season_map"], dict)
    assert isinstance(data["boro_occupied_slots"], dict)
    assert isinstance(data["boro_irrigation_feasibility"], dict)
    assert isinstance(data["rule_weights"], dict)
    assert isinstance(data["thermal_score_map"], dict)
    assert isinstance(data["water_score_map"], dict)
    assert isinstance(data["scientific_disclaimer"], str)
    assert isinstance(data["engine_version"], str)

    # All strategy templates have required fields
    for template in data["strategy_templates"].values():
        assert isinstance(template["name"], str)
        assert isinstance(template["description"], str)
        assert template["evidence_level"] in ["verified", "heuristic", "insufficient_data"]# Farm-specific rotation authorization tests


def test_generate_farm_rotation_cross_user_returns_404(auth_client: TestClient, admin_client: TestClient, mock_climate_report):
    """User A cannot generate rotation for User B's farm (cross-user 404)."""
    # Admin creates a real farm in the database
    farm_payload = {
        "name": "Admin Rotation Farm",
        "latitude": 22.5726,
        "longitude": 88.3639,
        "total_area_hectares": 10.0,
        "soil_type": "clay_loam",
        "primary_irrigation": "canal",
        "current_crop": "Rice",
    }
    farm_resp = admin_client.post("/api/farms", json=farm_payload)
    assert farm_resp.status_code == 201
    farm_id = farm_resp.json()["id"]

    with patch("app.services.climate_analyzer.climate_analyzer_service.generate_report",
               new_callable=AsyncMock) as mock_climate:
        mock_climate.return_value = mock_climate_report

        # Create a minimal valid strategy for primary_strategy
        from app.schemas.rotation import RotationStrategy, StrategyType, EvidenceLevel, EvidenceReport
        from app.schemas.rotation import FallowStep, FallowReason

        empty_strategy = RotationStrategy(
            strategy_type=StrategyType.COMPOSITE,
            name="Composite Multi-Factor",
            description="Test",
            evidence_level=EvidenceLevel.HEURISTIC,
            sequence=[FallowStep(step_type="fallow", slot="y1_aman", reason=FallowReason.NO_VALID_CROP)],
            total_years=2,
            planted_count=0,
            fallow_count=6,
            thermal_suitability_score=0.0,
            water_suitability_score=0.0,
            family_diversification_score=0.0,
            nitrogen_sequence_score=0.0,
            root_depth_score=0.0,
            irrigation_feasibility_score=0.0,
            composite_score=0.0,
            evidence_report=EvidenceReport(
                counts={r: {"verified": 0, "heuristic": 0, "insufficient_data": 0} for r in [
                    "thermal_suitability", "water_suitability", "botanical_family_diversification",
                    "nitrogen_role_sequence", "root_depth_alternation", "irrigation_feasibility"
                ]},
                verified_coverage_pct=0.0,
            ),
        )

        with patch("app.api.routes.rotations.rotation_engine.generate_recommendation_from_farm") as mock_gen:
            mock_gen.return_value = RotationRecommendation(
                farm_id=farm_id,
                latitude=22.5726,
                longitude=88.3639,
                analysis_date=date.today(),
                climate_summary={},
                strategies=[],
                primary_strategy=empty_strategy,
                generated_at="2026-11-03T12:00:00Z",
            )

            request = {
                "farm_id": farm_id,
                "max_cycle_years": 2,
                "exclude_crops": [],
            }
            # User A tries to generate rotation for Admin's farm
            response = auth_client.post(f"/api/farms/{farm_id}/rotations", json=request)

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_generate_farm_rotation_legacy_user_returns_404(auth_client: TestClient, mock_climate_report):
    """Normal user receives 404 when generating rotation for legacy farm (NULL owner_id)."""
    from app.models.farm import Farm
    from tests.conftest import TestingSessionLocal

    db = TestingSessionLocal()
    try:
        legacy_farm = Farm(
            id="legacy-farm-rotation-001",
            name="Legacy Rotation Farm",
            latitude=22.5726,
            longitude=88.3639,
            total_area_hectares=10.0,
            soil_type="clay_loam",
            primary_irrigation="canal",
            current_crop="Rice",
            owner_id=None,
        )
        db.add(legacy_farm)
        db.commit()
        db.refresh(legacy_farm)
        legacy_farm_id = legacy_farm.id
    finally:
        db.close()

    with patch("app.services.climate_analyzer.climate_analyzer_service.generate_report",
               new_callable=AsyncMock) as mock_climate:
        mock_climate.return_value = mock_climate_report

        from app.schemas.rotation import RotationStrategy, StrategyType, EvidenceLevel, EvidenceReport
        from app.schemas.rotation import FallowStep, FallowReason

        empty_strategy = RotationStrategy(
            strategy_type=StrategyType.COMPOSITE,
            name="Composite Multi-Factor",
            description="Test",
            evidence_level=EvidenceLevel.HEURISTIC,
            sequence=[FallowStep(step_type="fallow", slot="y1_aman", reason=FallowReason.NO_VALID_CROP)],
            total_years=2,
            planted_count=0,
            fallow_count=6,
            thermal_suitability_score=0.0,
            water_suitability_score=0.0,
            family_diversification_score=0.0,
            nitrogen_sequence_score=0.0,
            root_depth_score=0.0,
            irrigation_feasibility_score=0.0,
            composite_score=0.0,
            evidence_report=EvidenceReport(
                counts={r: {"verified": 0, "heuristic": 0, "insufficient_data": 0} for r in [
                    "thermal_suitability", "water_suitability", "botanical_family_diversification",
                    "nitrogen_role_sequence", "root_depth_alternation", "irrigation_feasibility"
                ]},
                verified_coverage_pct=0.0,
            ),
        )

        with patch("app.api.routes.rotations.rotation_engine.generate_recommendation_from_farm") as mock_gen:
            mock_gen.return_value = RotationRecommendation(
                farm_id=legacy_farm_id,
                latitude=22.5726,
                longitude=88.3639,
                analysis_date=date.today(),
                climate_summary={},
                strategies=[],
                primary_strategy=empty_strategy,
                generated_at="2026-11-03T12:00:00Z",
            )

            request = {
                "farm_id": legacy_farm_id,
                "max_cycle_years": 2,
                "exclude_crops": [],
            }
            response = auth_client.post(f"/api/farms/{legacy_farm_id}/rotations", json=request)

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_admin_can_access_user_rotation(auth_client: TestClient, admin_client: TestClient, mock_climate_report):
    """Admin can generate rotation for another user's farm."""
    # User creates a farm
    farm_payload = {
        "name": "User Rotation Farm",
        "latitude": 22.5726,
        "longitude": 88.3639,
        "total_area_hectares": 10.0,
        "soil_type": "clay_loam",
        "primary_irrigation": "canal",
        "current_crop": "Rice",
    }
    farm_resp = auth_client.post("/api/farms", json=farm_payload)
    assert farm_resp.status_code == 201
    farm_id = farm_resp.json()["id"]

    with patch("app.services.climate_analyzer.climate_analyzer_service.generate_report",
               new_callable=AsyncMock) as mock_climate:
        mock_climate.return_value = mock_climate_report

        from app.schemas.rotation import RotationStrategy, StrategyType, EvidenceLevel, EvidenceReport
        from app.schemas.rotation import FallowStep, FallowReason

        empty_strategy = RotationStrategy(
            strategy_type=StrategyType.COMPOSITE,
            name="Composite Multi-Factor",
            description="Test",
            evidence_level=EvidenceLevel.HEURISTIC,
            sequence=[FallowStep(step_type="fallow", slot="y1_aman", reason=FallowReason.NO_VALID_CROP)],
            total_years=2,
            planted_count=0,
            fallow_count=6,
            thermal_suitability_score=0.0,
            water_suitability_score=0.0,
            family_diversification_score=0.0,
            nitrogen_sequence_score=0.0,
            root_depth_score=0.0,
            irrigation_feasibility_score=0.0,
            composite_score=0.0,
            evidence_report=EvidenceReport(
                counts={r: {"verified": 0, "heuristic": 0, "insufficient_data": 0} for r in [
                    "thermal_suitability", "water_suitability", "botanical_family_diversification",
                    "nitrogen_role_sequence", "root_depth_alternation", "irrigation_feasibility"
                ]},
                verified_coverage_pct=0.0,
            ),
        )

        with patch("app.api.routes.rotations.rotation_engine.generate_recommendation_from_farm") as mock_gen:
            mock_gen.return_value = RotationRecommendation(
                farm_id=farm_id,
                latitude=22.5726,
                longitude=88.3639,
                analysis_date=date.today(),
                climate_summary={},
                strategies=[],
                primary_strategy=empty_strategy,
                generated_at="2026-11-03T12:00:00Z",
            )

            request = {
                "farm_id": farm_id,
                "max_cycle_years": 2,
                "exclude_crops": [],
            }
            # Admin generates rotation for User's farm
            response = admin_client.post(f"/api/farms/{farm_id}/rotations", json=request)

    assert response.status_code == 200
    data = response.json()
    assert data["farm_id"] == farm_id
    assert data["latitude"] == 22.5726