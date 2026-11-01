"""Climate data endpoint querying NASA POWER API."""

from datetime import date
from fastapi import APIRouter, HTTPException, Query, status
from app.schemas.climate import ClimateResponse
from app.services.nasa_power import nasa_power_service

router = APIRouter()


@router.get(
    "/climate",
    response_model=ClimateResponse,
    summary="Get NASA Agro-Climatology Data",
    description=(
        "Fetch historical daily agro-climatological observations (temperature, precipitation, "
        "solar radiation, and humidity) from NASA POWER for specified coordinates and date range. "
        "Includes comprehensive parameter provenance, distinct spatial resolutions per parameter, "
        "and data limitations."
    ),
)
async def get_climate_data(
    latitude: float = Query(
        ...,
        ge=-90.0,
        le=90.0,
        description="Latitude in decimal degrees (-90.0 to 90.0)",
        examples=[28.6139],
    ),
    longitude: float = Query(
        ...,
        ge=-180.0,
        le=180.0,
        description="Longitude in decimal degrees (-180.0 to 180.0)",
        examples=[77.2090],
    ),
    start_date: date = Query(
        ...,
        description="Start date for climate observations (YYYY-MM-DD)",
        examples=["2023-01-01"],
    ),
    end_date: date = Query(
        ...,
        description="End date for climate observations (YYYY-MM-DD)",
        examples=["2023-01-10"],
    ),
) -> ClimateResponse:
    """Validate query parameters and retrieve NASA POWER agro-climatology data."""
    # 1. Logical date order validation
    if start_date > end_date:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"start_date ({start_date}) cannot be after end_date ({end_date}).",
        )

    # 2. Future date check
    today = date.today()
    if start_date > today or end_date > today:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Requested dates cannot be in the future (today: {today}). NASA POWER provides historical observations.",
        )

    # 3. Maximum range limit to prevent excessive query load and upstream timeouts (e.g. 366 days max per query)
    date_diff = (end_date - start_date).days
    if date_diff > 366:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Requested range of {date_diff} days exceeds maximum allowed limit of 366 days per query.",
        )

    # Fetch and parse from NASA POWER service
    return await nasa_power_service.fetch_climate_data(
        latitude=latitude,
        longitude=longitude,
        start_date=start_date,
        end_date=end_date,
    )
