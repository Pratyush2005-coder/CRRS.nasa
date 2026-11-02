"""Pydantic schemas for NASA Climate Intelligence Analysis."""

from datetime import date
from enum import Enum
from typing import Dict, List, Optional
from pydantic import BaseModel, Field

from app.schemas.climate import ClimateMetadata


class HeatRiskLevel(str, Enum):
    """Categorical classification of thermal heat stress."""

    NONE = "NONE"
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    EXTREME = "EXTREME"


class ColdRiskLevel(str, Enum):
    """Categorical classification of cold / near-freezing hazard."""

    NONE = "NONE"
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"


class CompletenessCategory(str, Enum):
    """Data completeness tiers."""

    EXCELLENT = "EXCELLENT"  # >= 95% valid records
    GOOD = "GOOD"  # >= 85% valid records
    PARTIAL = "PARTIAL"  # >= 70% valid records
    POOR = "POOR"  # < 70% valid records


class ThermalCompatibility(str, Enum):
    """Suitability of observed thermal range against crop cardinal temperatures."""

    OPTIMAL = "OPTIMAL"
    SUITABLE = "SUITABLE"
    MARGINAL = "MARGINAL"
    UNSUITABLE = "UNSUITABLE"


class WaterCompatibility(str, Enum):
    """Hydrological balance of observed rainfall vs crop water demand."""

    OPTIMAL = "OPTIMAL"
    DEFICIT_RISK = "DEFICIT_RISK"
    SURPLUS_RISK = "SURPLUS_RISK"
    IRRIGATION_DEPENDENT = "IRRIGATION_DEPENDENT"


class RainfallAnalysis(BaseModel):
    """Comprehensive precipitation and drought-spell analytics."""

    total_rainfall_mm: Optional[float] = Field(None, description="Cumulative precipitation in mm")
    mean_daily_rainfall_mm: Optional[float] = Field(None, description="Average daily precipitation in mm/day")
    max_single_day_rainfall_mm: Optional[float] = Field(None, description="Peak single-day precipitation in mm")
    rainy_days_count: int = Field(..., description="Days with precipitation >= 1.0 mm (standard meteorological threshold)")
    dry_days_count: int = Field(..., description="Days with precipitation < 1.0 mm")
    consecutive_dry_days_max: int = Field(..., description="Maximum duration of consecutive dry days (drought spell proxy)")
    consecutive_wet_days_max: int = Field(..., description="Maximum duration of consecutive rainy days")
    rainfall_variance: Optional[float] = Field(None, description="Variance of daily precipitation values")
    rainfall_std_dev: Optional[float] = Field(None, description="Standard deviation of daily precipitation values")


class MonthlyRainfall(BaseModel):
    """Monthly precipitation aggregation."""

    year_month: str = Field(..., description="Calendar year and month in YYYY-MM format")
    total_mm: float = Field(..., description="Total rainfall for the month in mm")
    rainy_days: int = Field(..., description="Count of days with rainfall >= 1.0 mm")
    mean_daily_mm: float = Field(..., description="Average daily rainfall in mm/day")


class SeasonalRainfall(BaseModel):
    """Precipitation distribution segmented across regional agricultural cropping seasons."""

    season_name: str = Field(..., description="Agricultural season (e.g., 'Kharif / Monsoon', 'Rabi / Winter')")
    calendar_months: str = Field(..., description="Calendar months included (e.g., 'Jun - Oct')")
    total_rainfall_mm: float = Field(..., description="Total precipitation in season in mm")
    percentage_of_total: float = Field(..., description="Percentage of queried period's total rainfall (0-100%)")
    rainy_days_count: int = Field(..., description="Days with precipitation >= 1.0 mm in this season")


class TemperatureAnalysis(BaseModel):
    """Statistical thermal analysis over the period."""

    mean_temperature_c: Optional[float] = Field(None, description="Mean 2m temperature in °C")
    lowest_recorded_min_c: Optional[float] = Field(None, description="Absolute lowest daily minimum temperature in °C")
    highest_recorded_max_c: Optional[float] = Field(None, description="Absolute highest daily maximum temperature in °C")
    mean_daily_min_c: Optional[float] = Field(None, description="Mean of daily minimum temperatures in °C")
    mean_daily_max_c: Optional[float] = Field(None, description="Mean of daily maximum temperatures in °C")
    mean_diurnal_range_c: Optional[float] = Field(None, description="Average daily temperature range (Tmax - Tmin) in °C")


