"""NASA Climate Intelligence API endpoints."""

from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.deps import get_current_user
from app.core.rate_limiting import climate_analysis_rate_limit
from app.models.user import User
from app.models.farm import Farm
from app.schemas.climate_analyzer import ClimateIntelligenceReport
from app.services.climate_analyzer import climate_analyzer_service
from app.services.farm_service import farm_service

router = APIRouter()


def _validate_date_bounds(start_date: date, end_date: date, max_days: int = 366) -> None:
    """Validate date ordering, future date protection, and range limits."""
    if start_date > end_date:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"start_date ({start_date}) cannot be after end_date ({end_date}).",
        )

    today = date.today()
    if start_date > today or end_date > today:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Requested dates cannot be in the future (today: {today}). NASA POWER provides historical observations.",
        )

    date_diff = (end_date - start_date).days
    if date_diff > max_days:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Requested range of {date_diff} days exceeds maximum allowed limit of {max_days} days per query.",
        )


@router.get(
    "/climate/analysis",
    response_model=ClimateIntelligenceReport,
    status_code=status.HTTP_200_OK,
    summary="Get NASA Climate Intelligence Report",
    description=(
        "Synthesize NASA POWER Earth observation reanalyses into actionable agro-climatic intelligence. "
        "Includes cumulative rainfall, dry/wet spell durations, seasonal distribution (Kharif/Rabi/Summer), "
        "heat-risk frequency, near-freezing hazard indicators, GDD accumulation for verified crops, "
        "data completeness evaluation, and crop suitability assessments."
    ),
)
@climate_analysis_rate_limit()
async def get_climate_analysis(
    request: Request,
    latitude: float = Query(
        ...,
        ge=-90.0,
        le=90.0,
        description="Latitude in decimal degrees (-90.0 to 90.0)",
        examples=[22.5726],
    ),
    longitude: float = Query(
        ...,
        ge=-180.0,
        le=180.0,
        description="Longitude in decimal degrees (-180.0 to 180.0)",
        examples=[88.3639],
    ),
    start_date: date = Query(
        ...,
        description="Start date for climate observations (YYYY-MM-DD)",
        examples=["2023-01-01"],
    ),
    end_date: date = Query(
        ...,
        description="End date for climate observations (YYYY-MM-DD)",
        examples=["2023-03-31"],
    ),
    crop_id: Optional[str] = Query(
        None,
        description="Optional crop ID to narrow GDD accumulation and suitability analysis (e.g., 'rice', 'wheat')",
        examples=["wheat"],
    ),
) -> ClimateIntelligenceReport:
    """Validate parameters and compute NASA climate intelligence report for coordinates."""
    _validate_date_bounds(start_date=start_date, end_date=end_date)

    return await climate_analyzer_service.generate_report(
        latitude=latitude,
        longitude=longitude,
        start_date=start_date,
        end_date=end_date,
        crop_id=crop_id,
    )


@router.get(
    "/climate/intelligence",
    response_model=ClimateIntelligenceReport,
    status_code=status.HTTP_200_OK,
    summary="Get NASA Climate Intelligence Report (Alias)",
    include_in_schema=False,
)
@climate_analysis_rate_limit()
async def get_climate_intelligence_alias(
    request: Request,
    latitude: float = Query(..., ge=-90.0, le=90.0),
    longitude: float = Query(..., ge=-180.0, le=180.0),
    start_date: date = Query(...),
    end_date: date = Query(...),
    crop_id: Optional[str] = Query(None),
) -> ClimateIntelligenceReport:
    """Alias for /climate/analysis."""
    return await get_climate_analysis(
        request=request,
        latitude=latitude,
        longitude=longitude,
        start_date=start_date,
        end_date=end_date,
        crop_id=crop_id,
    )


@router.get(
    "/farms/{farm_id}/climate-analysis",
    response_model=ClimateIntelligenceReport,
    status_code=status.HTTP_200_OK,
    summary="Get Farm-Specific Climate Intelligence Report",
    description=(
        "Retrieve NASA POWER climate intelligence directly for a registered farm's coordinates. "
        "Links farm profile information directly with satellite reanalyses. "
        "Requires farm ownership or admin access."
    ),
)
async def get_farm_climate_analysis(
    farm_id: str,
    start_date: date = Query(
        ...,
        description="Query start date (YYYY-MM-DD)",
        examples=["2023-01-01"],
    ),
    end_date: date = Query(
        ...,
        description="Query end date (YYYY-MM-DD)",
        examples=["2023-03-31"],
    ),
    crop_id: Optional[str] = Query(
        None,
        description="Optional crop ID (defaults to farm's current_crop if matching catalog ID)",
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ClimateIntelligenceReport:
    """Fetch farm coordinates and compute climate intelligence report with ownership authorization."""
    _validate_date_bounds(start_date=start_date, end_date=end_date)

    is_admin = current_user.role == "admin"
    farm = farm_service.get_farm_by_id(db=db, farm_id=farm_id)
    if not farm:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Farm profile with ID '{farm_id}' was not found.",
        )

    # Authorize farm access
    if not is_admin:
        if farm.owner_id is None or farm.owner_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Farm profile with ID '{farm_id}' was not found.",
            )

    # Determine crop filter: query param overrides, fallback to matching current_crop
    target_crop = crop_id
    if not target_crop and farm.current_crop:
        candidate_crop = farm.current_crop.strip().lower()
        if candidate_crop in ("rice", "wheat", "lentil", "mustard", "chickpea", "green_gram", "maize"):
            target_crop = candidate_crop

    return await climate_analyzer_service.generate_report(
        latitude=farm.latitude,
        longitude=farm.longitude,
        start_date=start_date,
        end_date=end_date,
        crop_id=target_crop,
    )
