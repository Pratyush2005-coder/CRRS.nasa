"""Pydantic schemas for Crop Rotation Recommendation Engine (Phase 3A).

All models follow the finalized Phase 3 design:
- Frozen models for immutability
- Discriminated union for PlantedStep | FallowStep
- Evidence levels: VERIFIED | HEURISTIC | INSUFFICIENT_DATA
- Transparent evidence reporting (no arbitrary confidence thresholds)
- Boro rice duration-based slot occupancy
- Verified-only season mappings; unresolved tracked separately
- Irrigation feasibility per IrrigationType with evidence
"""

from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Set, Union
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.crop import (
    BotanicalFamily,
    NitrogenRole,
    RootingDepthClass,
    SoilType,
    WaterDemandClass,
)
from app.schemas.farm import IrrigationType
from app.schemas.climate_analyzer import (
    ThermalCompatibility,
    WaterCompatibility,
)


# =============================================================================
# ENUMS
# =============================================================================

class NormalizedSeason(str, Enum):
    """Normalized planning seasons derived from catalog growing_seasons."""
    AMAN = "aman"           # Jun–Oct (Kharif / Monsoon)
    BORO = "boro"           # Nov–Apr/May (Winter / Irrigated) — spans RABI + SUMMER slots
    AUS = "aus"             # Mar–Jun (Pre-Kharif / Summer)
    RABI = "rabi"           # Nov–Feb (Winter)
    SUMMER = "summer"       # Mar–May (Pre-Kharif / Zaid)


class SeasonSlot(str, Enum):
    """Discrete planning slots — 3 per year, up to 5 years (15 slots max)."""
    # Year 1
    Y1_AMAN = "y1_aman"
    Y1_RABI = "y1_rabi"
    Y1_SUMMER = "y1_summer"
    # Year 2
    Y2_AMAN = "y2_aman"
    Y2_RABI = "y2_rabi"
    Y2_SUMMER = "y2_summer"
    # Year 3
    Y3_AMAN = "y3_aman"
    Y3_RABI = "y3_rabi"
    Y3_SUMMER = "y3_summer"
    # Year 4
    Y4_AMAN = "y4_aman"
    Y4_RABI = "y4_rabi"
    Y4_SUMMER = "y4_summer"
    # Year 5
    Y5_AMAN = "y5_aman"
    Y5_RABI = "y5_rabi"
    Y5_SUMMER = "y5_summer"


class EvidenceLevel(str, Enum):
    """Evidence quality for each rule evaluation and data source."""
    VERIFIED = "verified"               # Directly from catalog, climate analyzer, or farm data
    HEURISTIC = "heuristic"             # Agronomic principle, no field validation
    INSUFFICIENT_DATA = "insufficient_data"  # No data available to evaluate


class RotationRule(str, Enum):
    """Rotation rules evaluated for each crop transition."""
    THERMAL_SUITABILITY = "thermal_suitability"
    WATER_SUITABILITY = "water_suitability"
    BOTANICAL_FAMILY_DIVERSIFICATION = "botanical_family_diversification"
    NITROGEN_ROLE_SEQUENCE = "nitrogen_role_sequence"
    ROOT_DEPTH_ALTERNATION = "root_depth_alternation"
    IRRIGATION_FEASIBILITY = "irrigation_feasibility"


class StrategyType(str, Enum):
    """Rotation strategy archetypes."""
    NITROGEN_SEQUENCE = "nitrogen_sequence"
    WATER_ALIGNED = "water_aligned"
    FAMILY_DIVERSIFICATION = "family_diversification"
    COMPOSITE = "composite"


class IrrigationFeasibility(str, Enum):
    """Boro irrigation feasibility per IrrigationType."""
    SUPPORTED = "supported"                   # Verified evidence (CANAL)
    REQUIRES_CONFIRMATION = "requires_confirmation"  # Unresolved (DRIP, SPRINKLER, FLOOD_FURROW)
    NOT_SUPPORTED = "not_supported"           # Contradicts crop requirement (RAINFED, NONE)


