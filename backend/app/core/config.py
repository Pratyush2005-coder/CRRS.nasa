"""Application configuration and scientific parameter metadata."""

from typing import Dict, List, Optional
from urllib.parse import urlsplit
from pydantic import field_validator, model_validator
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

    # Database Configuration
    DATABASE_URL: str = "sqlite:///./data/agroverse.db"

    # Allowed CORS Origins
    # Default development origins. Override via CORS_ORIGINS environment variable
    # with comma-separated values (e.g., "https://app.example.com,https://admin.example.com")
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ]

    # Database Connection Pool Settings
    # QueuePool settings (PostgreSQL) - ignored for SQLite
    DATABASE_POOL_SIZE: int = 5
    DATABASE_MAX_OVERFLOW: int = 10
    DATABASE_POOL_TIMEOUT: int = 30
    DATABASE_POOL_RECYCLE: int = 1800  # 30 minutes
    DATABASE_POOL_PRE_PING: bool = True

    # Connection timeout (driver-specific, passed via connect_args)
    # For PostgreSQL with psycopg2/psycopg/asyncpg this sets connect_timeout
    # For SQLite this is ignored
    DATABASE_CONNECT_TIMEOUT: int = 10

    # Echo SQL queries (debugging only - should be False in production)
    DATABASE_ECHO: bool = False

    # Database Initialization Retry Settings
    # Maximum number of initialization attempts on startup
    DATABASE_INIT_MAX_RETRIES: int = 3
    # Seconds to wait between retries (linear backoff: retry_backoff * attempt)
    DATABASE_INIT_RETRY_BACKOFF: float = 1.0

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def _parse_cors_origins(cls, v: str | List[str]) -> List[str]:
        """
        Parse CORS origins from comma-separated string or list.

        Accepts:
        - List[str]: used directly (e.g., from .env.example JSON format)
        - str: comma-separated origins (e.g., "https://a.com, https://b.com")

        Validates (strict):
        - Rejects empty or whitespace-only entries (both formats)
        - Rejects wildcard "*" (security risk with allow_credentials=True)
        - Uses urllib.parse.urlsplit for strict URL parsing
        - Scheme must be http or https
        - Hostname must exist and be valid
        - Rejects paths, query strings, fragments
        - Rejects embedded usernames/passwords
        - Rejects invalid ports (must be 1-65535 if specified)
        - Deduplicates origins preserving original order

        Production HTTP restriction is validated in _validate_cors_production_http model validator.
        """
        # If already a list (e.g., from JSON in .env.example), validate each entry
        if isinstance(v, list):
            # Reject empty/whitespace-only entries
            for entry in v:
                if not entry or not entry.strip():
                    raise ValueError("CORS_ORIGINS JSON list contains empty or whitespace-only entry")
            origins = [origin.strip() for origin in v]
        else:
            # Parse comma-separated string from environment variable
            # Reject empty/whitespace-only entries
            parts = v.split(",")
            if any(not part.strip() for part in parts):
                raise ValueError("CORS_ORIGINS comma-separated string contains empty entry")
            origins = [origin.strip() for origin in parts]

        # Validate each origin
        validated = []
        seen = set()
        for origin in origins:
            # Reject wildcard when credentials are enabled
            if origin == "*":
                raise ValueError(
                    "CORS wildcard origin '*' is not allowed with allow_credentials=True. "
                    "Specify explicit origins instead."
                )

            # Strict URL parsing using standard library
            try:
                parsed = urlsplit(origin)
            except Exception as e:
                raise ValueError(f"Invalid CORS origin '{origin}': {e}")

            # Scheme must be http or https
            if parsed.scheme not in ("http", "https"):
                raise ValueError(
                    f"Invalid CORS origin '{origin}': scheme must be http or https"
                )

            # Hostname must exist
            if not parsed.hostname:
                raise ValueError(
                    f"Invalid CORS origin '{origin}': missing hostname"
                )

            # Reject paths (any non-empty path)
            if parsed.path and parsed.path != "/":
                raise ValueError(
                    f"Invalid CORS origin '{origin}': paths not allowed (got '{parsed.path}')"
                )

            # Reject query strings
            if parsed.query:
                raise ValueError(
                    f"Invalid CORS origin '{origin}': query strings not allowed"
                )

            # Reject fragments
            if parsed.fragment:
                raise ValueError(
                    f"Invalid CORS origin '{origin}': fragments not allowed"
                )

            # Reject embedded username/password
            if parsed.username or parsed.password:
                raise ValueError(
                    f"Invalid CORS origin '{origin}': embedded credentials not allowed"
                )

            # Validate port if specified
            if parsed.port is not None:
                # urlsplit returns int for valid ports, but may raise ValueError for invalid
                try:
                    port = parsed.port
                except ValueError:
                    raise ValueError(
                        f"Invalid CORS origin '{origin}': invalid port number"
                    )
                if not (1 <= port <= 65535):
                    raise ValueError(
                        f"Invalid CORS origin '{origin}': port must be 1-65535 (got {port})"
                    )

            # Deduplicate while preserving order (case-sensitive comparison for origins)
            if origin not in seen:
                seen.add(origin)
                validated.append(origin)

        if not validated:
            raise ValueError(
                "CORS_ORIGINS cannot be empty. At least one valid origin is required."
            )

        return validated

    @field_validator("ENVIRONMENT")
    @classmethod
    def _validate_environment(cls, v: str) -> str:
        """Normalize environment value."""
        return v.lower()

    @model_validator(mode="after")
    def _validate_cors_production_http(self) -> "Settings":
        """
        Validate production HTTP restriction after all fields are parsed.

        In production (ENVIRONMENT=production), reject http:// origins for non-localhost hosts.
        """
        if self.ENVIRONMENT == "production":
            for origin in self.CORS_ORIGINS:
                parsed = urlsplit(origin)
                is_localhost = parsed.hostname in ("localhost", "127.0.0.1", "::1")
                if parsed.scheme == "http" and not is_localhost:
                    raise ValueError(
                        f"Invalid CORS origin '{origin}': HTTP not allowed in production "
                        f"for non-localhost hosts. Use HTTPS."
                    )
        return self

    # Authentication Configuration
    # SECURITY: SECRET_KEY must be set via environment variable in production.
    # No default provided to fail safely if missing in production.
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    PASSWORD_RESET_TOKEN_EXPIRE_MINUTES: int = 15

    # Auth Artifact Cleanup Configuration
    # Retention period for revoked refresh tokens (days) - tokens revoked longer than this are deleted
    REVOKED_REFRESH_TOKEN_RETENTION_DAYS: int = 30
    # Retention period for used password reset tokens (days) - tokens used longer than this are deleted
    USED_RESET_TOKEN_RETENTION_DAYS: int = 30
    # Retention period for expired (unused) password reset tokens (days) - tokens expired longer than this are deleted
    EXPIRED_RESET_TOKEN_RETENTION_DAYS: int = 7
    # Retention period for expired (unrevoked) refresh tokens (days) - tokens expired longer than this are deleted
    EXPIRED_UNREVOKED_REFRESH_TOKEN_RETENTION_DAYS: int = 7
    # Maximum number of records to delete per batch during cleanup operations
    AUTH_CLEANUP_BATCH_SIZE: int = 500

    # Account Lockout Configuration
    # Maximum failed login attempts allowed per email+IP within the window
    LOGIN_ATTEMPT_MAX_ATTEMPTS: int = 5
    # Sliding time window in minutes for counting failed attempts
    LOGIN_ATTEMPT_WINDOW_MINUTES: int = 15
    # Cooldown period in minutes after max attempts reached (lockout duration)
    LOGIN_ATTEMPT_COOLDOWN_MINUTES: int = 15

    # Development/Debug Configuration
    # SECURITY: Must be False in production. Exposes sensitive tokens in logs for debugging only.
    LOG_PASSWORD_RESET_TOKENS: bool = False

    # Rate Limiting Configuration
    # Set to True ONLY when running behind a trusted reverse proxy (nginx, ALB, Cloudflare, etc.)
    # that properly sets X-Forwarded-For header. Never enable this when directly exposed.
    BEHIND_TRUSTED_PROXY: bool = False

    # Redis Configuration for Distributed Rate Limiting
    # Redis connection URL (e.g., redis://localhost:6379/0, rediss://user:pass@host:6379/0)
    REDIS_URL: str = "redis://localhost:6379/0"
    # Enable Redis-backed distributed rate limiting. When false, uses in-memory fallback.
    REDIS_RATE_LIMITING_ENABLED: bool = False
    # Redis connection timeout in seconds
    REDIS_CONNECTION_TIMEOUT: float = 5.0
    # Redis socket timeout in seconds
    REDIS_SOCKET_TIMEOUT: float = 5.0
    # Redis socket keepalive in seconds (0 = disabled)
    REDIS_SOCKET_KEEPALIVE: int = 0
    # Maximum number of Redis connection retries
    REDIS_MAX_RETRIES: int = 3
    # Redis retry backoff factor (exponential backoff: base * 2^attempt)
    REDIS_RETRY_BACKOFF: float = 0.1
    # Redis health check interval in seconds (0 = disabled)
    REDIS_HEALTH_CHECK_INTERVAL: int = 30

    # Logging Configuration
    # When True, include client IP addresses in request logs.
    # Default: False (disabled for privacy). Enable only when explicitly needed for debugging/security.
    LOG_CLIENT_IP: bool = False

    @field_validator("ACCESS_TOKEN_EXPIRE_MINUTES")
    @classmethod
    def _validate_access_token_expire(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("ACCESS_TOKEN_EXPIRE_MINUTES must be positive")
        return v

    @field_validator("REFRESH_TOKEN_EXPIRE_DAYS")
    @classmethod
    def _validate_refresh_token_expire(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("REFRESH_TOKEN_EXPIRE_DAYS must be positive")
        return v

    @field_validator("PASSWORD_RESET_TOKEN_EXPIRE_MINUTES")
    @classmethod
    def _validate_password_reset_token_expire(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("PASSWORD_RESET_TOKEN_EXPIRE_MINUTES must be positive")
        if v > 60:
            raise ValueError("PASSWORD_RESET_TOKEN_EXPIRE_MINUTES should not exceed 60 minutes")
        return v

    # Auth Artifact Cleanup validators
    @field_validator("REVOKED_REFRESH_TOKEN_RETENTION_DAYS")
    @classmethod
    def _validate_revoked_refresh_token_retention(cls, v: int) -> int:
        if v < 0:
            raise ValueError("REVOKED_REFRESH_TOKEN_RETENTION_DAYS must be non-negative")
        return v

    @field_validator("USED_RESET_TOKEN_RETENTION_DAYS")
    @classmethod
    def _validate_used_reset_token_retention(cls, v: int) -> int:
        if v < 0:
            raise ValueError("USED_RESET_TOKEN_RETENTION_DAYS must be non-negative")
        return v

    @field_validator("EXPIRED_RESET_TOKEN_RETENTION_DAYS")
    @classmethod
    def _validate_expired_reset_token_retention(cls, v: int) -> int:
        if v < 0:
            raise ValueError("EXPIRED_RESET_TOKEN_RETENTION_DAYS must be non-negative")
        return v

    @field_validator("EXPIRED_UNREVOKED_REFRESH_TOKEN_RETENTION_DAYS")
    @classmethod
    def _validate_expired_unrevoked_refresh_token_retention(cls, v: int) -> int:
        if v < 0:
            raise ValueError("EXPIRED_UNREVOKED_REFRESH_TOKEN_RETENTION_DAYS must be non-negative")
        return v

    @field_validator("AUTH_CLEANUP_BATCH_SIZE")
    @classmethod
    def _validate_auth_cleanup_batch_size(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("AUTH_CLEANUP_BATCH_SIZE must be positive")
        return v

    # Account Lockout validators
    @field_validator("LOGIN_ATTEMPT_MAX_ATTEMPTS")
    @classmethod
    def _validate_login_attempt_max_attempts(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("LOGIN_ATTEMPT_MAX_ATTEMPTS must be positive")
        return v

    @field_validator("LOGIN_ATTEMPT_WINDOW_MINUTES")
    @classmethod
    def _validate_login_attempt_window_minutes(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("LOGIN_ATTEMPT_WINDOW_MINUTES must be positive")
        return v

    @field_validator("LOGIN_ATTEMPT_COOLDOWN_MINUTES")
    @classmethod
    def _validate_login_attempt_cooldown_minutes(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("LOGIN_ATTEMPT_COOLDOWN_MINUTES must be positive")
        return v

    # Database pool validators
    @field_validator("DATABASE_POOL_SIZE")
    @classmethod
    def _validate_pool_size(cls, v: int) -> int:
        if v < 0:
            raise ValueError("DATABASE_POOL_SIZE must be non-negative")
        return v

    @field_validator("DATABASE_MAX_OVERFLOW")
    @classmethod
    def _validate_max_overflow(cls, v: int) -> int:
        if v < 0:
            raise ValueError("DATABASE_MAX_OVERFLOW must be non-negative")
        return v

    @field_validator("DATABASE_POOL_TIMEOUT")
    @classmethod
    def _validate_pool_timeout(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("DATABASE_POOL_TIMEOUT must be positive")
        return v

    @field_validator("DATABASE_POOL_RECYCLE")
    @classmethod
    def _validate_pool_recycle(cls, v: int) -> int:
        if v < 0:
            raise ValueError("DATABASE_POOL_RECYCLE must be non-negative")
        return v

    @field_validator("DATABASE_CONNECT_TIMEOUT")
    @classmethod
    def _validate_connect_timeout(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("DATABASE_CONNECT_TIMEOUT must be positive")
        return v

    @field_validator("DATABASE_INIT_MAX_RETRIES")
    @classmethod
    def _validate_init_max_retries(cls, v: int) -> int:
        if v < 0:
            raise ValueError("DATABASE_INIT_MAX_RETRIES must be non-negative")
        return v

    @field_validator("DATABASE_INIT_RETRY_BACKOFF")
    @classmethod
    def _validate_init_retry_backoff(cls, v: float) -> float:
        if v < 0:
            raise ValueError("DATABASE_INIT_RETRY_BACKOFF must be non-negative")
        return v

    # Redis validators
    @field_validator("REDIS_URL")
    @classmethod
    def _validate_redis_url(cls, v: str) -> str:
        """Validate Redis URL format."""
        if not v:
            raise ValueError("REDIS_URL cannot be empty")
        # Accept redis://, rediss:// (TLS), and redis+unix:// schemes
        valid_schemes = ("redis://", "rediss://", "redis+unix://")
        if not any(v.startswith(scheme) for scheme in valid_schemes):
            raise ValueError(
                f"REDIS_URL must start with one of: {', '.join(valid_schemes)}"
            )
        return v

    @field_validator("REDIS_CONNECTION_TIMEOUT")
    @classmethod
    def _validate_redis_connection_timeout(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("REDIS_CONNECTION_TIMEOUT must be positive")
        return v

    @field_validator("REDIS_SOCKET_TIMEOUT")
    @classmethod
    def _validate_redis_socket_timeout(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("REDIS_SOCKET_TIMEOUT must be positive")
        return v

    @field_validator("REDIS_SOCKET_KEEPALIVE")
    @classmethod
    def _validate_redis_socket_keepalive(cls, v: int) -> int:
        if v < 0:
            raise ValueError("REDIS_SOCKET_KEEPALIVE must be non-negative")
        return v

    @field_validator("REDIS_MAX_RETRIES")
    @classmethod
    def _validate_redis_max_retries(cls, v: int) -> int:
        if v < 0:
            raise ValueError("REDIS_MAX_RETRIES must be non-negative")
        return v

    @field_validator("REDIS_RETRY_BACKOFF")
    @classmethod
    def _validate_redis_retry_backoff(cls, v: float) -> float:
        if v < 0:
            raise ValueError("REDIS_RETRY_BACKOFF must be non-negative")
        return v

    @field_validator("REDIS_HEALTH_CHECK_INTERVAL")
    @classmethod
    def _validate_redis_health_check_interval(cls, v: int) -> int:
        if v < 0:
            raise ValueError("REDIS_HEALTH_CHECK_INTERVAL must be non-negative")
        return v

    # Database driver validation
    @field_validator("DATABASE_URL")
    @classmethod
    def _validate_database_driver(cls, v: str) -> str:
        """
        Validate database URL uses a supported synchronous driver.

        Supported schemes:
        - sqlite:// (SQLite)
        - postgresql:// (uses psycopg2 or psycopg v3)
        - postgresql+psycopg2:// (explicit psycopg2)
        - postgresql+psycopg:// (explicit psycopg v3)

        Rejected:
        - postgresql+asyncpg:// (async driver, requires create_async_engine)
        - postgresql+pg8000:// (not verified for this application)
        """
        if v.startswith("postgresql+asyncpg://"):
            raise ValueError(
                "DATABASE_URL uses 'postgresql+asyncpg://' which is an async driver. "
                "This application uses synchronous SQLAlchemy create_engine(). "
                "Use 'postgresql://' (psycopg2/psycopg) or 'postgresql+psycopg2://' "
                "or 'postgresql+psycopg://' for synchronous PostgreSQL connections."
            )
        if v.startswith("postgresql+pg8000://"):
            raise ValueError(
                "DATABASE_URL uses 'postgresql+pg8000://' which is not a verified driver. "
                "Use 'postgresql://' (psycopg2/psycopg) or 'postgresql+psycopg2://' "
                "or 'postgresql+psycopg://' for synchronous PostgreSQL connections."
            )
        return v

    # Production guard for DATABASE_ECHO
    @model_validator(mode="after")
    def _validate_database_echo_production(self) -> "Settings":
        """
        Prevent DATABASE_ECHO=True in production to avoid SQL query logging.
        """
        if self.ENVIRONMENT == "production" and self.DATABASE_ECHO:
            raise ValueError(
                "DATABASE_ECHO cannot be True in production environment. "
                "Set DATABASE_ECHO=false or use ENVIRONMENT=development."
            )
        return self

    # Production guard for LOG_PASSWORD_RESET_TOKENS
    @model_validator(mode="after")
    def _validate_log_password_reset_tokens_production(self) -> "Settings":
        """
        Prevent LOG_PASSWORD_RESET_TOKENS=True in production to avoid token exposure in logs.
        """
        if self.ENVIRONMENT == "production" and self.LOG_PASSWORD_RESET_TOKENS:
            raise ValueError(
                "LOG_PASSWORD_RESET_TOKENS cannot be True in production environment. "
                "Set LOG_PASSWORD_RESET_TOKENS=false or use ENVIRONMENT=development."
            )
        return self

    # Production guard for automatic schema creation
    @model_validator(mode="after")
    def _validate_database_auto_create_production(self) -> "Settings":
        """
        In production, automatic Base.metadata.create_all() is disabled.
        Production schema must be managed by Alembic migrations.
        Development/test environments allow automatic table creation.
        """
        # This validator documents the behavior enforced in main.py lifespan
        # No setting is added - the behavior is controlled by ENVIRONMENT
        return self


settings = Settings()
