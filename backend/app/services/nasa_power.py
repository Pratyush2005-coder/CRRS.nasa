"""NASA POWER API client and data processing service."""

from datetime import date, datetime, timezone
import logging
from typing import Any, Dict, List, Optional
from fastapi import HTTPException, status
import httpx
import numpy as np
import pandas as pd

from app.core.config import DATA_LIMITATIONS_NOTE, PARAMETER_REGISTRY, settings
from app.schemas.climate import (
    ClimateMetadata,
    ClimateResponse,
    ClimateSummary,
    Coordinates,
    DailyClimateRecord,
    DateRange,
    ParameterDetail,
)

logger = logging.getLogger(__name__)

# NASA POWER fill value representing missing or uncalculated parameters
MISSING_VALUE_THRESHOLD = -900.0


def is_missing_value(val: Any) -> bool:
    """Check if value represents a NASA POWER missing/fill value indicator (-999.0)."""
    if val is None:
        return True
    try:
        f_val = float(val)
        return f_val <= MISSING_VALUE_THRESHOLD or np.isnan(f_val)
    except (ValueError, TypeError):
        return True


def clean_parameter_value(val: Any) -> Optional[float]:
    """Clean and round valid float parameter, converting fill values to None."""
    if is_missing_value(val):
        return None
    return round(float(val), 2)


