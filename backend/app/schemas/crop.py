"""Pydantic schemas for the Crop Knowledge Base."""

from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field

from app.schemas.farm import SoilType


class BotanicalFamily(str, Enum):
    """Botanical crop families."""

    POACEAE = "Poaceae"  # Gramineae (Cereals, Grasses)
    FABACEAE = "Fabaceae"  # Leguminosae (Pulses, Legumes)
    BRASSICACEAE = "Brassicaceae"  # Cruciferae (Mustards, Oilseeds)
    SOLANACEAE = "Solanaceae"  # Nightshades (Potato, Tomato)
    ASTERACEAE = "Asteraceae"  # Compositae (Sunflower, Safflower)
    PEDALIACEAE = "Pedaliaceae"  # Sesame
    MALVACEAE = "Malvaceae"  # Cotton, Okra


class NitrogenRole(str, Enum):
    """Agronomic nitrogen dynamic classification."""

    NITROGEN_FIXER = "nitrogen_fixer"  # Legumes fixing atmospheric N symbiotically
    HEAVY_FEEDER = "heavy_feeder"  # High N extractor (e.g., Rice, Wheat, Maize)
    MODERATE_FEEDER = "moderate_feeder"  # Moderate N demand (e.g., Mustard)
    LIGHT_FEEDER = "light_feeder"  # Low nutrient demand / restorative


class WaterDemandClass(str, Enum):
    """Crop water demand categories."""

    LOW = "low"  # < 350 mm
    MODERATE = "moderate"  # 350 - 600 mm
    HIGH = "high"  # 600 - 900 mm
    VERY_HIGH = "very_high"  # > 900 mm (e.g., lowland paddy rice)


class RootingDepthClass(str, Enum):
    """Effective root zone depth for soil moisture & structure interaction."""

    SHALLOW = "shallow"  # < 0.6 m (e.g., Lentil, Mustard)
    MEDIUM = "medium"  # 0.6 - 1.2 m (e.g., Wheat, Maize)
    DEEP = "deep"  # > 1.2 m (e.g., Chickpea taproot)


class ConfidenceLevel(str, Enum):
    """Verification confidence of the agronomic parameter set."""

    HIGH = "high"  # Directly corroborated by ICAR / BCKV / FAO peer-reviewed standards
    MEDIUM = "medium"  # Regional empirical estimates with minor extrapolation
    LOW = "low"  # Preliminary or unverified observation


class DurationRange(BaseModel):
    """Crop maturity duration in days from sowing to harvest."""

    min_days: int = Field(..., ge=30, le=365, description="Minimum days to maturity")
    max_days: int = Field(..., ge=30, le=365, description="Maximum days to maturity")
    typical_days: int = Field(..., ge=30, le=365, description="Typical/average days in pilot region")


class WaterRequirement(BaseModel):
    """Hydrological requirements based on FAO-56 and ICAR guidelines."""

    demand_class: WaterDemandClass = Field(..., description="Categorical water demand tier")
    min_mm: float = Field(..., ge=0.0, description="Minimum seasonal water requirement in mm")
    max_mm: float = Field(..., ge=0.0, description="Maximum seasonal water requirement in mm")
    critical_growth_stages: List[str] = Field(
        default_factory=list,
        description="Moisture-critical phenological growth stages where water deficit causes severe yield reduction",
    )


class SoilSuitability(BaseModel):
    """Pedological preferences and tolerance limits."""

    suitable_soil_types: List[SoilType] = Field(
        ...,
        description="Soil textural classes well-suited to this crop",
    )
    drainage_requirement: str = Field(
        ...,
        description="Drainage sensitivity (e.g., well-drained, waterlogging-tolerant)",
    )
    min_ph: float = Field(..., ge=3.0, le=10.0, description="Absolute minimum soil pH tolerated")
    max_ph: float = Field(..., ge=3.0, le=10.0, description="Absolute maximum soil pH tolerated")
    optimal_min_ph: float = Field(..., ge=3.0, le=10.0, description="Optimal minimum soil pH")
    optimal_max_ph: float = Field(..., ge=3.0, le=10.0, description="Optimal maximum soil pH")


