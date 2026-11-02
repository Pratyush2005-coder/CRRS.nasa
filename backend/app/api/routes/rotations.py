"""Crop Rotation Recommendation API endpoints."""

from datetime import date, datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.rotation import (
    RotationRequest,
    FarmRotationRequest,
    RotationRecommendation,
    StrategyType,
    STRATEGY_TEMPLATES,
    VERIFIED_SEASON_MAP,
    UNRESOLVED_SEASON_MAP,
    BORO_IRRIGATION_FEASIBILITY,
    BORO_OCCUPIED_SLOTS,
)
from app.schemas.farm import FarmResponse
from app.services.rotation_engine import rotation_engine
from app.services.farm_service import farm_service

router = APIRouter()


# -------------------------------------------------------------------------
# Helper: Build default climate date range (last 3 full calendar years)
# -------------------------------------------------------------------------

def _get_default_climate_years() -> tuple[int, int]:
    """Return (start_year, end_year) for the last 3 full calendar years."""
    end_year = date.today().year - 1
    start_year = end_year - 2
    return start_year, end_year


# -------------------------------------------------------------------------
# POST /api/rotations — Coordinate-based rotation recommendation
# -------------------------------------------------------------------------

@router.post(
    "/rotations",
    response_model=RotationRecommendation,
    status_code=status.HTTP_200_OK,
    summary="Generate Crop Rotation Recommendation (Coordinates)",
    description=(
        "Generate evidence-based multi-year crop rotation recommendations for given coordinates. "
        "Uses NASA POWER climate intelligence, verified crop catalog data, and established "
        "agronomic heuristics. Returns 4 distinct strategy variants with transparent evidence reporting."
    ),
)
async def generate_rotation(
    request: RotationRequest,
) -> RotationRecommendation:
    """Generate rotation recommendation from coordinates and optional farm context."""
    # Validate user-provided climate years BEFORE applying defaults
    today = date.today()
    if request.climate_start_year is not None:
        if request.climate_start_year < 1983 or request.climate_start_year > today.year - 1:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"climate_start_year must be between 1983 and {today.year - 1} (NASA POWER data availability).",
            )
    if request.climate_end_year is not None:
        if request.climate_end_year < 1983 or request.climate_end_year > today.year - 1:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"climate_end_year must be between 1983 and {today.year - 1} (NASA POWER data availability).",
            )
    if (request.climate_start_year is not None and request.climate_end_year is not None
            and request.climate_start_year > request.climate_end_year):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="climate_start_year cannot be after climate_end_year.",
        )

    # Determine climate years (apply defaults only where None)
    start_year = request.climate_start_year
    end_year = request.climate_end_year
    if start_year is None or end_year is None:
        default_start, default_end = _get_default_climate_years()
        if start_year is None:
            start_year = default_start
        if end_year is None:
            end_year = default_end

    try:
        recommendation = await rotation_engine.generate_recommendation(request)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Upstream service error: {type(e).__name__}",
        )

    return recommendation


# -------------------------------------------------------------------------
# POST /api/farms/{farm_id}/rotations — Farm-profile-based rotation
# -------------------------------------------------------------------------

