"""Health check endpoint."""

from datetime import datetime, timezone
from fastapi import APIRouter, Response
from app.core.config import settings
from app.core.database import check_database_connectivity
from app.schemas.health import HealthResponse

router = APIRouter()


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Backend Health Check",
    description="Check the operational status, version, and runtime environment of the AGROVERSE AI backend, including database connectivity.",
)
async def get_health(response: Response) -> HealthResponse:
    """Return operational health status with database connectivity check."""
    try:
        db_healthy = check_database_connectivity()
    except Exception:
        # Defense in depth: if check_database_connectivity somehow raises,
        # treat as unhealthy without crashing
        db_healthy = False

    if not db_healthy:
        response.status_code = 503
        return HealthResponse(
            status="unhealthy",
            service=settings.PROJECT_NAME,
            version=settings.VERSION,
            environment=settings.ENVIRONMENT,
            timestamp=datetime.now(timezone.utc),
        )

    return HealthResponse(
        status="healthy",
        service=settings.PROJECT_NAME,
        version=settings.VERSION,
        environment=settings.ENVIRONMENT,
        timestamp=datetime.now(timezone.utc),
    )
