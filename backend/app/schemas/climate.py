"""Climate endpoint request and response schemas."""

from datetime import date, datetime
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class Coordinates(BaseModel):
    """Geographic point coordinates."""

    latitude: float = Field(..., ge=-90.0, le=90.0, description="Latitude in decimal degrees")
    longitude: float = Field(..., ge=-180.0, le=180.0, description="Longitude in decimal degrees")


class DateRange(BaseModel):
    """Date span for climate query."""

    start_date: str = Field(..., description="Query start date in YYYY-MM-DD")
    end_date: str = Field(..., description="Query end date in YYYY-MM-DD")


class ParameterDetail(BaseModel):
    """Detailed scientific provenance for an individual parameter."""

    name: str = Field(..., description="Full parameter name")
    units: str = Field(..., description="Standard measurement units")
    source: str = Field(..., description="NASA observational or assimilation model source")
    spatial_resolution: str = Field(..., description="Specific spatial grid resolution")
    description: str = Field(..., description="Parameter description")


class ClimateMetadata(BaseModel):
    """Scientific metadata and data provenance."""

    data_source: str = Field(..., description="Data provider attribution")
    retrieval_timestamp: datetime = Field(..., description="UTC timestamp of data retrieval")
    coordinates: Coordinates = Field(..., description="Requested location coordinates")
    date_range: DateRange = Field(..., description="Requested date span")
    parameters_info: Dict[str, ParameterDetail] = Field(
        ..., description="Parameter-specific source and resolution details"
    )
    data_limitations: str = Field(..., description="Scientific limitations and resolution notice")
    is_simulated: bool = Field(
        False,
        description="Explicit flag: false indicates real NASA observation; true indicates demo/simulated data",
    )


class DailyClimateRecord(BaseModel):
    """Daily agro-climatological observation."""

    date: str = Field(..., description="Date of observation in YYYY-MM-DD")
    temperature_mean_c: Optional[float] = Field(None, description="Daily mean 2m temperature in °C")
    temperature_max_c: Optional[float] = Field(None, description="Daily max 2m temperature in °C")
    temperature_min_c: Optional[float] = Field(None, description="Daily min 2m temperature in °C")
    precipitation_mm: Optional[float] = Field(None, description="Corrected precipitation in mm/day")
    solar_radiation_mj_m2: Optional[float] = Field(
        None, description="All sky surface shortwave downward irradiance in MJ/m²/day"
    )
    relative_humidity_pct: Optional[float] = Field(None, description="Relative humidity at 2m in %")
    missing_parameters: List[str] = Field(
        default_factory=list,
        description="Parameters with missing observations (-999.0 fill values) on this day",
    )


class ClimateSummary(BaseModel):
    """Aggregated agro-climate statistics over the queried date range."""

    avg_temperature_c: Optional[float] = Field(None, description="Mean temperature across valid days in °C")
    min_temperature_c: Optional[float] = Field(None, description="Absolute lowest temperature in period in °C")
    max_temperature_c: Optional[float] = Field(None, description="Absolute highest temperature in period in °C")
    total_precipitation_mm: Optional[float] = Field(None, description="Cumulative precipitation in mm")
    avg_precipitation_daily_mm: Optional[float] = Field(None, description="Average daily precipitation in mm/day")
    avg_solar_radiation_mj_m2: Optional[float] = Field(
        None, description="Mean daily solar radiation in MJ/m²/day"
    )
    avg_relative_humidity_pct: Optional[float] = Field(None, description="Mean relative humidity in %")
    total_days: int = Field(..., description="Total days requested in date range")
    valid_data_days: int = Field(..., description="Count of days with at least one valid parameter")


class ClimateResponse(BaseModel):
    """Top-level response payload for GET /api/climate."""

    metadata: ClimateMetadata
    summary: ClimateSummary
    records: List[DailyClimateRecord]