class TemperatureRequirement(BaseModel):
    """Thermal thresholds for vegetative and reproductive stages."""

    min_temp_c: float = Field(..., description="Base lower physiological survival threshold in °C")
    max_temp_c: float = Field(..., description="Upper heat tolerance limit in °C")
    optimal_min_temp_c: float = Field(..., description="Optimal temperature lower bound in °C")
    optimal_max_temp_c: float = Field(..., description="Optimal temperature upper bound in °C")
    gdd_base_temp_c: Optional[float] = Field(
        None,
        description="Growing Degree Day (GDD) base threshold temperature (T_base) in °C where verified",
    )
    gdd_base_verified: bool = Field(
        False,
        description="True if GDD base temperature is verified in ICAR/FAO literature; False if estimated or unavailable",
    )


class NitrogenManagement(BaseModel):
    """Biological and agronomic nitrogen dynamics."""

    role: NitrogenRole = Field(..., description="Nitrogen extraction or fixation role")
    is_nitrogen_fixer: bool = Field(..., description="Whether crop fixes atmospheric nitrogen via nodulation")
    fixation_capacity_kg_ha: Optional[str] = Field(
        None,
        description="Estimated biological nitrogen fixation range (kg N/ha) where applicable",
    )
    residual_nitrogen_effect: str = Field(
        ...,
        description="Agronomic contribution or nutrient requirement for succeeding crop",
    )


class CropReference(BaseModel):
    """Credible institutional source attribution."""

    institution: str = Field(..., description="Research institution or governing body (e.g., ICAR, BCKV, FAO)")
    publication: str = Field(..., description="Title of bulletin, manual, or research report")
    details: Optional[str] = Field(None, description="Specific volume, chapter, or URL identifier")


class Crop(BaseModel):
    """Comprehensive Crop Knowledge Base entity."""

    crop_id: str = Field(..., description="Unique alphanumeric slug identifier (e.g., 'rice', 'wheat')")
    crop_name: str = Field(..., description="Common vernacular/English name")
    scientific_name: str = Field(..., description="Botanical binomial nomenclature")
    botanical_family: BotanicalFamily = Field(..., description="Botanical taxonomic family")
    pilot_region: str = Field("West Bengal, India", description="Agro-ecological calibration region")
    growing_seasons: List[str] = Field(
        ...,
        description="Applicable growing seasons in pilot region (e.g., Aman, Boro, Rabi, Pre-Kharif/Aus)",
    )
    duration: DurationRange
    rooting_depth_class: RootingDepthClass
    water_requirement: WaterRequirement
    soil_suitability: SoilSuitability
    temperature_requirement: TemperatureRequirement
    nitrogen_management: NitrogenManagement
    references: List[CropReference]
    confidence_level: ConfidenceLevel
    unverified_fields: List[str] = Field(
        default_factory=list,
        description="Explicit list of parameters that are estimated or pending localized field trial verification",
    )


class CropSummary(BaseModel):
    """Concise representation of a crop for catalog overview."""

    crop_id: str
    crop_name: str
    scientific_name: str
    botanical_family: BotanicalFamily
    growing_seasons: List[str]
    duration_typical_days: int
    water_demand_class: WaterDemandClass
    nitrogen_role: NitrogenRole
    rooting_depth_class: RootingDepthClass
    confidence_level: ConfidenceLevel


class CropCatalogResponse(BaseModel):
    """Response payload for GET /api/crops/catalog."""

    total: int = Field(..., description="Total count of catalog crops")
    pilot_region: str = Field(..., description="Calibrated pilot agro-ecological region")
    crops: List[Crop] = Field(..., description="Full crop knowledge entities")
    data_provenance_note: str = Field(..., description="Scientific attribution and transparency statement")