class FallowReason(str, Enum):
    """Explicit reasons for fallow slots."""
    NO_VALID_CROP = "no_valid_crop"
    EXCLUDED_BY_USER = "excluded_by_user"
    CLIMATE_BELOW_THRESHOLD = "climate_below_threshold"
    IRRIGATION_UNAVAILABLE = "irrigation_unavailable"


# =============================================================================
# CORE MODELS
# =============================================================================

class RuleEvidence(BaseModel):
    """Evidence metadata for a single rule evaluation."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    level: EvidenceLevel
    source: str  # e.g., "crop_catalog", "climate_analyzer", "farm_profile", "agronomic_heuristic"
    citation: Optional[str] = None  # e.g., "ICAR NRRI", "FAO-56", "BCKV Package of Practices"


class RuleEvaluation(BaseModel):
    """Result of evaluating one rotation rule for a crop transition."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    rule: RotationRule
    passed: bool
    score: float = Field(..., ge=0.0, le=100.0, description="Rule score 0-100")
    rationale: str = Field(..., description="Human-readable explanation")
    evidence: RuleEvidence
    caveats: List[str] = Field(default_factory=list)
    data_gaps: List[str] = Field(default_factory=list)


class CropSeasonFit(BaseModel):
    """Pre-computed climate suitability for a crop in one normalized season."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    crop_id: str
    crop_name: str
    normalized_season: NormalizedSeason
    # From climate analyzer response (categorical only)
    thermal_compatibility: ThermalCompatibility
    water_compatibility: WaterCompatibility
    overall_climate_score: Optional[float] = Field(
        None, ge=0.0, le=100.0, description="Composite score from climate analyzer"
    )
    agronomic_caveats: List[str] = Field(default_factory=list)
    # Derived
    irrigation_required: bool = Field(
        False, description="True for Boro rice, False otherwise"
    )
    evidence_level: EvidenceLevel = EvidenceLevel.VERIFIED


# =============================================================================
# SEQUENCE STEPS — Discriminated Union
# =============================================================================

class PlantedStep(BaseModel):
    """A crop actually planted in a season slot."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    step_type: Literal["planted"] = "planted"
    slot: SeasonSlot
    crop_id: str
    crop_name: str
    normalized_season: NormalizedSeason
    duration_typical_days: int = Field(..., ge=30, le=365)

    # Verified agronomic attributes from crop catalog
    botanical_family: BotanicalFamily
    nitrogen_role: NitrogenRole
    root_depth_class: RootingDepthClass
    water_demand_class: WaterDemandClass

    # Climate suitability for this crop in this season
    thermal_compatibility: ThermalCompatibility
    water_compatibility: WaterCompatibility
    overall_climate_score: Optional[float] = Field(None, ge=0.0, le=100.0)
    agronomic_caveats: List[str] = Field(default_factory=list)

    # Irrigation feasibility for this crop in this slot
    irrigation_feasibility: IrrigationFeasibility

    # Rule evaluations for transition from previous step
    rule_evaluations: List[RuleEvaluation] = Field(default_factory=list)


