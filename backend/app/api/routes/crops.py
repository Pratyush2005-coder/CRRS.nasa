"""Crop Knowledge Base API endpoints."""

from typing import Optional
from fastapi import APIRouter, HTTPException, Query, status

from app.schemas.crop import (
    BotanicalFamily,
    Crop,
    CropCatalogResponse,
    NitrogenRole,
    WaterDemandClass,
)
from app.services.crop_catalog import crop_catalog_service

router = APIRouter()


@router.get(
    "/crops/catalog",
    response_model=CropCatalogResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Crop Knowledge Base Catalog",
    description=(
        "Retrieve the complete catalog of verified agronomic crop profiles calibrated "
        "for the West Bengal pilot region. Supports filtering by botanical family, "
        "growing season, nitrogen role, or water demand class. Data is corroborated from "
        "ICAR, BCKV, and FAO peer-reviewed standards."
    ),
)
def get_crop_catalog(
    family: Optional[BotanicalFamily] = Query(
        None,
        description="Filter by botanical taxonomy family (e.g., Poaceae, Fabaceae, Brassicaceae)",
    ),
    season: Optional[str] = Query(
        None,
        description="Filter by growing season (e.g., 'Aman', 'Rabi', 'Aus', 'Pre-Kharif')",
        examples=["Rabi"],
    ),
    nitrogen_role: Optional[NitrogenRole] = Query(
        None,
        description="Filter by nitrogen dynamic (e.g., 'nitrogen_fixer', 'heavy_feeder')",
    ),
    water_demand: Optional[WaterDemandClass] = Query(
        None,
        description="Filter by water demand tier ('low', 'moderate', 'high', 'very_high')",
    ),
) -> CropCatalogResponse:
    """Retrieve catalog crops with optional agronomic filters."""
    filtered = crop_catalog_service.filter_crops(
        family=family.value if family else None,
        season=season,
        nitrogen_role=nitrogen_role.value if nitrogen_role else None,
        water_demand=water_demand.value if water_demand else None,
    )

    return CropCatalogResponse(
        total=len(filtered),
        pilot_region="West Bengal, India",
        crops=filtered,
        data_provenance_note=crop_catalog_service.get_provenance_statement(),
    )


@router.get(
    "/crops/{crop_id}",
    response_model=Crop,
    status_code=status.HTTP_200_OK,
    summary="Get Crop Profile by ID",
    description=(
        "Fetch detailed agronomic profile, temperature/water bounds, soil preferences, "
        "GDD base temperature, nitrogen management properties, and institutional citations for an individual crop."
    ),
)
def get_crop_by_id(
    crop_id: str,
) -> Crop:
    """Retrieve an individual crop entity by its unique slug ID."""
    crop = crop_catalog_service.get_crop(crop_id)
    if not crop:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Crop with ID '{crop_id}' was not found in the catalog. Available crops include: rice, wheat, lentil, mustard, chickpea, green_gram, maize.",
        )
    return crop
