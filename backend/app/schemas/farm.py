"""Pydantic schemas for Farm Profile management."""

from datetime import date, datetime
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class SoilType(str, Enum):
    """Recognized soil types for agricultural suitability modeling."""

    CLAY = "clay"
    SANDY_LOAM = "sandy_loam"
    SILT_LOAM = "silt_loam"
    CLAY_LOAM = "clay_loam"
    SANDY = "sandy"
    LOAM = "loam"
    PEATY = "peaty"
    SALINE = "saline"


class IrrigationType(str, Enum):
    """Primary water delivery and irrigation types."""

    RAINFED = "rainfed"
    DRIP = "drip"
    SPRINKLER = "sprinkler"
    FLOOD_FURROW = "flood_furrow"
    CANAL = "canal"
    NONE = "none"


class CropHistoryRecord(BaseModel):
    """Historical crop rotation record for agronomic context."""

    crop_name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Name of harvested crop",
        examples=["Soybean"],
    )
    harvest_year: int = Field(
        ...,
        ge=1900,
        le=2100,
        description="Year of harvest",
        examples=[2023],
    )
    season: Optional[str] = Field(
        None,
        max_length=50,
        description="Growing season (e.g., Kharif, Rabi, Spring, Summer, Monsoon)",
        examples=["Kharif"],
    )
    yield_tonnes_per_hectare: Optional[float] = Field(
        None,
        ge=0.0,
        description="Reported crop yield in metric tonnes per hectare",
        examples=[2.8],
    )


class FarmBase(BaseModel):
    """Shared attributes for Farm Profile."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=150,
        description="Name or identifier of the farm/field",
        examples=["Punjab Valley Field A"],
    )
    farmer_name: Optional[str] = Field(
        None,
        max_length=100,
        description="Name of farmer, manager, or enterprise owner",
        examples=["Rajesh Patel"],
    )
    latitude: float = Field(
        ...,
        ge=-90.0,
        le=90.0,
        description="Latitude in decimal degrees (-90.0 to 90.0)",
        examples=[30.9010],
    )
    longitude: float = Field(
        ...,
        ge=-180.0,
        le=180.0,
        description="Longitude in decimal degrees (-180.0 to 180.0)",
        examples=[75.8573],
    )
    elevation_m: Optional[float] = Field(
        None,
        ge=-500.0,
        le=9000.0,
        description="Elevation above sea level in meters",
        examples=[244.0],
    )
    region: Optional[str] = Field(
        None,
        max_length=100,
        description="Administrative region, state, or province",
        examples=["Punjab"],
    )
    country: Optional[str] = Field(
        None,
        max_length=100,
        description="Country name or code",
        examples=["India"],
    )
    total_area_hectares: float = Field(
        ...,
        gt=0.0,
        le=1_000_000.0,
        description="Cultivable farm area in hectares",
        examples=[14.2],
    )
    soil_type: SoilType = Field(
        ...,
        description="Primary soil classification",
        examples=[SoilType.CLAY_LOAM],
    )
    soil_ph: Optional[float] = Field(
        None,
        ge=3.0,
        le=10.0,
        description="Soil pH measurement (3.0 to 10.0)",
        examples=[6.8],
    )
    organic_matter_pct: Optional[float] = Field(
        None,
        ge=0.0,
        le=100.0,
        description="Percentage of organic matter in soil (0.0 to 100.0)",
        examples=[2.4],
    )
    primary_irrigation: IrrigationType = Field(
        default=IrrigationType.RAINFED,
        description="Primary irrigation source",
        examples=[IrrigationType.CANAL],
    )
    current_crop: Optional[str] = Field(
        None,
        max_length=100,
        description="Crop currently standing in the field",
        examples=["Wheat"],
    )
    current_crop_planting_date: Optional[date] = Field(
        None,
        description="Planting date for current crop (YYYY-MM-DD)",
        examples=["2023-11-15"],
    )
    previous_crops: List[CropHistoryRecord] = Field(
        default_factory=list,
        description="Historical rotation sequence",
    )


class FarmCreate(FarmBase):
    """Payload schema for POST /api/farms and PUT /api/farms/{id}."""

    pass


class FarmUpdate(BaseModel):
    """Payload schema for PATCH /api/farms/{id} (all fields optional)."""

    name: Optional[str] = Field(None, min_length=1, max_length=150)
    farmer_name: Optional[str] = Field(None, max_length=100)
    latitude: Optional[float] = Field(None, ge=-90.0, le=90.0)
    longitude: Optional[float] = Field(None, ge=-180.0, le=180.0)
    elevation_m: Optional[float] = Field(None, ge=-500.0, le=9000.0)
    region: Optional[str] = Field(None, max_length=100)
    country: Optional[str] = Field(None, max_length=100)
    total_area_hectares: Optional[float] = Field(None, gt=0.0, le=1_000_000.0)
    soil_type: Optional[SoilType] = None
    soil_ph: Optional[float] = Field(None, ge=3.0, le=10.0)
    organic_matter_pct: Optional[float] = Field(None, ge=0.0, le=100.0)
    primary_irrigation: Optional[IrrigationType] = None
    current_crop: Optional[str] = Field(None, max_length=100)
    current_crop_planting_date: Optional[date] = None
    previous_crops: Optional[List[CropHistoryRecord]] = None


class FarmResponse(FarmBase):
    """Serialized farm profile response."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique UUID identifier")
    created_at: datetime = Field(..., description="UTC creation timestamp")
    updated_at: datetime = Field(..., description="UTC update timestamp")


class FarmListResponse(BaseModel):
    """Paginated list of farm profiles."""

    total: int = Field(..., description="Total count of matching farm profiles")
    items: List[FarmResponse] = Field(..., description="Page of farm profiles")
    skip: int = Field(..., description="Offset / skip count")
    limit: int = Field(..., description="Maximum page size")