class FallowStep(BaseModel):
    """Explicit fallow slot — NO agronomic attributes."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    step_type: Literal["fallow"] = "fallow"
    slot: SeasonSlot
    reason: FallowReason

    # NO botanical_family, nitrogen_role, root_depth_class, water_demand_class
    # NO climate suitability, NO rule_evaluations


# Discriminated union for sequence items
SequenceStep = Union[PlantedStep, FallowStep]


def is_planted(step: SequenceStep) -> bool:
    """Type guard for PlantedStep."""
    return step.step_type == "planted"


def is_fallow(step: SequenceStep) -> bool:
    """Type guard for FallowStep."""
    return step.step_type == "fallow"


def get_planted_steps(sequence: List[SequenceStep]) -> List[PlantedStep]:
    """Extract only planted steps from a mixed sequence."""
    return [s for s in sequence if is_planted(s)]


# =============================================================================
# EVIDENCE REPORT
# =============================================================================

class EvidenceReport(BaseModel):
    """Transparent evidence accounting — NO arbitrary confidence label."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    # Counts per rule per evidence level
    counts: Dict[str, Dict[EvidenceLevel, int]] = Field(
        ..., description="rule_name -> {evidence_level -> count}"
    )

    # Coverage: percentage of rule evaluations with VERIFIED evidence
    verified_coverage_pct: float = Field(
        ..., ge=0.0, le=100.0, description="Percentage of evaluations with VERIFIED evidence"
    )

    # Explicit limitations and data gaps
    limitations: List[str] = Field(default_factory=list)
    data_gaps: List[str] = Field(default_factory=list)


# =============================================================================
# ROTATION STRATEGY
# =============================================================================

class RotationStrategy(BaseModel):
    """Complete rotation strategy (multi-year sequence)."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    strategy_type: StrategyType
    name: str
    description: str
    evidence_level: EvidenceLevel  # Overall strategy evidence level

    sequence: List[SequenceStep]  # Mixed PlantedStep + FallowStep
    total_years: int = Field(..., ge=1, le=5)
    planted_count: int = Field(..., ge=0)
    fallow_count: int = Field(..., ge=0)

    # Sub-scores (0-100 each)
    thermal_suitability_score: float = Field(..., ge=0.0, le=100.0)
    water_suitability_score: float = Field(..., ge=0.0, le=100.0)
    family_diversification_score: float = Field(..., ge=0.0, le=100.0)
    nitrogen_sequence_score: float = Field(..., ge=0.0, le=100.0)
    root_depth_score: float = Field(..., ge=0.0, le=100.0)
    irrigation_feasibility_score: float = Field(..., ge=0.0, le=100.0)

    # Composite score (weights sum to 1.0, NO economic, NO pest/disease)
    composite_score: float = Field(..., ge=0.0, le=100.0)

    # Transparent evidence report (replaces confidence)
    evidence_report: EvidenceReport


# =============================================================================
# TOP-LEVEL RESPONSE
# =============================================================================

class RotationRecommendation(BaseModel):
    """Top-level rotation recommendation response."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    farm_id: Optional[str] = None
    latitude: float = Field(..., ge=-90.0, le=90.0)
    longitude: float = Field(..., ge=-180.0, le=180.0)
    analysis_date: date

    # Climate context summary (extracted from ClimateIntelligenceReport)
    climate_summary: Dict[str, Any]

    # Strategies (typically 2-3 distinct)
    strategies: List[RotationStrategy]
    primary_strategy: RotationStrategy

    # Metadata
    generated_at: str
    engine_version: str = "1.0.0"
    scientific_disclaimer: str = (
        "Rotation recommendations are based on verified crop catalog data, "
        "NASA climate intelligence, and established agronomic heuristics. "
        "Botanical family diversification, nitrogen role sequencing, and root "
        "depth alternation are heuristic principles; they do not guarantee "
        "pest, disease, or yield outcomes. Boro rice climate evaluation uses "
        "single-year proxy data. Multi-year climate normals, planting calendars, "
        "and relay planting (Utera) are not modeled. Consult local agricultural "
        "extension for field-specific decisions."
    )


# =============================================================================
# REQUEST MODELS
# =============================================================================

