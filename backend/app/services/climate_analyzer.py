"""NASA Climate Intelligence Analyzer Service.

Fuses NASA POWER Earth observation reanalyses with verified agronomic parameters
from the Crop Knowledge Base to produce actionable, scientifically rigorous climate intelligence.
"""

from collections import defaultdict
from datetime import date, datetime, timezone
import math
from typing import Dict, List, Optional, Tuple
import numpy as np
import pandas as pd

from app.core.config import DATA_LIMITATIONS_NOTE
from app.schemas.climate import (
    ClimateMetadata,
    ClimateResponse,
    Coordinates,
    DailyClimateRecord,
    DateRange,
)
from app.schemas.climate_analyzer import (
    ClimateIntelligenceReport,
    ColdRiskIndicators,
    ColdRiskLevel,
    CompletenessCategory,
    CropClimateSuitability,
    CropGDDResult,
    HeatRiskIndicators,
    HeatRiskLevel,
    MissingDataAnalysis,
    MonthlyRainfall,
    RainfallAnalysis,
    SeasonalRainfall,
    TemperatureAnalysis,
    ThermalCompatibility,
    WaterCompatibility,
)
from app.schemas.crop import Crop, WaterDemandClass
from app.services.crop_catalog import crop_catalog_service
from app.services.nasa_power import nasa_power_service

SCIENTIFIC_PROVENANCE_DISCLOSURE = (
    "NASA Climate Intelligence synthesized using NASA GMAO MERRA-2 atmospheric assimilation "
    "(0.5° latitude x 0.625° longitude, ~50 km x ~60 km) and NASA CERES satellite solar irradiance "
    "(1.0° x 1.0°, ~110 km x ~110 km). Meteorological observations represent regional grid cell "
    "averages rather than in-situ field sensor measurements. Cold-hazard and heat-risk indicators "
    "represent threshold frequency counts; localized micro-climates, frost pockets, and slope aspects "
    "may cause field-level variations. GDD is calculated strictly for crops with verified base "
    "temperatures in accordance with FAO-56 and ICAR standards."
)

COLD_RISK_CAVEAT = (
    "Atmospheric temperatures from NASA GMAO MERRA-2 (0.5° x 0.625°) reflect 2-meter air temperatures. "
    "Surface ground temperatures can be 2-3°C cooler in low-lying micro-topography due to radiative "
    "nighttime cooling. These metrics represent atmospheric cold-stress hazard events, not direct field-level "
    "frost probabilities."
)

HEAT_THRESHOLD_NOTE = (
    "Heat stress threshold: T_max >= 35.0°C (induces pollen sterility and stomatal closure in C3 crops). "
    "Extreme heat threshold: T_max >= 40.0°C (causes rapid cellular dehydration and reproductive failure)."
)

# In-memory cache for climate intelligence reports
# Key: (rounded_lat, rounded_lon, start_str, end_str, crop_id)
# Value: (timestamp, report)
_REPORT_CACHE: Dict[Tuple[float, float, str, str, Optional[str]], Tuple[datetime, ClimateIntelligenceReport]] = {}
CACHE_TTL_SECONDS = 3600
CACHE_MAX_ENTRIES = 128


