"""Health check schema."""

from datetime import datetime, timezone
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Health check response schema."""

    status: str = Field(..., description="Operational status of backend service")
    service: str = Field(..., description="Name of backend service")
    version: str = Field(..., description="Semantic version of backend API")
    environment: str = Field(..., description="Runtime environment")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Current server UTC timestamp",
    )