class RotationRequest(BaseModel):
    """Input for coordinate-based rotation generation."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    latitude: float = Field(..., ge=-90.0, le=90.0)
    longitude: float = Field(..., ge=-180.0, le=180.0)
    farm_id: Optional[str] = None

    # Optional farm context overrides (used if farm_id not provided)
    soil_type: Optional[SoilType] = None
    soil_ph: Optional[float] = Field(None, ge=3.0, le=10.0)
    organic_matter_pct: Optional[float] = Field(None, ge=0.0, le=100.0)
    irrigation_type: Optional[IrrigationType] = None
    previous_crops: List[str] = Field(
        default_factory=list,
        description="Crop IDs from farm history (most recent first)"
    )

    max_cycle_years: int = Field(3, ge=2, le=5)
    exclude_crops: List[str] = Field(default_factory=list)
    preferred_start_slot: Optional[SeasonSlot] = None

    # Climate period (defaults to last 3 full years if not specified)
    climate_start_year: Optional[int] = None
    climate_end_year: Optional[int] = None


class FarmRotationRequest(BaseModel):
    """Input using existing farm profile."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    farm_id: str
    max_cycle_years: int = Field(3, ge=2, le=5)
    exclude_crops: List[str] = Field(default_factory=list)
    climate_start_year: Optional[int] = None
    climate_end_year: Optional[int] = None


# =============================================================================
# INTERNAL LOOKUP TYPES (not exposed via API)
# =============================================================================

