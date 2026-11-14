from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.security import HTTPBearer
from app.api.routes import api_router
from app.core.config import settings
from app.core.database import init_db
from app.core.logging_config import setup_logging
from app.core.rate_limiting import setup_rate_limiting, redis_lifespan
from app.core.request_logging import RequestLoggingMiddleware
from app.core.security_headers import SecurityHeadersMiddleware
from slowapi.middleware import SlowAPIMiddleware


# HTTP Bearer authentication scheme for OpenAPI documentation
# This enables the "Authorize" button in Swagger UI
# Using HTTPBearer with auto_error=False to document the scheme without enforcing it
bearer_scheme = HTTPBearer(auto_error=False)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan managing startup and shutdown tasks."""
    # Initialize structured logging first
    setup_logging()

    # Initialize database with configurable retry logic
    # PRODUCTION GUARD: In production, schema is managed by Alembic migrations.
    # Base.metadata.create_all() only runs in development/test environments.
    if settings.ENVIRONMENT != "production":
        init_db(
            max_retries=settings.DATABASE_INIT_MAX_RETRIES,
            retry_backoff=settings.DATABASE_INIT_RETRY_BACKOFF,
        )
    else:
        # Production: verify connectivity, fail fast if unavailable
        # Never call init_db() or Base.metadata.create_all() in production
        from app.core.database import check_database_connectivity
        if not check_database_connectivity():
            import logging
            logger = logging.getLogger(__name__)
            # Safe log message - no credentials, URLs, or SQL details
            logger.critical(
                "Database connectivity check failed on production startup. "
                "Production requires a healthy database connection at startup. "
                "Refusing to start."
            )
            raise RuntimeError(
                "Database unavailable - production startup aborted. "
                "Ensure the database is running and accessible."
            )

    # Setup rate limiting (includes Redis connection initialization)
    setup_rate_limiting(app)

    # Manage Redis lifecycle
    async with redis_lifespan(app):
        yield


def custom_openapi():
    """Custom OpenAPI schema with BearerAuth security scheme for Swagger UI."""
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title=settings.PROJECT_NAME,
        version=settings.VERSION,
        description=(
            "AGROVERSE AI — NASA Space Apps Challenge 2026. "
            "A NASA-data-powered Crop Rotation Decision Support Platform providing "
            "historical climate intelligence, soil moisture context, and crop suitability models."
        ),
        routes=app.routes,
        tags=[
            {"name": "Auth", "description": "User registration, login, and token management"},
            {"name": "Health", "description": "Service health and database connectivity checks"},
            {"name": "Climate", "description": "NASA POWER agro-climatology data endpoints"},
            {"name": "Climate Intelligence", "description": "NASA POWER-derived climate analysis and intelligence reports"},
            {"name": "Farms", "description": "Farm profile management (requires authentication)"},
            {"name": "Crops", "description": "Verified crop knowledge base catalog (public)"},
            {"name": "Rotations", "description": "Crop rotation recommendations (some endpoints require authentication)"},
        ],
    )
    # Add HTTPBearer security scheme (matches FastAPI's default security scheme name)
    if "components" not in openapi_schema:
        openapi_schema["components"] = {}
    openapi_schema["components"]["securitySchemes"] = {
        "HTTPBearer": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": "JWT access token obtained from /api/auth/login endpoint. "
                           "Include in Authorization header as: Authorization: Bearer <token>"
        }
    }
    app.openapi_schema = openapi_schema
    return app.openapi_schema


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
    swagger_ui_init_oauth={},
)

# Initialize rate limiter early so middleware can access it
from app.core.rate_limiting import get_limiter
app.state.limiter = get_limiter()

# Add SlowAPI middleware for rate limiting
app.add_middleware(SlowAPIMiddleware)

app.openapi = custom_openapi

# Request logging and correlation ID middleware - MUST be added early
# to capture all requests and make request_id available to downstream handlers
app.add_middleware(RequestLoggingMiddleware)

# Configure Cross-Origin Resource Sharing (CORS) for React frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security Headers Middleware - MUST be added LAST (outermost on response)
# so it wraps CORS responses including preflight
app.add_middleware(SecurityHeadersMiddleware)

# Mount API routers
app.include_router(api_router, prefix=settings.API_V1_STR)

# Apply BearerAuth security requirement to protected routes
# Public endpoints remain unsecured in documentation
# Protected endpoints are documented via their Depends(get_current_user) dependency
# FastAPI automatically infers security requirements from dependencies


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
