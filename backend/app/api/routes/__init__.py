"""API route endpoints."""

from fastapi import APIRouter
from app.api.routes.health import router as health_router
from app.api.routes.climate import router as climate_router
from app.api.routes.farms import router as farms_router
from app.api.routes.crops import router as crops_router
from app.api.routes.climate_analyzer import router as climate_analyzer_router
from app.api.routes.rotations import router as rotations_router
from app.api.routes.auth import router as auth_router

api_router = APIRouter()
api_router.include_router(health_router, prefix="", tags=["Health"])
api_router.include_router(climate_router, prefix="", tags=["Climate"])
api_router.include_router(climate_analyzer_router, prefix="", tags=["Climate Intelligence"])
api_router.include_router(farms_router, prefix="", tags=["Farms"])
api_router.include_router(crops_router, prefix="", tags=["Crops"])
api_router.include_router(rotations_router, prefix="", tags=["Rotations"])
api_router.include_router(auth_router, prefix="", tags=["Auth"])