class NasaPowerService:
    """Asynchronous client for querying NASA POWER API and parsing agro-climatology data."""

    def __init__(self, client: Optional[httpx.AsyncClient] = None):
        self._client = client

    def _get_parameters_dict(self) -> Dict[str, ParameterDetail]:
        """Build parameter provenance dictionary from registry."""
        return {
            param: ParameterDetail(
                name=info["name"],
                units=info["units"],
                source=info["source"],
                spatial_resolution=info["spatial_resolution"],
                description=info["description"],
            )
            for param, info in PARAMETER_REGISTRY.items()
        }

    async def fetch_climate_data(
        self,
        latitude: float,
        longitude: float,
        start_date: date,
        end_date: date,
    ) -> ClimateResponse:
        """Fetch daily agro-climatology data from NASA POWER API.

        Raises:
            HTTPException: If upstream API returns an error or is unreachable.
        """
        # Format dates as YYYYMMDD required by NASA POWER API
        start_str = start_date.strftime("%Y%m%d")
        end_str = end_date.strftime("%Y%m%d")

        requested_parameters = list(PARAMETER_REGISTRY.keys())
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "start": start_str,
            "end": end_str,
            "community": settings.NASA_POWER_COMMUNITY,
            "parameters": ",".join(requested_parameters),
            "format": "JSON",
            "user": "AGROVERSEAI",
        }

        async def _query(client: httpx.AsyncClient) -> Dict[str, Any]:
            try:
                response = await client.get(
                    settings.NASA_POWER_BASE_URL,
                    params=params,
                    timeout=settings.NASA_POWER_TIMEOUT_SECONDS,
                )
            except httpx.TimeoutException as exc:
                logger.error(f"NASA POWER API request timed out: {exc}")
                raise HTTPException(
                    status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                    detail="Upstream NASA POWER API request timed out. Please try a narrower date range or retry later.",
                ) from exc
            except httpx.RequestError as exc:
                logger.error(f"Network error querying NASA POWER API: {exc}")
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"Unable to connect to NASA POWER API: {str(exc)}",
                ) from exc

            if response.status_code != 200:
                logger.error(
                    f"NASA POWER API returned HTTP {response.status_code}: {response.text}"
                )
                error_detail = f"NASA POWER API error (HTTP {response.status_code})"
                try:
                    err_json = response.json()
                    if "messages" in err_json:
                        error_detail = f"NASA POWER API error: {err_json['messages']}"
                    else:
                        error_detail = f"NASA POWER API error (HTTP {response.status_code}): {response.text[:200]}"
                except Exception:
                    error_detail = f"NASA POWER API error (HTTP {response.status_code}): {response.text[:200]}"

                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=error_detail,
                )

            return response.json()

        if self._client:
            raw_data = await _query(self._client)
        else:
            async with httpx.AsyncClient() as client:
                raw_data = await _query(client)

        return self.parse_nasa_response(
            raw_data=raw_data,
            latitude=latitude,
            longitude=longitude,
            start_date=start_date,
            end_date=end_date,
        )

    def parse_nasa_response(
        self,
        raw_data: Dict[str, Any],
        latitude: float,
        longitude: float,
        start_date: date,
        end_date: date,
    ) -> ClimateResponse:
        """Parse raw NASA POWER JSON into structured Pydantic models.

        Ensures scientific integrity:
        - Replaces -999.0 with None.
        - Keeps record of missing parameters.
        - Calculates statistical aggregates using Pandas.
        - Sets is_simulated to False strictly because data was received from NASA.
        """
        properties = raw_data.get("properties", {})
        param_data = properties.get("parameter", {})

        # Extract dates from parameters
        date_keys = set()
        for p_key, values in param_data.items():
            if isinstance(values, dict):
                date_keys.update(values.keys())

        sorted_dates = sorted(list(date_keys))

        records: List[DailyClimateRecord] = []
        for d_str in sorted_dates:
            # Parse YYYYMMDD to YYYY-MM-DD
            formatted_date = (
                f"{d_str[:4]}-{d_str[4:6]}-{d_str[6:]}"
                if len(d_str) == 8
                else d_str
            )

            t2m_raw = param_data.get("T2M", {}).get(d_str)
            t2m_max_raw = param_data.get("T2M_MAX", {}).get(d_str)
            t2m_min_raw = param_data.get("T2M_MIN", {}).get(d_str)
            precip_raw = param_data.get("PRECTOTCORR", {}).get(d_str)
            solar_raw = param_data.get("ALLSKY_SFC_SW_DWN", {}).get(d_str)
            rh_raw = param_data.get("RH2M", {}).get(d_str)

            missing: List[str] = []
            if is_missing_value(t2m_raw):
                missing.append("T2M")
            if is_missing_value(t2m_max_raw):
                missing.append("T2M_MAX")
            if is_missing_value(t2m_min_raw):
                missing.append("T2M_MIN")
            if is_missing_value(precip_raw):
                missing.append("PRECTOTCORR")
            if is_missing_value(solar_raw):
                missing.append("ALLSKY_SFC_SW_DWN")
            if is_missing_value(rh_raw):
                missing.append("RH2M")

            record = DailyClimateRecord(
                date=formatted_date,
                temperature_mean_c=clean_parameter_value(t2m_raw),
                temperature_max_c=clean_parameter_value(t2m_max_raw),
                temperature_min_c=clean_parameter_value(t2m_min_raw),
                precipitation_mm=clean_parameter_value(precip_raw),
                solar_radiation_mj_m2=clean_parameter_value(solar_raw),
                relative_humidity_pct=clean_parameter_value(rh_raw),
                missing_parameters=missing,
            )
            records.append(record)

        # Compute summary metrics using Pandas
        summary = self._compute_summary(records)

        # Build verified metadata with parameter-specific provenance
        metadata = ClimateMetadata(
            data_source=(
                "NASA Langley Research Center (LaRC) POWER Project "
                "- Agroclimatology (AG) Community"
            ),
            retrieval_timestamp=datetime.now(timezone.utc),
            coordinates=Coordinates(latitude=latitude, longitude=longitude),
            date_range=DateRange(
                start_date=start_date.isoformat(),
                end_date=end_date.isoformat(),
            ),
            parameters_info=self._get_parameters_dict(),
            data_limitations=DATA_LIMITATIONS_NOTE,
            # Scientific integrity: False only on confirmed NASA POWER payload
            is_simulated=False,
        )

        return ClimateResponse(
            metadata=metadata,
            summary=summary,
            records=records,
        )

    def _compute_summary(
        self, records: List[DailyClimateRecord]
    ) -> ClimateSummary:
        """Compute statistical aggregates using Pandas with null safety."""
        total_days = len(records)
        if total_days == 0:
            return ClimateSummary(
                avg_temperature_c=None,
                min_temperature_c=None,
                max_temperature_c=None,
                total_precipitation_mm=None,
                avg_precipitation_daily_mm=None,
                avg_solar_radiation_mj_m2=None,
                avg_relative_humidity_pct=None,
                total_days=0,
                valid_data_days=0,
            )

        data = [
            {
                "t2m": r.temperature_mean_c,
                "t2m_max": r.temperature_max_c,
                "t2m_min": r.temperature_min_c,
                "precip": r.precipitation_mm,
                "solar": r.solar_radiation_mj_m2,
                "rh": r.relative_humidity_pct,
            }
            for r in records
        ]

        df = pd.DataFrame(data)

        # Count days with at least one non-null reading
        valid_days = int(df.notna().any(axis=1).sum())

        def _mean_val(series: pd.Series) -> Optional[float]:
            clean = series.dropna()
            return round(float(clean.mean()), 2) if not clean.empty else None

        def _sum_val(series: pd.Series) -> Optional[float]:
            clean = series.dropna()
            return round(float(clean.sum()), 2) if not clean.empty else None

        def _min_val(series: pd.Series) -> Optional[float]:
            clean = series.dropna()
            return round(float(clean.min()), 2) if not clean.empty else None

        def _max_val(series: pd.Series) -> Optional[float]:
            clean = series.dropna()
            return round(float(clean.max()), 2) if not clean.empty else None

        return ClimateSummary(
            avg_temperature_c=_mean_val(df["t2m"]),
            min_temperature_c=_min_val(df["t2m_min"]),
            max_temperature_c=_max_val(df["t2m_max"]),
            total_precipitation_mm=_sum_val(df["precip"]),
            avg_precipitation_daily_mm=_mean_val(df["precip"]),
            avg_solar_radiation_mj_m2=_mean_val(df["solar"]),
            avg_relative_humidity_pct=_mean_val(df["rh"]),
            total_days=total_days,
            valid_data_days=valid_days,
        )


nasa_power_service = NasaPowerService()