class HeatRiskIndicators(BaseModel):
    """High-temperature stress metrics for agricultural crops."""

    heat_stress_days_count: int = Field(
        ...,
        description="Days where daily maximum temperature reaches or exceeds 35.0°C (C3 crop reproductive stress threshold)",
    )
    extreme_heat_days_count: int = Field(
        ...,
        description="Days where daily maximum temperature reaches or exceeds 40.0°C (cellular damage / pollen sterility threshold)",
    )
    heat_risk_level: HeatRiskLevel = Field(..., description="Categorical evaluation of heat hazard")
    threshold_note: str = Field(
        ...,
        description="Scientific definition of thresholds used",
    )


class ColdRiskIndicators(BaseModel):
    """Low-temperature hazard metrics."""

    cold_stress_days_count: int = Field(
        ...,
        description="Days where daily minimum temperature drops to or below 5.0°C (chilling injury threshold for tropical crops)",
    )
    near_freezing_hazard_days_count: int = Field(
        ...,
        description="Days where daily minimum temperature drops to or below 2.0°C (indicative of frost risk in low-lying micro-topography)",
    )
    frost_hazard_level: ColdRiskLevel = Field(..., description="Categorical cold hazard classification")
    scientific_caveat: str = Field(
        ...,
        description="Scientific disclosure distinguishing atmospheric grid reanalysis from field surface temperature",
    )


class CropGDDResult(BaseModel):
    """Growing Degree Days (GDD) calculation for a verified crop."""

    crop_id: str = Field(..., description="Crop identifier")
    crop_name: str = Field(..., description="Common crop name")
    gdd_base_temp_c: Optional[float] = Field(None, description="Verified base threshold temperature (T_base) in °C")
    is_verified_base: bool = Field(..., description="Whether base temperature is peer-reviewed and verified")
    accumulated_gdd: Optional[float] = Field(None, description="Cumulative GDD accumulated over valid days in °C-days")
    valid_gdd_days: int = Field(..., description="Number of days with valid temperature records used in summation")
    methodology: str = Field(..., description="Mathematical formula used for GDD summation")


class CropClimateSuitability(BaseModel):
    """Agro-ecological suitability evaluation for an individual crop under observed climate."""

    crop_id: str
    crop_name: str
    thermal_compatibility: ThermalCompatibility
    water_compatibility: WaterCompatibility
    overall_climate_score: Optional[float] = Field(
        None,
        ge=0.0,
        le=100.0,
        description="Calculated composite suitability score (0-100) based strictly on verified parameters",
    )
    observed_mean_temp_c: Optional[float]
    crop_optimal_temp_range: str
    observed_rainfall_mm: Optional[float]
    crop_water_need_mm_range: str
    agronomic_caveats: List[str] = Field(default_factory=list)


class MissingDataAnalysis(BaseModel):
    """Quality and completeness evaluation of the underlying NASA POWER dataset."""

    total_days_in_period: int = Field(..., description="Total calendar days spanned by requested date range")
    valid_observation_days: int = Field(..., description="Days with at least one valid meteorological parameter")
    missing_observation_days: int = Field(..., description="Days completely lacking observations")
    data_completeness_pct: float = Field(..., description="Percentage of valid observation days (0.0 - 100.0%)")
    completeness_category: CompletenessCategory = Field(..., description="Data completeness status")
    missing_parameters_summary: Dict[str, int] = Field(
        default_factory=dict,
        description="Count of missing instances (-999.0 fill values) per individual NASA parameter",
    )


class ClimateIntelligenceReport(BaseModel):
    """Complete modular NASA Climate Intelligence Report payload."""

    metadata: ClimateMetadata
    date_range_days: int = Field(..., description="Total days queried in date range")
    missing_data: MissingDataAnalysis
    rainfall_analysis: RainfallAnalysis
    seasonal_rainfall: List[SeasonalRainfall]
    monthly_rainfall: List[MonthlyRainfall]
    temperature_analysis: TemperatureAnalysis
    heat_risk: HeatRiskIndicators
    cold_risk: ColdRiskIndicators
    gdd_summary: List[CropGDDResult]
    crop_suitability: List[CropClimateSuitability]
    scientific_provenance: str = Field(..., description="Complete scientific and spatial resolution disclosures")
