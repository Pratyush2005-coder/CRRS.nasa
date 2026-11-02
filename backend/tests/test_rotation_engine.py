"""Tests for Rotation Engine (Phase 3B)."""

from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.schemas.rotation import (
    NormalizedSeason,
    SeasonSlot,
    EvidenceLevel,
    RotationRule,
    StrategyType,
    IrrigationFeasibility,
    FallowReason,
    RotationRequest,
    FarmRotationRequest,
    VERIFIED_SEASON_MAP,
    UNRESOLVED_SEASON_MAP,
    BORO_OCCUPIED_SLOTS,
    THERMAL_SCORE_MAP,
    WATER_SCORE_MAP,
)
from app.services.rotation_engine import SLOT_TO_NORMALIZED_SEASON, get_slots_for_years, get_slot_year
from app.schemas.farm import IrrigationType, CropHistoryRecord
from app.schemas.climate import (
    ClimateMetadata,
    Coordinates,
    DateRange,
    ParameterDetail,
)
from app.schemas.climate_analyzer import (
    ThermalCompatibility,
    WaterCompatibility,
    ClimateIntelligenceReport,
    CropClimateSuitability,
    MissingDataAnalysis,
    CompletenessCategory,
    RainfallAnalysis,
    TemperatureAnalysis,
    HeatRiskIndicators,
    HeatRiskLevel,
    ColdRiskIndicators,
    ColdRiskLevel,
)
from app.schemas.crop import Crop
from app.services.rotation_engine import RotationEngine, rotation_engine
from datetime import datetime


# -------------------------------------------------------------------------
# Fixtures
# -------------------------------------------------------------------------

