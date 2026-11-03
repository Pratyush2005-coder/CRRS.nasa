"""Authentication API routes."""

from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.rate_limiting import register_rate_limit, login_rate_limit
from app.core.security import create_access_token, create_refresh_token
from app.schemas.user import UserCreate, UserLogin, TokenResponse, UserResponse
from app.services.user_service import user_service

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register New User",
    description=(
        "Create a new user account with email and password. "
        "Returns the created user profile (excluding sensitive fields)."
    ),
)
@register_rate_limit()
def register_user(
    request: Request,
    user_in: UserCreate,
    db: Session = Depends(get_db),
) -> UserResponse:
    """Register a new user.

    Args:
        user_in: User registration data (email and password).
        db: Database session dependency.

    Returns:
        Created user profile with UUID, role, and timestamps.

    Raises:
        HTTPException: 409 if email already registered,
                       422 if validation fails.
    """
    try:
        user = user_service.create_user(db=db, user_in=user_in)
        return user
    except ValueError as e:
        # Handle duplicate email and other validation errors
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        ) from e


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="User Login",
    description=(
        "Authenticate user with email and password. "
        "Returns access and refresh tokens on success."
    ),
)
@login_rate_limit()
def login_user(
    request: Request,
    login_in: UserLogin,
    db: Session = Depends(get_db),
) -> TokenResponse:
    """Authenticate a user and return tokens.

    Args:
        login_in: User login credentials (email and password).
        db: Database session dependency.

    Returns:
        TokenResponse containing access/refresh tokens and user profile.

    Raises:
        HTTPException: 401 if credentials are invalid or user is inactive,
                       422 if validation fails.
    """
    # Authenticate user
    user = user_service.authenticate_user(db=db, email=login_in.email, password=login_in.password)
    if not user:
        # Generic error message to prevent email enumeration
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    # Create tokens using configured expiry
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(subject=user.id, expires_delta=access_token_expires)
    refresh_token = create_refresh_token(subject=user.id)

    # Calculate expires_in from configured value
    expires_in = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60

    # Build user response
    user_response = UserResponse(
        id=user.id,
        email=user.email,
        role=user.role,
        is_active=user.is_active,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=expires_in,
        user=user_response,
    )