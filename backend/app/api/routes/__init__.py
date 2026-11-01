"""API route endpoints."""

from fastapi import APIRouter
from app.api.routes.health import router as health_router
from app.api.routes.climate import router as climate_router

api_router = APIRouter()
api_router.include_router(health_router, prefix="", tags=["Health"])
api_router.include_router(climate_router, prefix="", tags=["Climate"])
