"""API Pydantic Schemas."""

from app.schemas.health import HealthResponse
from app.schemas.climate import (
    ClimateResponse,
    ClimateMetadata,
    ClimateSummary,
    DailyClimateRecord,
)
from app.schemas.farm import (
    CropHistoryRecord,
    FarmBase,
    FarmCreate,
    FarmListResponse,
    FarmResponse,
    FarmUpdate,
    IrrigationType,
    SoilType,
)

from app.schemas.crop import (
    BotanicalFamily,
    ConfidenceLevel,
    Crop,
    CropCatalogResponse,
    CropReference,
    CropSummary,
    DurationRange,
    NitrogenManagement,
    NitrogenRole,
    RootingDepthClass,
    SoilSuitability,
    TemperatureRequirement,
    WaterDemandClass,
    WaterRequirement,
)

__all__ = [
    "HealthResponse",
    "ClimateResponse",
    "ClimateMetadata",
    "ClimateSummary",
    "DailyClimateRecord",
    "CropHistoryRecord",
    "FarmBase",
    "FarmCreate",
    "FarmListResponse",
    "FarmResponse",
    "FarmUpdate",
    "IrrigationType",
    "SoilType",
    "BotanicalFamily",
    "ConfidenceLevel",
    "Crop",
    "CropCatalogResponse",
    "CropReference",
    "CropSummary",
    "DurationRange",
    "NitrogenManagement",
    "NitrogenRole",
    "RootingDepthClass",
    "SoilSuitability",
    "TemperatureRequirement",
    "WaterDemandClass",
    "WaterRequirement",
]
