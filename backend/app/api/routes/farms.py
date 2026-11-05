"""Farm Profile API routes."""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.deps import get_current_user, require_admin
from app.models.user import User
from app.models.farm import Farm
from app.schemas.farm import (
    FarmCreate,
    FarmListResponse,
    FarmResponse,
    FarmUpdate,
    SoilType,
)
from app.services.farm_service import farm_service

router = APIRouter()


def _authorize_farm_access(
    farm: Farm,
    current_user: User,
    is_admin: bool,
) -> None:
    """
    Authorize farm access based on ownership and admin status.

    Args:
        farm: The farm to check access for.
        current_user: The authenticated user.
        is_admin: Whether the user has admin role.

    Raises:
        HTTPException: 404 if farm is not accessible (to avoid enumeration).
    """
    if is_admin:
        # Admins can access all farms, including legacy farms with NULL owner_id
        return

    # Normal users can only access farms they own
    if farm.owner_id is None:
        # Legacy farms with NULL owner_id are not accessible to normal users
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Farm profile with ID '{farm.id}' was not found.",
        )

    if farm.owner_id != current_user.id:
        # Users cannot access other users' farms
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Farm profile with ID '{farm.id}' was not found.",
        )


@router.post(
    "/farms",
    response_model=FarmResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Farm Profile",
    description=(
        "Register a new farm profile with geographic coordinates, soil characteristics, "
        "irrigation infrastructure, and historical crop sequence. "
        "The authenticated user becomes the farm owner."
    ),
)
def create_farm(
    farm_in: FarmCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FarmResponse:
    """Create a new farm profile owned by the authenticated user."""
    farm = farm_service.create_farm(db=db, farm_in=farm_in, owner_id=current_user.id)
    return farm


@router.get(
    "/farms",
    response_model=FarmListResponse,
    status_code=status.HTTP_200_OK,
    summary="List Farm Profiles",
    description="Retrieve paginated list of farm profiles owned by the authenticated user (or all farms for admins).",
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
    current_user: User = Depends(get_current_user),
) -> FarmListResponse:
    """List farm profiles with pagination and filters (owned by user, or all for admin)."""
    is_admin = current_user.role == "admin"
    items, total = farm_service.list_farms(
        db=db,
        skip=skip,
        limit=limit,
        search=search,
        soil_type=soil_type.value if soil_type else None,
        owner_id=None if is_admin else current_user.id,
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
    description="Retrieve a specific farm profile by its unique UUID (must be owned by user or user is admin).",
)
def get_farm(
    farm_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FarmResponse:
    """Retrieve an individual farm profile by ID with ownership authorization."""
    is_admin = current_user.role == "admin"
    farm = farm_service.get_farm_by_id(db=db, farm_id=farm_id)
    if not farm:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Farm profile with ID '{farm_id}' was not found.",
        )
    _authorize_farm_access(farm, current_user, is_admin)
    return farm


@router.put(
    "/farms/{farm_id}",
    response_model=FarmResponse,
    status_code=status.HTTP_200_OK,
    summary="Replace Farm Profile (Full Update)",
    description="Completely update and replace an existing farm profile's attributes (must be owned by user or user is admin).",
)
def replace_farm(
    farm_id: str,
    farm_in: FarmCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FarmResponse:
    """Full update (replacement) of an existing farm profile with ownership authorization."""
    is_admin = current_user.role == "admin"
    farm = farm_service.get_farm_by_id(db=db, farm_id=farm_id)
    if not farm:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Farm profile with ID '{farm_id}' was not found.",
        )
    _authorize_farm_access(farm, current_user, is_admin)
    return farm_service.replace_farm(db=db, db_farm=farm, farm_in=farm_in)


@router.patch(
    "/farms/{farm_id}",
    response_model=FarmResponse,
    status_code=status.HTTP_200_OK,
    summary="Update Farm Profile (Partial Update)",
    description="Selectively update specific attributes of an existing farm profile (must be owned by user or user is admin).",
)
def update_farm(
    farm_id: str,
    farm_update: FarmUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FarmResponse:
    """Partial update of an existing farm profile with ownership authorization."""
    is_admin = current_user.role == "admin"
    farm = farm_service.get_farm_by_id(db=db, farm_id=farm_id)
    if not farm:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Farm profile with ID '{farm_id}' was not found.",
        )
    _authorize_farm_access(farm, current_user, is_admin)
    return farm_service.update_farm(db=db, db_farm=farm, farm_update=farm_update)


@router.delete(
    "/farms/{farm_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Farm Profile",
    description="Permanently delete a farm profile by UUID (must be owned by user or user is admin).",
)
def delete_farm(
    farm_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    """Delete a farm profile by ID with ownership authorization."""
    is_admin = current_user.role == "admin"
    farm = farm_service.get_farm_by_id(db=db, farm_id=farm_id)
    if not farm:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Farm profile with ID '{farm_id}' was not found.",
        )
    _authorize_farm_access(farm, current_user, is_admin)
    farm_service.delete_farm(db=db, db_farm=farm)
