from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import api_router
from app.core.config import settings
from app.core.database import init_db
from app.core.rate_limiting import setup_rate_limiting


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan managing startup and shutdown tasks."""
    init_db()
    yield


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description=(
        "AGROVERSE AI — NASA Space Apps Challenge 2026. "
        "A NASA-data-powered Crop Rotation Decision Support Platform providing "
        "historical climate intelligence, soil moisture context, and crop suitability models."
    ),
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan,
)

# Setup rate limiting
setup_rate_limiting(app)

# Configure Cross-Origin Resource Sharing (CORS) for React frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API routers
app.include_router(api_router, prefix=settings.API_V1_STR)


@app.get("/", tags=["Root"])
async def root():
    """Root redirect / information endpoint."""
    return {
        "project": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "docs": "/docs",
        "api_health": f"{settings.API_V1_STR}/health",
        "climate_endpoint": f"{settings.API_V1_STR}/climate",
        "climate_analysis_endpoint": f"{settings.API_V1_STR}/climate/analysis",
        "farms_endpoint": f"{settings.API_V1_STR}/farms",
        "crops_endpoint": f"{settings.API_V1_STR}/crops/catalog",
    }
