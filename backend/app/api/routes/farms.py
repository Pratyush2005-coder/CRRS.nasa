"""Farm Profile API routes."""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.farm import (
    FarmCreate,
    FarmListResponse,
    FarmResponse,
    FarmUpdate,
    SoilType,
)
from app.services.farm_service import farm_service

router = APIRouter()


@router.post(
    "/farms",
    response_model=FarmResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Farm Profile",
    description=(
        "Register a new farm profile with geographic coordinates, soil characteristics, "
        "irrigation infrastructure, and historical crop sequence."
    ),
)
def create_farm(
    farm_in: FarmCreate,
    db: Session = Depends(get_db),
) -> FarmResponse:
    """Create a new farm profile."""
    return farm_service.create_farm(db=db, farm_in=farm_in)


@router.get(
    "/farms",
    response_model=FarmListResponse,
    status_code=status.HTTP_200_OK,
    summary="List Farm Profiles",
    description="Retrieve paginated list of registered farm profiles with optional search and soil filtering.",
)
def list_farms(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(20, ge=1, le=100, description="Maximum number of records to return"),
    search: Optional[str] = Query(
        None,
        description="Filter by name, farmer name, region, or country",
    ),
    soil_type: Optional[SoilType] = Query(
        None,
        description="Filter by primary soil type",
    ),
    db: Session = Depends(get_db),
) -> FarmListResponse:
    """List farm profiles with pagination and filters."""
    items, total = farm_service.list_farms(
        db=db,
        skip=skip,
        limit=limit,
        search=search,
        soil_type=soil_type.value if soil_type else None,
    )
    return FarmListResponse(
        total=total,
        items=items,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/farms/{farm_id}",
    response_model=FarmResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Farm Profile",
    description="Retrieve a specific farm profile by its unique UUID.",
)
def get_farm(
    farm_id: str,
    db: Session = Depends(get_db),
) -> FarmResponse:
    """Retrieve an individual farm profile by ID."""
    farm = farm_service.get_farm_by_id(db=db, farm_id=farm_id)
    if not farm:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Farm profile with ID '{farm_id}' was not found.",
        )
    return farm


@router.put(
    "/farms/{farm_id}",
    response_model=FarmResponse,
    status_code=status.HTTP_200_OK,
    summary="Replace Farm Profile (Full Update)",
    description="Completely update and replace an existing farm profile's attributes.",
)
def replace_farm(
    farm_id: str,
    farm_in: FarmCreate,
    db: Session = Depends(get_db),
) -> FarmResponse:
    """Full update (replacement) of an existing farm profile."""
    farm = farm_service.get_farm_by_id(db=db, farm_id=farm_id)
    if not farm:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Farm profile with ID '{farm_id}' was not found.",
        )
    return farm_service.replace_farm(db=db, db_farm=farm, farm_in=farm_in)


@router.patch(
    "/farms/{farm_id}",
    response_model=FarmResponse,
    status_code=status.HTTP_200_OK,
    summary="Update Farm Profile (Partial Update)",
    description="Selectively update specific attributes of an existing farm profile.",
)
def update_farm(
    farm_id: str,
    farm_update: FarmUpdate,
    db: Session = Depends(get_db),
) -> FarmResponse:
    """Partial update of an existing farm profile."""
    farm = farm_service.get_farm_by_id(db=db, farm_id=farm_id)
    if not farm:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Farm profile with ID '{farm_id}' was not found.",
        )
    return farm_service.update_farm(db=db, db_farm=farm, farm_update=farm_update)


@router.delete(
    "/farms/{farm_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Farm Profile",
    description="Permanently delete a farm profile by UUID.",
)
def delete_farm(
    farm_id: str,
    db: Session = Depends(get_db),
) -> None:
    """Delete a farm profile by ID."""
    farm = farm_service.get_farm_by_id(db=db, farm_id=farm_id)
    if not farm:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Farm profile with ID '{farm_id}' was not found.",
        )
    farm_service.delete_farm(db=db, db_farm=farm)