class _CropOccupancy(BaseModel):
    """Internal: which slots a crop occupies based on duration and planting season."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    crop_id: str
    planting_slot: SeasonSlot
    occupied_slots: Set[SeasonSlot]
    harvest_slot: SeasonSlot
    evidence_level: EvidenceLevel


# Verified-only season map (used by engine for automatic recommendations)
VERIFIED_SEASON_MAP: Dict[str, Set[NormalizedSeason]] = {
    "rice": {NormalizedSeason.AMAN, NormalizedSeason.BORO, NormalizedSeason.AUS},
    "wheat": {NormalizedSeason.RABI},
    "lentil": {NormalizedSeason.RABI},
    "mustard": {NormalizedSeason.RABI},
    "chickpea": {NormalizedSeason.RABI},
    "green_gram": {NormalizedSeason.SUMMER},   # AMAN excluded — unresolved
    "maize": {NormalizedSeason.RABI},          # AMAN excluded — unresolved
}

# Unresolved season mappings (tracked for transparency)
UNRESOLVED_SEASON_MAP: Dict[str, Set[NormalizedSeason]] = {
    "green_gram": {NormalizedSeason.AMAN},  # "Kharif" generic, no duration evidence
    "maize": {NormalizedSeason.AMAN},       # "Kharif" generic, no duration evidence
}

# Boro rice irrigation feasibility per IrrigationType
BORO_IRRIGATION_FEASIBILITY: Dict[IrrigationType, IrrigationFeasibility] = {
    IrrigationType.CANAL: IrrigationFeasibility.SUPPORTED,
    IrrigationType.DRIP: IrrigationFeasibility.REQUIRES_CONFIRMATION,
    IrrigationType.SPRINKLER: IrrigationFeasibility.REQUIRES_CONFIRMATION,
    IrrigationType.FLOOD_FURROW: IrrigationFeasibility.REQUIRES_CONFIRMATION,
    IrrigationType.RAINFED: IrrigationFeasibility.NOT_SUPPORTED,
    IrrigationType.NONE: IrrigationFeasibility.NOT_SUPPORTED,
}

# Slot calendar month ranges (for overlap logic only — approximate)
SLOT_MONTH_RANGES: Dict[SeasonSlot, tuple[int, int]] = {
    SeasonSlot.Y1_AMAN: (6, 10),
    SeasonSlot.Y1_RABI: (11, 2),
    SeasonSlot.Y1_SUMMER: (3, 5),
    SeasonSlot.Y2_AMAN: (6, 10),
    SeasonSlot.Y2_RABI: (11, 2),
    SeasonSlot.Y2_SUMMER: (3, 5),
    SeasonSlot.Y3_AMAN: (6, 10),
    SeasonSlot.Y3_RABI: (11, 2),
    SeasonSlot.Y3_SUMMER: (3, 5),
    SeasonSlot.Y4_AMAN: (6, 10),
    SeasonSlot.Y4_RABI: (11, 2),
    SeasonSlot.Y4_SUMMER: (3, 5),
    SeasonSlot.Y5_AMAN: (6, 10),
    SeasonSlot.Y5_RABI: (11, 2),
    SeasonSlot.Y5_SUMMER: (3, 5),
}

# Boro occupancy: planted in RABI slot, spans RABI + SUMMER
BORO_OCCUPIED_SLOTS: Dict[SeasonSlot, Set[SeasonSlot]] = {
    SeasonSlot.Y1_RABI: {SeasonSlot.Y1_RABI, SeasonSlot.Y1_SUMMER},
    SeasonSlot.Y2_RABI: {SeasonSlot.Y2_RABI, SeasonSlot.Y2_SUMMER},
    SeasonSlot.Y3_RABI: {SeasonSlot.Y3_RABI, SeasonSlot.Y3_SUMMER},
    SeasonSlot.Y4_RABI: {SeasonSlot.Y4_RABI, SeasonSlot.Y4_SUMMER},
    SeasonSlot.Y5_RABI: {SeasonSlot.Y5_RABI, SeasonSlot.Y5_SUMMER},
}

# Strategy templates with explicit heuristic labels
STRATEGY_TEMPLATES: Dict[StrategyType, Dict[str, Any]] = {
    StrategyType.NITROGEN_SEQUENCE: {
        "name": "Nitrogen Role Sequence",
        "description": (
            "Prefers legume (nitrogen_fixer) → cereal (heavy_feeder) transitions "
            "based on qualitative nitrogen roles. Heuristic; no quantitative N balance."
        ),
        "evidence_level": EvidenceLevel.HEURISTIC,
    },
    StrategyType.WATER_ALIGNED: {
        "name": "Water Demand Alignment",
        "description": (
            "Prefers crops whose water demand class matches local rainfall + "
            "irrigation capacity. Uses verified climate analyzer water_compatibility."
        ),
        "evidence_level": EvidenceLevel.VERIFIED,
    },
    StrategyType.FAMILY_DIVERSIFICATION: {
        "name": "Botanical Family Diversification",
        "description": (
            "Alternates botanical families (Poaceae, Fabaceae, Brassicaceae) to "
            "reduce host-specific pathogen buildup. Heuristic; does not guarantee "
            "pest/disease prevention. No verified regional pathogen data."
        ),
        "evidence_level": EvidenceLevel.HEURISTIC,
    },
    StrategyType.COMPOSITE: {
        "name": "Composite Multi-Factor",
        "description": (
            "Equal-weight combination of all rule scores. Mix of verified and "
            "heuristic evidence."
        ),
        "evidence_level": EvidenceLevel.HEURISTIC,
    },
}

# Rule weights (sum = 1.0)
RULE_WEIGHTS: Dict[RotationRule, float] = {
    RotationRule.THERMAL_SUITABILITY: 0.25,
    RotationRule.WATER_SUITABILITY: 0.25,
    RotationRule.BOTANICAL_FAMILY_DIVERSIFICATION: 0.20,
    RotationRule.NITROGEN_ROLE_SEQUENCE: 0.15,
    RotationRule.ROOT_DEPTH_ALTERNATION: 0.10,
    RotationRule.IRRIGATION_FEASIBILITY: 0.05,
}

# Categorical → numeric score mapping (explicit heuristic)
THERMAL_SCORE_MAP: Dict[ThermalCompatibility, float] = {
    ThermalCompatibility.OPTIMAL: 100.0,
    ThermalCompatibility.SUITABLE: 75.0,
    ThermalCompatibility.MARGINAL: 50.0,
    ThermalCompatibility.UNSUITABLE: 25.0,
}

WATER_SCORE_MAP: Dict[WaterCompatibility, float] = {
    WaterCompatibility.OPTIMAL: 100.0,
    WaterCompatibility.DEFICIT_RISK: 60.0,
    WaterCompatibility.SURPLUS_RISK: 55.0,
    WaterCompatibility.IRRIGATION_DEPENDENT: 40.0,
}