class ClimateAnalyzerService:
    """Service providing advanced agro-climatic intelligence from NASA POWER data."""

    def __init__(self, power_service=None, catalog_service=None):
        self._nasa_power = power_service or nasa_power_service
        self._crop_catalog = catalog_service or crop_catalog_service

    @property
    def cache(self) -> Dict[Tuple[float, float, str, str, Optional[str]], Tuple[datetime, ClimateIntelligenceReport]]:
        """Access the internal report cache dictionary."""
        return _REPORT_CACHE

    def clear_cache(self) -> None:
        """Clear the in-memory cache (useful for testing)."""
        _REPORT_CACHE.clear()

    async def generate_report(
        self,
        latitude: float,
        longitude: float,
        start_date: date,
        end_date: date,
        crop_id: Optional[str] = None,
        use_cache: bool = True,
    ) -> ClimateIntelligenceReport:
        """Fetch NASA POWER records and generate a comprehensive climate intelligence report."""
        rounded_lat = round(latitude, 3)
        rounded_lon = round(longitude, 3)
        start_str = start_date.isoformat()
        end_str = end_date.isoformat()
        crop_filter = crop_id.strip().lower() if crop_id else None
        cache_key = (rounded_lat, rounded_lon, start_str, end_str, crop_filter)

        if use_cache and cache_key in _REPORT_CACHE:
            cached_time, cached_report = _REPORT_CACHE[cache_key]
            if (datetime.now(timezone.utc) - cached_time).total_seconds() < CACHE_TTL_SECONDS:
                return cached_report

        # 1. Fetch raw daily climate data via NASA POWER service
        climate_response = await self._nasa_power.fetch_climate_data(
            latitude=latitude,
            longitude=longitude,
            start_date=start_date,
            end_date=end_date,
        )

        # 2. Analyze records
        report = self.analyze_climate_response(
            climate_response=climate_response,
            crop_id=crop_filter,
        )

        # 3. Cache report
        if use_cache:
            if len(_REPORT_CACHE) >= CACHE_MAX_ENTRIES:
                # Evict oldest entry
                oldest_key = min(_REPORT_CACHE.keys(), key=lambda k: _REPORT_CACHE[k][0])
                del _REPORT_CACHE[oldest_key]
            _REPORT_CACHE[cache_key] = (datetime.now(timezone.utc), report)

        return report

    def analyze_climate_response(
        self,
        climate_response: ClimateResponse,
        crop_id: Optional[str] = None,
    ) -> ClimateIntelligenceReport:
        """Perform comprehensive statistical and agronomic intelligence on pre-fetched climate records."""
        records = climate_response.records
        metadata = climate_response.metadata
        total_days = len(records)

        # 1. Missing Data Analysis
        missing_analysis = self._evaluate_missing_data(records)

        # 2. Rainfall Analysis
        rainfall_analysis = self._analyze_rainfall(records)

        # 3. Seasonal & Monthly Rainfall Distribution
        seasonal_rainfall = self._analyze_seasonal_rainfall(records, rainfall_analysis.total_rainfall_mm)
        monthly_rainfall = self._analyze_monthly_rainfall(records)

        # 4. Temperature Analysis
        temperature_analysis = self._analyze_temperatures(records)

        # 5. Heat Risk Indicators
        heat_risk = self._analyze_heat_risk(records)

        # 6. Cold Risk Indicators
        cold_risk = self._analyze_cold_risk(records)

        # 7. Crop-Specific GDD (Growing Degree Days)
        gdd_results = self._calculate_gdd(records, crop_id=crop_id)

        # 8. Crop Climate Suitability
        crop_suitability = self._evaluate_crop_suitability(
            rainfall=rainfall_analysis,
            temperature=temperature_analysis,
            heat_risk=heat_risk,
            cold_risk=cold_risk,
            crop_id=crop_id,
        )

        return ClimateIntelligenceReport(
            metadata=metadata,
            date_range_days=total_days,
            missing_data=missing_analysis,
            rainfall_analysis=rainfall_analysis,
            seasonal_rainfall=seasonal_rainfall,
            monthly_rainfall=monthly_rainfall,
            temperature_analysis=temperature_analysis,
            heat_risk=heat_risk,
            cold_risk=cold_risk,
            gdd_summary=gdd_results,
            crop_suitability=crop_suitability,
            scientific_provenance=SCIENTIFIC_PROVENANCE_DISCLOSURE,
        )

    # -------------------------------------------------------------------------
    # Private Analytics Modules
    # -------------------------------------------------------------------------

    def _evaluate_missing_data(
        self, records: List[DailyClimateRecord]
    ) -> MissingDataAnalysis:
        """Quantify completeness, missing values, and data reliability."""
        total_days = len(records)
        if total_days == 0:
            return MissingDataAnalysis(
                total_days_in_period=0,
                valid_observation_days=0,
                missing_observation_days=0,
                data_completeness_pct=0.0,
                completeness_category=CompletenessCategory.POOR,
                missing_parameters_summary={},
            )

        param_missing_counts: Dict[str, int] = defaultdict(int)
        valid_days_count = 0

        for r in records:
            has_valid_param = (
                r.temperature_mean_c is not None
                or r.temperature_max_c is not None
                or r.temperature_min_c is not None
                or r.precipitation_mm is not None
                or r.solar_radiation_mj_m2 is not None
                or r.relative_humidity_pct is not None
            )
            if has_valid_param:
                valid_days_count += 1

            for p in r.missing_parameters:
                param_missing_counts[p] += 1

        missing_days = total_days - valid_days_count
        completeness_pct = round((valid_days_count / total_days) * 100.0, 2)

        if completeness_pct >= 95.0:
            category = CompletenessCategory.EXCELLENT
        elif completeness_pct >= 85.0:
            category = CompletenessCategory.GOOD
        elif completeness_pct >= 70.0:
            category = CompletenessCategory.PARTIAL
        else:
            category = CompletenessCategory.POOR

        return MissingDataAnalysis(
            total_days_in_period=total_days,
            valid_observation_days=valid_days_count,
            missing_observation_days=missing_days,
            data_completeness_pct=completeness_pct,
            completeness_category=category,
            missing_parameters_summary=dict(param_missing_counts),
        )

    def _analyze_rainfall(
        self, records: List[DailyClimateRecord]
    ) -> RainfallAnalysis:
        """Calculate historical precipitation, dry/wet spells, and rainfall variability."""
        precip_vals = [
            r.precipitation_mm for r in records if r.precipitation_mm is not None
        ]

        if not precip_vals:
            return RainfallAnalysis(
                total_rainfall_mm=None,
                mean_daily_rainfall_mm=None,
                max_single_day_rainfall_mm=None,
                rainy_days_count=0,
                dry_days_count=0,
                consecutive_dry_days_max=0,
                consecutive_wet_days_max=0,
                rainfall_variance=None,
                rainfall_std_dev=None,
            )

        total_mm = round(float(sum(precip_vals)), 2)
        mean_daily = round(float(np.mean(precip_vals)), 2)
        max_daily = round(float(np.max(precip_vals)), 2)
        variance = round(float(np.var(precip_vals)), 2)
        std_dev = round(float(np.std(precip_vals)), 2)

        rainy_days = sum(1 for p in precip_vals if p >= 1.0)
        dry_days = sum(1 for p in precip_vals if p < 1.0)

        # Calculate contiguous dry spells and wet spells
        max_dry_streak = 0
        current_dry_streak = 0
        max_wet_streak = 0
        current_wet_streak = 0

        for r in records:
            p = r.precipitation_mm
            if p is None:
                # Reset contiguous counters across missing values to avoid unverified assumptions
                current_dry_streak = 0
                current_wet_streak = 0
                continue

            if p < 1.0:
                current_dry_streak += 1
                current_wet_streak = 0
                if current_dry_streak > max_dry_streak:
                    max_dry_streak = current_dry_streak
            else:
                current_wet_streak += 1
                current_dry_streak = 0
                if current_wet_streak > max_wet_streak:
                    max_wet_streak = current_wet_streak

        return RainfallAnalysis(
            total_rainfall_mm=total_mm,
            mean_daily_rainfall_mm=mean_daily,
            max_single_day_rainfall_mm=max_daily,
            rainy_days_count=rainy_days,
            dry_days_count=dry_days,
            consecutive_dry_days_max=max_dry_streak,
            consecutive_wet_days_max=max_wet_streak,
            rainfall_variance=variance,
            rainfall_std_dev=std_dev,
        )

    def _analyze_seasonal_rainfall(
        self, records: List[DailyClimateRecord], total_rainfall_mm: Optional[float]
    ) -> List[SeasonalRainfall]:
        """Aggregate rainfall into regional agricultural seasons (Kharif, Rabi, Summer)."""
        # West Bengal / Eastern India standard agro-seasons:
        # 1. Kharif / Monsoon: Months 6, 7, 8, 9, 10 (June to October)
        # 2. Rabi / Winter: Months 11, 12, 1, 2 (November to February)
        # 3. Summer / Pre-Kharif (Aus/Zaid): Months 3, 4, 5 (March to May)
        season_definitions = [
            {
                "name": "Kharif / Monsoon",
                "months": {6, 7, 8, 9, 10},
                "calendar": "Jun - Oct",
            },
            {
                "name": "Rabi / Winter",
                "months": {11, 12, 1, 2},
                "calendar": "Nov - Feb",
            },
            {
                "name": "Summer / Pre-Kharif (Aus / Zaid)",
                "months": {3, 4, 5},
                "calendar": "Mar - May",
            },
        ]

        results: List[SeasonalRainfall] = []
        overall_total = total_rainfall_mm or 0.0

        for s_def in season_definitions:
            season_precips = []
            rainy_days = 0

            for r in records:
                try:
                    month = int(r.date[5:7])
                except (ValueError, IndexError):
                    continue

                if month in s_def["months"]:
                    if r.precipitation_mm is not None:
                        season_precips.append(r.precipitation_mm)
                        if r.precipitation_mm >= 1.0:
                            rainy_days += 1

            season_total = round(float(sum(season_precips)), 2)
            pct = (
                round((season_total / overall_total) * 100.0, 1)
                if overall_total > 0.0
                else 0.0
            )

            results.append(
                SeasonalRainfall(
                    season_name=s_def["name"],
                    calendar_months=s_def["calendar"],
                    total_rainfall_mm=season_total,
                    percentage_of_total=pct,
                    rainy_days_count=rainy_days,
                )
            )

        return results

    def _analyze_monthly_rainfall(
        self, records: List[DailyClimateRecord]
    ) -> List[MonthlyRainfall]:
        """Group rainfall into chronological monthly buckets."""
        monthly_groups: Dict[str, List[float]] = defaultdict(list)

        for r in records:
            if len(r.date) >= 7 and r.precipitation_mm is not None:
                month_key = r.date[:7]
                monthly_groups[month_key].append(r.precipitation_mm)

        results: List[MonthlyRainfall] = []
        for m_key in sorted(monthly_groups.keys()):
            p_list = monthly_groups[m_key]
            total = round(float(sum(p_list)), 2)
            rainy = sum(1 for p in p_list if p >= 1.0)
            mean_val = round(float(np.mean(p_list)), 2) if p_list else 0.0

            results.append(
                MonthlyRainfall(
                    year_month=m_key,
                    total_mm=total,
                    rainy_days=rainy,
                    mean_daily_mm=mean_val,
                )
            )

        return results

    def _analyze_temperatures(
        self, records: List[DailyClimateRecord]
    ) -> TemperatureAnalysis:
        """Compute mean, extremes, and diurnal thermal metrics."""
        t2m_vals = [r.temperature_mean_c for r in records if r.temperature_mean_c is not None]
        t2m_min_vals = [r.temperature_min_c for r in records if r.temperature_min_c is not None]
        t2m_max_vals = [r.temperature_max_c for r in records if r.temperature_max_c is not None]

        diurnal_ranges = [
            r.temperature_max_c - r.temperature_min_c
            for r in records
            if r.temperature_max_c is not None and r.temperature_min_c is not None
        ]

        return TemperatureAnalysis(
            mean_temperature_c=round(float(np.mean(t2m_vals)), 2) if t2m_vals else None,
            lowest_recorded_min_c=round(float(np.min(t2m_min_vals)), 2) if t2m_min_vals else None,
            highest_recorded_max_c=round(float(np.max(t2m_max_vals)), 2) if t2m_max_vals else None,
            mean_daily_min_c=round(float(np.mean(t2m_min_vals)), 2) if t2m_min_vals else None,
            mean_daily_max_c=round(float(np.mean(t2m_max_vals)), 2) if t2m_max_vals else None,
            mean_diurnal_range_c=round(float(np.mean(diurnal_ranges)), 2) if diurnal_ranges else None,
        )

    def _analyze_heat_risk(
        self, records: List[DailyClimateRecord]
    ) -> HeatRiskIndicators:
        """Count heat stress days and assign categorical heat risk tier."""
        heat_stress_count = 0
        extreme_heat_count = 0

        for r in records:
            if r.temperature_max_c is not None:
                if r.temperature_max_c >= 35.0:
                    heat_stress_count += 1
                if r.temperature_max_c >= 40.0:
                    extreme_heat_count += 1

        if extreme_heat_count >= 5 or heat_stress_count >= 25:
            level = HeatRiskLevel.EXTREME
        elif extreme_heat_count >= 1 or heat_stress_count >= 15:
            level = HeatRiskLevel.HIGH
        elif heat_stress_count >= 5:
            level = HeatRiskLevel.MODERATE
        elif heat_stress_count >= 1:
            level = HeatRiskLevel.LOW
        else:
            level = HeatRiskLevel.NONE

        return HeatRiskIndicators(
            heat_stress_days_count=heat_stress_count,
            extreme_heat_days_count=extreme_heat_count,
            heat_risk_level=level,
            threshold_note=HEAT_THRESHOLD_NOTE,
        )

    def _analyze_cold_risk(
        self, records: List[DailyClimateRecord]
    ) -> ColdRiskIndicators:
        """Quantify cold stress and near-freezing hazard days."""
        cold_stress_count = 0
        near_freezing_count = 0

        for r in records:
            if r.temperature_min_c is not None:
                if r.temperature_min_c <= 5.0:
                    cold_stress_count += 1
                if r.temperature_min_c <= 2.0:
                    near_freezing_count += 1

        if near_freezing_count >= 3:
            level = ColdRiskLevel.HIGH
        elif near_freezing_count >= 1 or cold_stress_count >= 10:
            level = ColdRiskLevel.MODERATE
        elif cold_stress_count >= 1:
            level = ColdRiskLevel.LOW
        else:
            level = ColdRiskLevel.NONE

        return ColdRiskIndicators(
            cold_stress_days_count=cold_stress_count,
            near_freezing_hazard_days_count=near_freezing_count,
            frost_hazard_level=level,
            scientific_caveat=COLD_RISK_CAVEAT,
        )

    def _calculate_gdd(
        self,
        records: List[DailyClimateRecord],
        crop_id: Optional[str] = None,
    ) -> List[CropGDDResult]:
        """Calculate cumulative Growing Degree Days (GDD) strictly for crops with verified base temperatures.

        Formula: Daily GDD = max(((T_max + T_min) / 2) - T_base, 0)
        Days missing T_max or T_min are excluded from summation.
        """
        all_crops = self._crop_catalog.get_all_crops()
        if crop_id:
            target_crop = self._crop_catalog.get_crop(crop_id)
            crops_to_evaluate = [target_crop] if target_crop else []
        else:
            crops_to_evaluate = all_crops

        results: List[CropGDDResult] = []

        for crop in crops_to_evaluate:
            t_req = crop.temperature_requirement
            t_base = t_req.gdd_base_temp_c
            is_verified = t_req.gdd_base_verified and t_base is not None

            if not is_verified:
                results.append(
                    CropGDDResult(
                        crop_id=crop.crop_id,
                        crop_name=crop.crop_name,
                        gdd_base_temp_c=None,
                        is_verified_base=False,
                        accumulated_gdd=None,
                        valid_gdd_days=0,
                        methodology="GDD calculation omitted: Base temperature is unverified in literature.",
                    )
                )
                continue

            daily_gdd_sum = 0.0
            valid_days = 0

            for r in records:
                if r.temperature_max_c is not None and r.temperature_min_c is not None:
                    mean_t = (r.temperature_max_c + r.temperature_min_c) / 2.0
                    gdd_day = max(mean_t - t_base, 0.0)
                    daily_gdd_sum += gdd_day
                    valid_days += 1

            accumulated = round(daily_gdd_sum, 1) if valid_days > 0 else None

            results.append(
                CropGDDResult(
                    crop_id=crop.crop_id,
                    crop_name=crop.crop_name,
                    gdd_base_temp_c=t_base,
                    is_verified_base=True,
                    accumulated_gdd=accumulated,
                    valid_gdd_days=valid_days,
                    methodology=f"Daily GDD = max(((T_max + T_min) / 2) - {t_base}°C, 0.0)",
                )
            )

        return results

    def _evaluate_crop_suitability(
        self,
        rainfall: RainfallAnalysis,
        temperature: TemperatureAnalysis,
        heat_risk: HeatRiskIndicators,
        cold_risk: ColdRiskIndicators,
        crop_id: Optional[str] = None,
    ) -> List[CropClimateSuitability]:
        """Evaluate crop thermal and water compatibility based strictly on verified parameters."""
        all_crops = self._crop_catalog.get_all_crops()
        if crop_id:
            target_crop = self._crop_catalog.get_crop(crop_id)
            crops_to_evaluate = [target_crop] if target_crop else []
        else:
            crops_to_evaluate = all_crops

        results: List[CropClimateSuitability] = []

        mean_temp = temperature.mean_temperature_c
        total_precip = rainfall.total_rainfall_mm

        for crop in crops_to_evaluate:
            t_req = crop.temperature_requirement
            w_req = crop.water_requirement
            caveats: List[str] = []

            # 1. Thermal Compatibility
            if mean_temp is not None:
                if t_req.optimal_min_temp_c <= mean_temp <= t_req.optimal_max_temp_c:
                    thermal_comp = ThermalCompatibility.OPTIMAL
                    thermal_score = 100.0
                elif t_req.min_temp_c <= mean_temp <= t_req.max_temp_c:
                    thermal_comp = ThermalCompatibility.SUITABLE
                    thermal_score = 75.0
                    if mean_temp < t_req.optimal_min_temp_c:
                        caveats.append(
                            f"Observed mean temperature ({mean_temp}°C) is slightly below optimal range "
                            f"({t_req.optimal_min_temp_c}-{t_req.optimal_max_temp_c}°C)."
                        )
                    else:
                        caveats.append(
                            f"Observed mean temperature ({mean_temp}°C) is above optimal range "
                            f"({t_req.optimal_min_temp_c}-{t_req.optimal_max_temp_c}°C)."
                        )
                else:
                    thermal_comp = ThermalCompatibility.UNSUITABLE
                    thermal_score = 25.0
                    caveats.append(
                        f"Observed mean temperature ({mean_temp}°C) falls outside physiological limits "
                        f"({t_req.min_temp_c}-{t_req.max_temp_c}°C)."
                    )
            else:
                thermal_comp = ThermalCompatibility.MARGINAL
                thermal_score = 50.0

            # Heat risk impact
            if heat_risk.heat_stress_days_count >= 1:
                if crop.crop_id == "wheat":
                    caveats.append(
                        f"Wheat is sensitive to terminal heat: {heat_risk.heat_stress_days_count} heat stress days "
                        "(T_max >= 35°C) recorded."
                    )
                    thermal_score = max(thermal_score - (10.0 * heat_risk.heat_stress_days_count), 10.0)

            # Cold risk impact
            if cold_risk.cold_stress_days_count >= 1:
                if crop.crop_id in ("rice", "green_gram"):
                    caveats.append(
                        f"Warm-season crop {crop.crop_name} exposed to {cold_risk.cold_stress_days_count} "
                        "cold stress days (T_min <= 5°C)."
                    )
                    thermal_score = max(thermal_score - (10.0 * cold_risk.cold_stress_days_count), 10.0)

            # 2. Water Compatibility
            if total_precip is not None:
                if w_req.min_mm <= total_precip <= w_req.max_mm * 1.3:
                    water_comp = WaterCompatibility.OPTIMAL
                    water_score = 100.0
                elif total_precip < w_req.min_mm:
                    deficit_mm = round(w_req.min_mm - total_precip, 1)
                    if w_req.demand_class == WaterDemandClass.VERY_HIGH:
                        water_comp = WaterCompatibility.IRRIGATION_DEPENDENT
                        water_score = 40.0
                        caveats.append(
                            f"Rainfall ({total_precip} mm) is insufficient for high-water crop ({w_req.min_mm}-{w_req.max_mm} mm); "
                            f"deficit of ~{deficit_mm} mm must be bridged by assured irrigation."
                        )
                    else:
                        water_comp = WaterCompatibility.DEFICIT_RISK
                        water_score = 60.0
                        caveats.append(
                            f"Precipitation deficit of ~{deficit_mm} mm against crop minimum ({w_req.min_mm} mm); "
                            "supplemental irrigation recommended during critical stages."
                        )
                else:
                    # Surplus precipitation
                    surplus_mm = round(total_precip - w_req.max_mm, 1)
                    if crop.soil_suitability.drainage_requirement.lower().find("well-drained") != -1:
                        water_comp = WaterCompatibility.SURPLUS_RISK
                        water_score = 55.0
                        caveats.append(
                            f"Observed rainfall ({total_precip} mm) exceeds maximum need ({w_req.max_mm} mm) by {surplus_mm} mm; "
                            "adequate drainage required to prevent waterlogging."
                        )
                    else:
                        water_comp = WaterCompatibility.OPTIMAL
                        water_score = 90.0
            else:
                water_comp = WaterCompatibility.DEFICIT_RISK
                water_score = 50.0

            # Composite Score (50% thermal, 50% water)
            if mean_temp is not None and total_precip is not None:
                composite_score = round((thermal_score * 0.5) + (water_score * 0.5), 1)
            else:
                composite_score = None

            results.append(
                CropClimateSuitability(
                    crop_id=crop.crop_id,
                    crop_name=crop.crop_name,
                    thermal_compatibility=thermal_comp,
                    water_compatibility=water_comp,
                    overall_climate_score=composite_score,
                    observed_mean_temp_c=mean_temp,
                    crop_optimal_temp_range=f"{t_req.optimal_min_temp_c} - {t_req.optimal_max_temp_c} °C",
                    observed_rainfall_mm=total_precip,
                    crop_water_need_mm_range=f"{w_req.min_mm} - {w_req.max_mm} mm",
                    agronomic_caveats=caveats,
                )
            )

        return results


climate_analyzer_service = ClimateAnalyzerService()