@router.post(
    "/farms/{farm_id}/rotations",
    response_model=RotationRecommendation,
    status_code=status.HTTP_200_OK,
    summary="Generate Crop Rotation Recommendation (Farm Profile)",
    description=(
        "Generate rotation recommendations using an existing farm profile's coordinates, "
        "soil characteristics, irrigation type, and crop history. "
        "Farm profile fields override request body where applicable."
    ),
)
async def generate_farm_rotation(
    farm_id: str,
    request: FarmRotationRequest,
    db: Session = Depends(get_db),
) -> RotationRecommendation:
    """Generate rotation recommendation from existing farm profile."""
    # Fetch farm profile
    farm = farm_service.get_farm_by_id(db=db, farm_id=farm_id)
    if not farm:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Farm profile with ID '{farm_id}' was not found.",
        )

    # Verify farm_id matches
    if request.farm_id != farm_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="farm_id in request body must match path parameter.",
        )

    # Validate user-provided climate years BEFORE applying defaults
    today = date.today()
    if request.climate_start_year is not None:
        if request.climate_start_year < 1983 or request.climate_start_year > today.year - 1:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"climate_start_year must be between 1983 and {today.year - 1} (NASA POWER data availability).",
            )
    if request.climate_end_year is not None:
        if request.climate_end_year < 1983 or request.climate_end_year > today.year - 1:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"climate_end_year must be between 1983 and {today.year - 1} (NASA POWER data availability).",
            )
    if (request.climate_start_year is not None and request.climate_end_year is not None
            and request.climate_start_year > request.climate_end_year):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="climate_start_year cannot be after climate_end_year.",
        )

    # Determine climate years (apply defaults only where None)
    start_year = request.climate_start_year
    end_year = request.climate_end_year
    if start_year is None or end_year is None:
        default_start, default_end = _get_default_climate_years()
        if start_year is None:
            start_year = default_start
        if end_year is None:
            end_year = default_end

    # Generate climate report for farm coordinates
    start_date = date(start_year, 1, 1)
    end_date = date(end_year, 12, 31)

    try:
        from app.services.climate_analyzer import climate_analyzer_service
        climate_report = await climate_analyzer_service.generate_report(
            latitude=farm.latitude,
            longitude=farm.longitude,
            start_date=start_date,
            end_date=end_date,
        )

        # Build previous crops from farm history
        previous_crops = []
        if farm.previous_crops:
            previous_crops = [
                h.crop_name.lower().replace(" ", "_").replace("-", "_")
                for h in farm.previous_crops
            ]

        # Generate recommendation using farm profile
        recommendation = rotation_engine.generate_recommendation_from_farm(
            request=request,
            farm_profile=farm,
            climate_report=climate_report,
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Upstream service error: {type(e).__name__}",
        )

    return recommendation


# -------------------------------------------------------------------------
# GET /api/rotations/catalog — Rotation strategy catalog (transparency)
# -------------------------------------------------------------------------

@router.get(
    "/rotations/catalog",
    status_code=status.HTTP_200_OK,
    summary="Get Rotation Engine Catalog",
    description=(
        "Retrieve the rotation engine's strategy templates, verified season mappings, "
        "unresolved season mappings, Boro rice occupancy rules, and irrigation feasibility tables. "
        "Provides full transparency into the decision logic and evidence base."
    ),
)
def get_rotation_catalog() -> dict:
    """Return rotation engine configuration and strategy catalog for transparency."""
    return {
        "strategy_templates": {
            strategy_type.value: {
                "name": template["name"],
                "description": template["description"],
                "evidence_level": template["evidence_level"].value,
            }
            for strategy_type, template in STRATEGY_TEMPLATES.items()
        },
        "verified_season_map": {
            crop_id: [s.value for s in seasons]
            for crop_id, seasons in VERIFIED_SEASON_MAP.items()
        },
        "unresolved_season_map": {
            crop_id: [s.value for s in seasons]
            for crop_id, seasons in UNRESOLVED_SEASON_MAP.items()
        },
        "boro_occupied_slots": {
            slot.value: [s.value for s in occupied]
            for slot, occupied in BORO_OCCUPIED_SLOTS.items()
        },
        "boro_irrigation_feasibility": {
            irrigation_type.value: feasibility.value
            for irrigation_type, feasibility in BORO_IRRIGATION_FEASIBILITY.items()
        },
        "rule_weights": {
            rule.value: weight
            for rule, weight in rotation_engine.RULE_WEIGHTS.items()
        } if hasattr(rotation_engine, 'RULE_WEIGHTS') else {},
        "thermal_score_map": {
            compat.value: score
            for compat, score in rotation_engine.THERMAL_SCORE_MAP.items()
        } if hasattr(rotation_engine, 'THERMAL_SCORE_MAP') else {},
        "water_score_map": {
            compat.value: score
            for compat, score in rotation_engine.WATER_SCORE_MAP.items()
        } if hasattr(rotation_engine, 'WATER_SCORE_MAP') else {},
        "scientific_disclaimer": (
            "Rotation recommendations are based on verified crop catalog data, "
            "NASA climate intelligence, and established agronomic heuristics. "
            "Botanical family diversification, nitrogen role sequencing, and root "
            "depth alternation are heuristic principles; they do not guarantee "
            "pest, disease, or yield outcomes. Boro rice climate evaluation uses "
            "single-year proxy data. Multi-year climate normals, planting calendars, "
            "and relay planting (Utera) are not modeled. Consult local agricultural "
            "extension for field-specific decisions."
        ),
        "engine_version": "1.0.0",
    }