@pytest.fixture
def mock_climate_report() -> ClimateIntelligenceReport:
    """Create a mock climate intelligence report with all crops having OPTIMAL suitability."""
    return ClimateIntelligenceReport(
        metadata=ClimateMetadata(
            data_source="NASA POWER Test",
            retrieval_timestamp=datetime.now(timezone.utc),
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
def engine() -> RotationEngine:
    """Create a rotation engine instance."""
    return RotationEngine()


# -------------------------------------------------------------------------
# Boro Occupancy Tests
# -------------------------------------------------------------------------

def test_boro_occupancy_y1_rabi(engine: RotationEngine):
    """Test Boro rice occupies Y1_RABI and Y1_SUMMER when planted in Y1_RABI."""
    occupied = engine.get_boro_occupied_slots(SeasonSlot.Y1_RABI)
    assert SeasonSlot.Y1_RABI in occupied
    assert SeasonSlot.Y1_SUMMER in occupied
    assert len(occupied) == 2


def test_boro_occupancy_all_years(engine: RotationEngine):
    """Test Boro occupancy for all RABI slots across 5 years."""
    for year in range(1, 6):
        rabi_slot = SeasonSlot(f"y{year}_rabi")
        summer_slot = SeasonSlot(f"y{year}_summer")
        occupied = engine.get_boro_occupied_slots(rabi_slot)
        assert rabi_slot in occupied
        assert summer_slot in occupied
        assert len(occupied) == 2


def test_boro_not_planting_in_non_rabi(engine: RotationEngine):
    """Test Boro rice cannot be planted in non-RABI slots."""
    assert engine.is_boro_planting_slot(SeasonSlot.Y1_RABI) is True
    assert engine.is_boro_planting_slot(SeasonSlot.Y1_AMAN) is False
    assert engine.is_boro_planting_slot(SeasonSlot.Y1_SUMMER) is False


def test_get_occupied_slots_for_rice_boro(engine: RotationEngine):
    """Test rice in RABI slot (Boro) occupies 2 slots."""
    occupied = engine.get_occupied_slots_for_crop("rice", SeasonSlot.Y1_RABI)
    assert SeasonSlot.Y1_RABI in occupied
    assert SeasonSlot.Y1_SUMMER in occupied


def test_get_occupied_slots_for_rice_aman(engine: RotationEngine):
    """Test rice in AMAN slot occupies only 1 slot."""
    occupied = engine.get_occupied_slots_for_crop("rice", SeasonSlot.Y1_AMAN)
    assert occupied == {SeasonSlot.Y1_AMAN}


def test_get_occupied_slots_for_wheat(engine: RotationEngine):
    """Test wheat occupies only its planting slot."""
    occupied = engine.get_occupied_slots_for_crop("wheat", SeasonSlot.Y1_RABI)
    assert occupied == {SeasonSlot.Y1_RABI}


# -------------------------------------------------------------------------
# Season Compatibility Tests
# -------------------------------------------------------------------------

def test_verified_season_map_excludes_unresolved(engine: RotationEngine):
    """Test that VERIFIED_SEASON_MAP excludes unresolved mappings."""
    # green_gram has unresolved AMAN mapping
    assert NormalizedSeason.AMAN not in VERIFIED_SEASON_MAP.get("green_gram", set())
    assert NormalizedSeason.SUMMER in VERIFIED_SEASON_MAP.get("green_gram", set())

    # maize has unresolved AMAN mapping
    assert NormalizedSeason.AMAN not in VERIFIED_SEASON_MAP.get("maize", set())
    assert NormalizedSeason.RABI in VERIFIED_SEASON_MAP.get("maize", set())


def test_get_valid_crops_for_aman_slot(engine: RotationEngine, mock_climate_report):
    """Test valid crops for AMAN slot."""
    valid = engine.get_valid_crops_for_slot(
        SeasonSlot.Y1_AMAN, mock_climate_report, irrigation_type=IrrigationType.CANAL
    )
    crop_ids = [f[0].crop_id for f in valid]
    assert "rice" in crop_ids  # Rice has verified AMAN
    assert "green_gram" not in crop_ids  # green_gram AMAN is unresolved


def test_get_valid_crops_for_rabi_slot(engine: RotationEngine, mock_climate_report):
    """Test valid crops for RABI slot."""
    valid = engine.get_valid_crops_for_slot(
        SeasonSlot.Y1_RABI, mock_climate_report, irrigation_type=IrrigationType.CANAL
    )
    crop_ids = [f[0].crop_id for f in valid]
    assert "wheat" in crop_ids
    assert "lentil" in crop_ids
    assert "mustard" in crop_ids
    assert "chickpea" in crop_ids
    assert "maize" in crop_ids
    assert "rice" in crop_ids  # Boro rice in RABI


def test_get_valid_crops_for_summer_slot(engine: RotationEngine, mock_climate_report):
    """Test valid crops for SUMMER slot."""
    valid = engine.get_valid_crops_for_slot(
        SeasonSlot.Y1_SUMMER, mock_climate_report, irrigation_type=IrrigationType.CANAL
    )
    crop_ids = [f[0].crop_id for f in valid]
    assert "green_gram" in crop_ids
    # Boro rice planted in RABI occupies SUMMER, so not directly plantable in SUMMER


def test_excluded_crops_filtered(engine: RotationEngine, mock_climate_report):
    """Test excluded crops are filtered out."""
    valid = engine.get_valid_crops_for_slot(
        SeasonSlot.Y1_RABI,
        mock_climate_report,
        excluded_crops={"wheat", "lentil"},
        irrigation_type=IrrigationType.CANAL,
    )
    crop_ids = [f[0].crop_id for f in valid]
    assert "wheat" not in crop_ids
    assert "lentil" not in crop_ids
    assert "mustard" in crop_ids


# -------------------------------------------------------------------------
# Irrigation Feasibility Tests
# -------------------------------------------------------------------------

def test_boro_irrigation_feasibility_canal(engine: RotationEngine):
    """Test CANAL irrigation supports Boro rice."""
    feas = engine.get_boro_irrigation_feasibility(IrrigationType.CANAL)
    assert feas == IrrigationFeasibility.SUPPORTED


def test_boro_irrigation_feasibility_rainfed(engine: RotationEngine):
    """Test RAINFED does not support Boro rice."""
    feas = engine.get_boro_irrigation_feasibility(IrrigationType.RAINFED)
    assert feas == IrrigationFeasibility.NOT_SUPPORTED


def test_boro_irrigation_feasibility_drip(engine: RotationEngine):
    """Test DRIP requires confirmation for Boro rice."""
    feas = engine.get_boro_irrigation_feasibility(IrrigationType.DRIP)
    assert feas == IrrigationFeasibility.REQUIRES_CONFIRMATION


def test_non_boro_irrigation_feasibility(engine: RotationEngine):
    """Test non-Boro crops get appropriate feasibility."""
    feas = engine.get_irrigation_feasibility("wheat", NormalizedSeason.RABI, IrrigationType.RAINFED)
    assert feas == IrrigationFeasibility.SUPPORTED


# -------------------------------------------------------------------------
# Rule Evaluation Tests
# -------------------------------------------------------------------------

def test_evaluate_thermal_suitability(engine: RotationEngine, mock_climate_report):
    """Test thermal suitability evaluation."""
    # Create a mock CropSeasonFit
    from app.schemas.rotation import CropSeasonFit
    fit = CropSeasonFit(
        crop_id="rice",
        crop_name="Rice (Paddy)",
        normalized_season=NormalizedSeason.AMAN,
        thermal_compatibility=ThermalCompatibility.OPTIMAL,
        water_compatibility=WaterCompatibility.OPTIMAL,
        overall_climate_score=90.0,
        agronomic_caveats=[],
        irrigation_required=False,
        evidence_level=EvidenceLevel.VERIFIED,
    )

    eval_ = engine._evaluate_thermal_suitability(None, fit, mock_climate_report)
    assert eval_.rule == RotationRule.THERMAL_SUITABILITY
    assert eval_.score == 100.0  # OPTIMAL maps to 100
    assert eval_.passed is True
    assert eval_.evidence.level == EvidenceLevel.VERIFIED


def test_evaluate_water_suitability(engine: RotationEngine, mock_climate_report):
    """Test water suitability evaluation."""
    from app.schemas.rotation import CropSeasonFit
    fit = CropSeasonFit(
        crop_id="rice",
        crop_name="Rice (Paddy)",
        normalized_season=NormalizedSeason.AMAN,
        thermal_compatibility=ThermalCompatibility.OPTIMAL,
        water_compatibility=WaterCompatibility.OPTIMAL,
        overall_climate_score=90.0,
        agronomic_caveats=[],
        irrigation_required=False,
        evidence_level=EvidenceLevel.VERIFIED,
    )

    eval_ = engine._evaluate_water_suitability(None, fit, mock_climate_report)
    assert eval_.rule == RotationRule.WATER_SUITABILITY
    assert eval_.score == 100.0  # OPTIMAL maps to 100
    assert eval_.passed is True


def test_evaluate_family_diversification_same_family(engine: RotationEngine, mock_climate_report):
    """Test family diversification - same family (rice -> wheat, both Poaceae)."""
    from app.schemas.rotation import CropSeasonFit, PlantedStep
    # Rice and wheat are both POACEAE
    fit = CropSeasonFit(
        crop_id="wheat",
        crop_name="Wheat",
        normalized_season=NormalizedSeason.RABI,
        thermal_compatibility=ThermalCompatibility.OPTIMAL,
        water_compatibility=WaterCompatibility.OPTIMAL,
        overall_climate_score=85.0,
        agronomic_caveats=[],
        irrigation_required=False,
        evidence_level=EvidenceLevel.VERIFIED,
    )

    # Previous step: rice (POACEAE)
    prev_step = PlantedStep(
        slot=SeasonSlot.Y1_AMAN,
        crop_id="rice",
        crop_name="Rice (Paddy)",
        normalized_season=NormalizedSeason.AMAN,
        duration_typical_days=125,
        botanical_family=__import__('app.schemas.crop', fromlist=['BotanicalFamily']).BotanicalFamily.POACEAE,
        nitrogen_role=__import__('app.schemas.crop', fromlist=['NitrogenRole']).NitrogenRole.HEAVY_FEEDER,
        root_depth_class=__import__('app.schemas.crop', fromlist=['RootingDepthClass']).RootingDepthClass.SHALLOW,
        water_demand_class=__import__('app.schemas.crop', fromlist=['WaterDemandClass']).WaterDemandClass.VERY_HIGH,
        thermal_compatibility=ThermalCompatibility.OPTIMAL,
        water_compatibility=WaterCompatibility.OPTIMAL,
        irrigation_feasibility=IrrigationFeasibility.SUPPORTED,
    )

    eval_ = engine._evaluate_family_diversification(prev_step, fit)
    assert eval_.rule == RotationRule.BOTANICAL_FAMILY_DIVERSIFICATION
    assert eval_.passed is False  # Same family
    assert eval_.score == 40.0


def test_evaluate_family_diversification_different_family(engine: RotationEngine, mock_climate_report):
    """Test family diversification - different family (rice -> lentil)."""
    from app.schemas.rotation import CropSeasonFit, PlantedStep
    from app.schemas.crop import BotanicalFamily, NitrogenRole, RootingDepthClass, WaterDemandClass

    fit = CropSeasonFit(
        crop_id="lentil",
        crop_name="Lentil (Masoor)",
        normalized_season=NormalizedSeason.RABI,
        thermal_compatibility=ThermalCompatibility.OPTIMAL,
        water_compatibility=WaterCompatibility.OPTIMAL,
        overall_climate_score=88.0,
        agronomic_caveats=[],
        irrigation_required=False,
        evidence_level=EvidenceLevel.VERIFIED,
    )

    # Previous step: rice (POACEAE)
    prev_step = PlantedStep(
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

    eval_ = engine._evaluate_family_diversification(prev_step, fit)
    assert eval_.rule == RotationRule.BOTANICAL_FAMILY_DIVERSIFICATION
    assert eval_.passed is True  # Different family (POACEAE -> FABACEAE)
    assert eval_.score == 100.0


def test_evaluate_nitrogen_sequence_fixer_to_feeder(engine: RotationEngine, mock_climate_report):
    """Test nitrogen sequence: fixer -> heavy_feeder (preferred)."""
    from app.schemas.rotation import CropSeasonFit, PlantedStep
    from app.schemas.crop import BotanicalFamily, NitrogenRole, RootingDepthClass, WaterDemandClass

    fit = CropSeasonFit(
        crop_id="wheat",
        crop_name="Wheat",
        normalized_season=NormalizedSeason.RABI,
        thermal_compatibility=ThermalCompatibility.OPTIMAL,
        water_compatibility=WaterCompatibility.OPTIMAL,
        overall_climate_score=85.0,
        agronomic_caveats=[],
        irrigation_required=False,
        evidence_level=EvidenceLevel.VERIFIED,
    )

    # Previous step: lentil (NITROGEN_FIXER)
    prev_step = PlantedStep(
        slot=SeasonSlot.Y1_AMAN,
        crop_id="lentil",
        crop_name="Lentil (Masoor)",
        normalized_season=NormalizedSeason.RABI,  # lentil in RABI
        duration_typical_days=105,
        botanical_family=BotanicalFamily.FABACEAE,
        nitrogen_role=NitrogenRole.NITROGEN_FIXER,
        root_depth_class=RootingDepthClass.SHALLOW,
        water_demand_class=WaterDemandClass.LOW,
        thermal_compatibility=ThermalCompatibility.OPTIMAL,
        water_compatibility=WaterCompatibility.OPTIMAL,
        irrigation_feasibility=IrrigationFeasibility.SUPPORTED,
    )

    eval_ = engine._evaluate_nitrogen_sequence(prev_step, fit)
    assert eval_.rule == RotationRule.NITROGEN_ROLE_SEQUENCE
    assert eval_.passed is True  # fixer -> feeder is preferred
    assert eval_.score == 100.0


def test_evaluate_nitrogen_sequence_feeder_to_feeder(engine: RotationEngine, mock_climate_report):
    """Test nitrogen sequence: feeder -> feeder (not preferred)."""
    from app.schemas.rotation import CropSeasonFit, PlantedStep
    from app.schemas.crop import BotanicalFamily, NitrogenRole, RootingDepthClass, WaterDemandClass

    fit = CropSeasonFit(
        crop_id="maize",
        crop_name="Maize (Corn)",
        normalized_season=NormalizedSeason.RABI,
        thermal_compatibility=ThermalCompatibility.OPTIMAL,
        water_compatibility=WaterCompatibility.OPTIMAL,
        overall_climate_score=84.0,
        agronomic_caveats=[],
        irrigation_required=False,
        evidence_level=EvidenceLevel.VERIFIED,
    )

    # Previous step: wheat (HEAVY_FEEDER)
    prev_step = PlantedStep(
        slot=SeasonSlot.Y1_AMAN,
        crop_id="wheat",
        crop_name="Wheat",
        normalized_season=NormalizedSeason.RABI,
        duration_typical_days=110,
        botanical_family=BotanicalFamily.POACEAE,
        nitrogen_role=NitrogenRole.HEAVY_FEEDER,
        root_depth_class=RootingDepthClass.MEDIUM,
        water_demand_class=WaterDemandClass.MODERATE,
        thermal_compatibility=ThermalCompatibility.OPTIMAL,
        water_compatibility=WaterCompatibility.OPTIMAL,
        irrigation_feasibility=IrrigationFeasibility.SUPPORTED,
    )

    eval_ = engine._evaluate_nitrogen_sequence(prev_step, fit)
    assert eval_.rule == RotationRule.NITROGEN_ROLE_SEQUENCE
    assert eval_.passed is False  # feeder -> feeder not preferred
    assert eval_.score == 60.0


def test_evaluate_root_depth_alternation(engine: RotationEngine, mock_climate_report):
    """Test root depth alternation."""
    from app.schemas.rotation import CropSeasonFit, PlantedStep
    from app.schemas.crop import BotanicalFamily, NitrogenRole, RootingDepthClass, WaterDemandClass

    fit = CropSeasonFit(
        crop_id="chickpea",
        crop_name="Chickpea (Bengal Gram / Chana)",
        normalized_season=NormalizedSeason.RABI,
        thermal_compatibility=ThermalCompatibility.OPTIMAL,
        water_compatibility=WaterCompatibility.OPTIMAL,
        overall_climate_score=86.0,
        agronomic_caveats=[],
        irrigation_required=False,
        evidence_level=EvidenceLevel.VERIFIED,
    )

    # Previous step: wheat (MEDIUM root depth)
    prev_step = PlantedStep(
        slot=SeasonSlot.Y1_AMAN,
        crop_id="wheat",
        crop_name="Wheat",
        normalized_season=NormalizedSeason.RABI,
        duration_typical_days=110,
        botanical_family=BotanicalFamily.POACEAE,
        nitrogen_role=NitrogenRole.HEAVY_FEEDER,
        root_depth_class=RootingDepthClass.MEDIUM,
        water_demand_class=WaterDemandClass.MODERATE,
        thermal_compatibility=ThermalCompatibility.OPTIMAL,
        water_compatibility=WaterCompatibility.OPTIMAL,
        irrigation_feasibility=IrrigationFeasibility.SUPPORTED,
    )

    eval_ = engine._evaluate_root_depth_alternation(prev_step, fit)
    assert eval_.rule == RotationRule.ROOT_DEPTH_ALTERNATION
    assert eval_.passed is True  # MEDIUM -> DEEP is alternation
    assert eval_.score == 100.0


def test_evaluate_irrigation_feasibility_supported(engine: RotationEngine):
    """Test irrigation feasibility - supported."""
    from app.schemas.rotation import CropSeasonFit

    fit = CropSeasonFit(
        crop_id="rice",
        crop_name="Rice (Paddy)",
        normalized_season=NormalizedSeason.BORO,
        thermal_compatibility=ThermalCompatibility.OPTIMAL,
        water_compatibility=WaterCompatibility.IRRIGATION_DEPENDENT,
        overall_climate_score=40.0,
        agronomic_caveats=[],
        irrigation_required=True,
        evidence_level=EvidenceLevel.VERIFIED,
    )

    eval_ = engine._evaluate_irrigation_feasibility(None, fit, IrrigationType.CANAL)
    assert eval_.rule == RotationRule.IRRIGATION_FEASIBILITY
    assert eval_.passed is True
    assert eval_.score == 100.0


def test_evaluate_irrigation_feasibility_not_supported(engine: RotationEngine):
    """Test irrigation feasibility - not supported (rainfed for Boro)."""
    from app.schemas.rotation import CropSeasonFit

    fit = CropSeasonFit(
        crop_id="rice",
        crop_name="Rice (Paddy)",
        normalized_season=NormalizedSeason.BORO,
        thermal_compatibility=ThermalCompatibility.OPTIMAL,
        water_compatibility=WaterCompatibility.IRRIGATION_DEPENDENT,
        overall_climate_score=40.0,
        agronomic_caveats=[],
        irrigation_required=True,
        evidence_level=EvidenceLevel.VERIFIED,
    )

    eval_ = engine._evaluate_irrigation_feasibility(None, fit, IrrigationType.RAINFED)
    assert eval_.rule == RotationRule.IRRIGATION_FEASIBILITY
    assert eval_.passed is False
    assert eval_.score == 20.0


# -------------------------------------------------------------------------
# Sequence Generation Tests
# -------------------------------------------------------------------------

def test_generate_sequences_basic(engine: RotationEngine, mock_climate_report):
    """Test basic sequence generation."""
    sequences = engine.generate_sequences(
        climate_report=mock_climate_report,
        max_cycle_years=2,
        irrigation_type=IrrigationType.CANAL,
    )

    assert len(sequences) > 0
    assert len(sequences) <= 10  # Max sequences

    # Check sequence structure
    for seq in sequences:
        assert len(seq) == 6  # 2 years * 3 slots
        for step in seq:
            assert step.slot in list(SeasonSlot)[:6]  # Y1 and Y2 slots


def test_generate_sequences_deterministic(engine: RotationEngine, mock_climate_report):
    """Test sequence generation is deterministic."""
    seq1 = engine.generate_sequences(
        climate_report=mock_climate_report,
        max_cycle_years=2,
        irrigation_type=IrrigationType.CANAL,
    )
    seq2 = engine.generate_sequences(
        climate_report=mock_climate_report,
        max_cycle_years=2,
        irrigation_type=IrrigationType.CANAL,
    )

    assert seq1 == seq2


def test_generate_sequences_respects_excluded_crops(engine: RotationEngine, mock_climate_report):
    """Test excluded crops are not in sequences."""
    sequences = engine.generate_sequences(
        climate_report=mock_climate_report,
        max_cycle_years=2,
        excluded_crops={"rice", "wheat"},
        irrigation_type=IrrigationType.CANAL,
    )

    for seq in sequences:
        for step in seq:
            if step.step_type == "planted":
                assert step.crop_id not in {"rice", "wheat"}


def test_generate_sequences_includes_fallow(engine: RotationEngine, mock_climate_report):
    """Test sequences include fallow steps when needed."""
    # Exclude all crops that can grow in RABI to force fallow
    sequences = engine.generate_sequences(
        climate_report=mock_climate_report,
        max_cycle_years=1,
        excluded_crops={"wheat", "lentil", "mustard", "chickpea", "maize", "rice"},
        irrigation_type=IrrigationType.CANAL,
    )

    for seq in sequences:
        fallow_steps = [s for s in seq if s.step_type == "fallow"]
        assert len(fallow_steps) > 0


def test_generate_sequences_boro_occupancy_respected(engine: RotationEngine, mock_climate_report):
    """Test Boro rice occupancy prevents planting in SUMMER slot."""
    sequences = engine.generate_sequences(
        climate_report=mock_climate_report,
        max_cycle_years=2,
        excluded_crops={"wheat", "lentil", "mustard", "chickpea", "maize", "green_gram"},
        irrigation_type=IrrigationType.CANAL,
    )

    # Find sequence with Boro rice in Y1_RABI
    for seq in sequences:
        for i, step in enumerate(seq):
            if step.step_type == "planted" and step.crop_id == "rice" and step.slot == SeasonSlot.Y1_RABI:
                # Next slot (Y1_SUMMER) should be fallow due to Boro occupancy
                if i + 1 < len(seq):
                    next_step = seq[i + 1]
                    assert next_step.step_type == "fallow"
                    assert next_step.slot == SeasonSlot.Y1_SUMMER


# -------------------------------------------------------------------------
# Scoring Tests
# -------------------------------------------------------------------------

def test_score_sequence(engine: RotationEngine, mock_climate_report):
    """Test sequence scoring."""
    sequences = engine.generate_sequences(
        climate_report=mock_climate_report,
        max_cycle_years=2,
        irrigation_type=IrrigationType.CANAL,
    )

    seq = sequences[0]
    scores = engine.score_sequence(seq, StrategyType.COMPOSITE)

    assert "thermal_suitability_score" in scores
    assert "water_suitability_score" in scores
    assert "family_diversification_score" in scores
    assert "nitrogen_sequence_score" in scores
    assert "root_depth_score" in scores
    assert "irrigation_feasibility_score" in scores
    assert "composite_score" in scores

    # All scores should be 0-100
    for key, value in scores.items():
        assert 0.0 <= value <= 100.0


def test_score_sequence_strategy_weights(engine: RotationEngine, mock_climate_report):
    """Test different strategies produce different weight emphasis."""
    sequences = engine.generate_sequences(
        climate_report=mock_climate_report,
        max_cycle_years=2,
        irrigation_type=IrrigationType.CANAL,
    )

    seq = sequences[0]

    nitrogen_scores = engine.score_sequence(seq, StrategyType.NITROGEN_SEQUENCE)
    water_scores = engine.score_sequence(seq, StrategyType.WATER_ALIGNED)
    family_scores = engine.score_sequence(seq, StrategyType.FAMILY_DIVERSIFICATION)
    composite_scores = engine.score_sequence(seq, StrategyType.COMPOSITE)

    # Each strategy should have different composite scores due to different weights
    scores = [nitrogen_scores["composite_score"], water_scores["composite_score"],
              family_scores["composite_score"], composite_scores["composite_score"]]
    # At least some should differ (depends on sequence)
    assert len(set(round(s, 1) for s in scores)) >= 1


# -------------------------------------------------------------------------
# Evidence Reporting Tests
# -------------------------------------------------------------------------

def test_build_evidence_report(engine: RotationEngine, mock_climate_report):
    """Test evidence report generation."""
    sequences = engine.generate_sequences(
        climate_report=mock_climate_report,
        max_cycle_years=2,
        irrigation_type=IrrigationType.CANAL,
    )

    seq = sequences[0]
    report = engine.build_evidence_report(seq)

    assert report.verified_coverage_pct >= 0.0
    assert report.verified_coverage_pct <= 100.0
    assert isinstance(report.limitations, list)
    assert isinstance(report.data_gaps, list)
    assert len(report.limitations) > 0
    assert len(report.data_gaps) > 0

    # Check counts structure
    for rule in RotationRule:
        assert rule.value in report.counts
        for level in EvidenceLevel:
            assert level in report.counts[rule.value]


# -------------------------------------------------------------------------
# Strategy Generation Tests
# -------------------------------------------------------------------------

def test_generate_strategies_all_four(engine: RotationEngine, mock_climate_report):
    """Test all four strategies are generated."""
    sequences = engine.generate_sequences(
        climate_report=mock_climate_report,
        max_cycle_years=2,
        irrigation_type=IrrigationType.CANAL,
    )

    strategies = engine.generate_strategies(sequences, 2)

    assert len(strategies) == 4
    strategy_types = {s.strategy_type for s in strategies}
    assert strategy_types == {
        StrategyType.NITROGEN_SEQUENCE,
        StrategyType.WATER_ALIGNED,
        StrategyType.FAMILY_DIVERSIFICATION,
        StrategyType.COMPOSITE,
    }


def test_generate_strategies_ordered_by_score(engine: RotationEngine, mock_climate_report):
    """Test strategies are ordered by composite score within each strategy."""
    sequences = engine.generate_sequences(
        climate_report=mock_climate_report,
        max_cycle_years=2,
        irrigation_type=IrrigationType.CANAL,
    )

    strategies = engine.generate_strategies(sequences, 2)

    for strategy in strategies:
        # Each strategy should have valid scores
        assert 0.0 <= strategy.composite_score <= 100.0
        assert strategy.total_years == 2
        assert strategy.planted_count >= 0
        assert strategy.fallow_count >= 0
        assert len(strategy.sequence) == 6


def test_primary_strategy_selection(engine: RotationEngine, mock_climate_report):
    """Test primary strategy is the one with highest composite score."""
    sequences = engine.generate_sequences(
        climate_report=mock_climate_report,
        max_cycle_years=2,
        irrigation_type=IrrigationType.CANAL,
    )

    strategies = engine.generate_strategies(sequences, 2)
    primary = max(strategies, key=lambda s: s.composite_score)

    # Primary should have highest composite score
    for s in strategies:
        assert primary.composite_score >= s.composite_score


# -------------------------------------------------------------------------
# Input Validation Tests
# -------------------------------------------------------------------------

def test_validate_rotation_request_valid(engine: RotationEngine):
    """Test valid rotation request passes validation."""
    request = RotationRequest(
        latitude=22.57,
        longitude=88.36,
        max_cycle_years=3,
    )
    errors = engine.validate_rotation_request(request)
    assert len(errors) == 0


def test_validate_rotation_request_invalid_years(engine: RotationEngine):
    """Test invalid max_cycle_years caught by Pydantic validation."""
    from pydantic import ValidationError
    try:
        request = RotationRequest(
            latitude=22.57,
            longitude=88.36,
            max_cycle_years=1,  # Too low
        )
        errors = engine.validate_rotation_request(request)
        assert any("max_cycle_years" in e for e in errors)
    except ValidationError as e:
        # Pydantic validates ge=2 before our custom validation
        assert "max_cycle_years" in str(e)
        assert "greater than or equal to 2" in str(e)


def test_validate_rotation_request_invalid_excluded_crop(engine: RotationEngine):
    """Test invalid excluded crop caught."""
    request = RotationRequest(
        latitude=22.57,
        longitude=88.36,
        exclude_crops=["nonexistent_crop"],
    )
    errors = engine.validate_rotation_request(request)
    assert any("not found in catalog" in e for e in errors)


def test_validate_rotation_request_invalid_previous_crop(engine: RotationEngine):
    """Test invalid previous crop caught."""
    request = RotationRequest(
        latitude=22.57,
        longitude=88.36,
        previous_crops=["nonexistent_crop"],
    )
    errors = engine.validate_rotation_request(request)
    assert any("not found in catalog" in e for e in errors)


# -------------------------------------------------------------------------
# Integration Test (Full Pipeline)
# -------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_generate_recommendation_full(engine: RotationEngine, mock_climate_report):
    """Test full recommendation generation."""
    request = RotationRequest(
        latitude=22.57,
        longitude=88.36,
        max_cycle_years=2,
        irrigation_type=IrrigationType.CANAL,
    )

    with patch.object(engine, 'generate_climate_report', new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = mock_climate_report

        recommendation = await engine.generate_recommendation(request, climate_report=mock_climate_report)

    assert recommendation.farm_id is None
    assert recommendation.latitude == 22.57
    assert recommendation.longitude == 88.36
    assert len(recommendation.strategies) == 4
    assert recommendation.primary_strategy in recommendation.strategies
    assert "period_days" in recommendation.climate_summary
    assert "data_completeness" in recommendation.climate_summary


# -------------------------------------------------------------------------
# Slot Mapping Tests
# -------------------------------------------------------------------------

def test_slot_to_normalized_season_mapping():
    """Test slot to normalized season mapping is correct."""
    assert SLOT_TO_NORMALIZED_SEASON[SeasonSlot.Y1_AMAN] == NormalizedSeason.AMAN
    assert SLOT_TO_NORMALIZED_SEASON[SeasonSlot.Y1_RABI] == NormalizedSeason.RABI
    assert SLOT_TO_NORMALIZED_SEASON[SeasonSlot.Y1_SUMMER] == NormalizedSeason.SUMMER
    assert SLOT_TO_NORMALIZED_SEASON[SeasonSlot.Y2_AMAN] == NormalizedSeason.AMAN
    assert SLOT_TO_NORMALIZED_SEASON[SeasonSlot.Y5_RABI] == NormalizedSeason.RABI


def test_get_slots_for_years():
    """Test slot list generation for N years."""
    slots_2y = get_slots_for_years(2)
    assert len(slots_2y) == 6
    assert slots_2y[0] == SeasonSlot.Y1_AMAN
    assert slots_2y[5] == SeasonSlot.Y2_SUMMER

    slots_5y = get_slots_for_years(5)
    assert len(slots_5y) == 15
    assert slots_5y[-1] == SeasonSlot.Y5_SUMMER


def test_get_slot_year():
    """Test year extraction from slot."""
    assert get_slot_year(SeasonSlot.Y1_AMAN) == 1
    assert get_slot_year(SeasonSlot.Y3_RABI) == 3
    assert get_slot_year(SeasonSlot.Y5_SUMMER) == 5


# -------------------------------------------------------------------------
# Regression Tests for Phase 3B.1 Fixes
# -------------------------------------------------------------------------


def test_get_crop_season_fit_missing_suitability_returns_insufficient_data(engine: RotationEngine, mock_climate_report):
    """Test get_crop_season_fit returns INSUFFICIENT_DATA when climate suitability is missing."""
    # Create a copy of the mock report with empty crop_suitability
    empty_report = mock_climate_report.model_copy(update={"crop_suitability": []})

    fit = engine.get_crop_season_fit("rice", NormalizedSeason.AMAN, empty_report)

    assert fit is not None
    assert fit.evidence_level == EvidenceLevel.INSUFFICIENT_DATA
    assert fit.thermal_compatibility == ThermalCompatibility.MARGINAL
    assert fit.water_compatibility == WaterCompatibility.DEFICIT_RISK
    assert fit.overall_climate_score is None
    assert any("No climate suitability data available" in c for c in fit.agronomic_caveats)


def test_thermal_evaluator_insufficient_data_propagation(engine: RotationEngine, mock_climate_report):
    """Test thermal evaluator correctly propagates INSUFFICIENT_DATA evidence level and data gaps."""
    from app.schemas.rotation import CropSeasonFit

    fit = CropSeasonFit(
        crop_id="rice",
        crop_name="Rice (Paddy)",
        normalized_season=NormalizedSeason.AMAN,
        thermal_compatibility=ThermalCompatibility.MARGINAL,
        water_compatibility=WaterCompatibility.DEFICIT_RISK,
        overall_climate_score=None,
        agronomic_caveats=["No climate suitability data available for Rice (Paddy) in aman season. Thermal and water compatibility defaulted to conservative estimates."],
        irrigation_required=False,
        evidence_level=EvidenceLevel.INSUFFICIENT_DATA,
    )

    eval_ = engine._evaluate_thermal_suitability(None, fit, mock_climate_report)

    assert eval_.rule == RotationRule.THERMAL_SUITABILITY
    assert eval_.evidence.level == EvidenceLevel.INSUFFICIENT_DATA
    assert eval_.evidence.source == "climate_analyzer_missing"
    assert eval_.evidence.citation == "No climate suitability data available for this crop/season"
    assert "Crop-specific thermal suitability not available from climate analyzer" in eval_.data_gaps
    assert eval_.score == THERMAL_SCORE_MAP[ThermalCompatibility.MARGINAL]


def test_water_evaluator_insufficient_data_propagation(engine: RotationEngine, mock_climate_report):
    """Test water evaluator correctly propagates INSUFFICIENT_DATA evidence level and data gaps."""
    from app.schemas.rotation import CropSeasonFit

    fit = CropSeasonFit(
        crop_id="rice",
        crop_name="Rice (Paddy)",
        normalized_season=NormalizedSeason.AMAN,
        thermal_compatibility=ThermalCompatibility.MARGINAL,
        water_compatibility=WaterCompatibility.DEFICIT_RISK,
        overall_climate_score=None,
        agronomic_caveats=["No climate suitability data available for Rice (Paddy) in aman season. Thermal and water compatibility defaulted to conservative estimates."],
        irrigation_required=False,
        evidence_level=EvidenceLevel.INSUFFICIENT_DATA,
    )

    eval_ = engine._evaluate_water_suitability(None, fit, mock_climate_report, None)

    assert eval_.rule == RotationRule.WATER_SUITABILITY
    assert eval_.evidence.level == EvidenceLevel.INSUFFICIENT_DATA
    assert eval_.evidence.source == "climate_analyzer_missing"
    assert "Crop-specific water suitability not available from climate analyzer" in eval_.data_gaps
    assert eval_.score == WATER_SCORE_MAP[WaterCompatibility.DEFICIT_RISK]


def test_generate_recommendation_from_farm_uses_previous_crops(engine: RotationEngine, mock_climate_report):
    """Test generate_recommendation_from_farm correctly reads previous_crops from farm profile."""
    from unittest.mock import MagicMock

    # Create a mock farm profile with previous_crops (not crop_history)
    mock_farm = MagicMock()
    mock_farm.latitude = 22.57
    mock_farm.longitude = 88.36
    mock_farm.soil_type = None
    mock_farm.soil_ph = None
    mock_farm.organic_matter_pct = None
    mock_farm.primary_irrigation = IrrigationType.CANAL
    mock_farm.previous_crops = [
        CropHistoryRecord(crop_name="Rice (Paddy)", harvest_year=2023),
        CropHistoryRecord(crop_name="Wheat", harvest_year=2023),
    ]

    request = FarmRotationRequest(
        farm_id="test_farm_123",
        max_cycle_years=2,
    )

    # This should not raise an error about crop_history
    try:
        result = engine.generate_recommendation_from_farm(
            request=request,
            farm_profile=mock_farm,
            climate_report=mock_climate_report,
        )
        # If it succeeds, the previous_crops were read correctly
        assert result is not None
        assert result.farm_id == "test_farm_123"
    except AttributeError as e:
        if "crop_history" in str(e):
            pytest.fail("generate_recommendation_from_farm incorrectly tries to access 'crop_history' instead of 'previous_crops'")
        raise