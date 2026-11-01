"""Application configuration and scientific parameter metadata."""

from typing import Dict, List
from pydantic_settings import BaseSettings, SettingsConfigDict


class ParameterInfo:
    """Metadata specification for an individual NASA POWER parameter."""

    def __init__(
        self,
        name: str,
        units: str,
        source: str,
        spatial_resolution: str,
        description: str,
    ):
        self.name = name
        self.units = units
        self.source = source
        self.spatial_resolution = spatial_resolution
        self.description = description

    def to_dict(self) -> Dict[str, str]:
        return {
            "name": self.name,
            "units": self.units,
            "source": self.source,
            "spatial_resolution": self.spatial_resolution,
            "description": self.description,
        }


# Parameter-specific source and spatial resolution registry.
# Meteorological variables use GMAO MERRA-2 (0.5° x 0.625°).
# Solar radiation parameters use CERES SYN1deg / FLASHFlux / SRB (1.0° x 1.0°).
PARAMETER_REGISTRY: Dict[str, Dict[str, str]] = {
    "T2M": {
        "name": "Temperature at 2 Meters",
        "units": "°C",
        "source": "NASA GMAO MERRA-2 Assimilation Model",
        "spatial_resolution": "0.5° latitude x 0.625° longitude (~50 km x ~60 km)",
        "description": "Daily mean air temperature at 2 meters above ground level.",
    },
    "T2M_MAX": {
        "name": "Maximum Temperature at 2 Meters",
        "units": "°C",
        "source": "NASA GMAO MERRA-2 Assimilation Model",
        "spatial_resolution": "0.5° latitude x 0.625° longitude (~50 km x ~60 km)",
        "description": "Daily maximum air temperature at 2 meters above ground level.",
    },
    "T2M_MIN": {
        "name": "Minimum Temperature at 2 Meters",
        "units": "°C",
        "source": "NASA GMAO MERRA-2 Assimilation Model",
        "spatial_resolution": "0.5° latitude x 0.625° longitude (~50 km x ~60 km)",
        "description": "Daily minimum air temperature at 2 meters above ground level.",
    },
    "PRECTOTCORR": {
        "name": "Precipitation Corrected",
        "units": "mm/day",
        "source": "NASA GMAO MERRA-2 Assimilation Model",
        "spatial_resolution": "0.5° latitude x 0.625° longitude (~50 km x ~60 km)",
        "description": "Corrected total precipitation rate over the day.",
    },
    "ALLSKY_SFC_SW_DWN": {
        "name": "All Sky Surface Shortwave Downward Irradiance",
        "units": "MJ/m²/day",
        "source": "NASA CERES SYN1deg / FLASHFlux / SRB Satellite Observations",
        "spatial_resolution": "1.0° latitude x 1.0° longitude (~110 km x ~110 km)",
        "description": "Total solar irradiance incident on a horizontal surface at the Earth's surface.",
    },
    "RH2M": {
        "name": "Relative Humidity at 2 Meters",
        "units": "%",
        "source": "NASA GMAO MERRA-2 Assimilation Model",
        "spatial_resolution": "0.5° latitude x 0.625° longitude (~50 km x ~60 km)",
        "description": "Daily mean relative humidity at 2 meters above ground level.",
    },
}

DATA_LIMITATIONS_NOTE = (
    "NASA POWER data is based on global satellite observations and regional numerical "
    "reanalyses (GMAO MERRA-2 and CERES). Spatial resolutions range from 0.5° x 0.625° "
    "(meteorology) to 1.0° x 1.0° (solar radiation). These observations reflect regional "
    "averages rather than in-situ sensor measurements, and do not capture hyper-local "
    "micro-climates, topological frost pockets, or farm-specific soil variability. "
    "These values serve as regional decision-support estimates and do not replace "
    "localized agricultural expertise or in-field ground sensors."
)


class Settings(BaseSettings):
    """Application settings with environment variable support."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    PROJECT_NAME: str = "AGROVERSE AI Backend"
    VERSION: str = "0.1.0"
    API_V1_STR: str = "/api"
    ENVIRONMENT: str = "development"

    # NASA POWER Configuration
    NASA_POWER_BASE_URL: str = (
        "https://power.larc.nasa.gov/api/temporal/daily/point"
    )
    NASA_POWER_TIMEOUT_SECONDS: float = 30.0
    NASA_POWER_COMMUNITY: str = "AG"

    # Allowed CORS Origins
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ]


settings = Settings()
