"""Authentication API routes."""

import logging
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field, EmailStr
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.rate_limiting import (
    register_rate_limit,
    login_rate_limit,
    forgot_password_rate_limit,
    reset_password_rate_limit,
)
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    InvalidTokenError,
    TokenExpiredError,
    InvalidTokenTypeError,
)
from app.schemas.user import UserCreate, UserLogin, TokenResponse, UserResponse, SessionListResponse, SessionInfo
from app.services.user_service import user_service
from app.api.deps import get_current_user
from app.models.user import User

logger = logging.getLogger(__name__)


class RefreshTokenRequest(BaseModel):
    """Schema for refresh token request."""

    refresh_token: str = Field(..., description="JWT refresh token")


class RefreshTokenResponse(BaseModel):
    """Schema for successful token refresh response."""

    access_token: str = Field(..., description="New JWT access token")
    refresh_token: str = Field(..., description="New JWT refresh token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(..., description="Access token lifetime in seconds")


class ForgotPasswordRequest(BaseModel):
    """Schema for forgot password request."""

    email: EmailStr = Field(..., description="User email address")


class ForgotPasswordResponse(BaseModel):
    """Schema for forgot password response (generic, no token exposure)."""

    detail: str = Field(
        default="If the email exists, a password reset link has been sent.",
        description="Generic response to prevent email enumeration"
    )


class ResetPasswordRequest(BaseModel):
    """Schema for reset password request."""

    token: str = Field(..., description="Password reset token")
    new_password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="New password (minimum 8 characters)"
    )


class ResetPasswordResponse(BaseModel):
    """Schema for successful password reset response."""

    detail: str = Field(
        default="Password has been successfully reset. Please log in with your new password.",
        description="Confirmation message"
    )


class LogoutRequest(BaseModel):
    """Schema for logout request."""

    refresh_token: str = Field(..., description="JWT refresh token to revoke")


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
        "Returns access and refresh tokens on success. "
        "Implements account lockout: 5 failed attempts per email+IP in 15 minutes "
        "triggers a 15-minute lockout."
    ),
)
@login_rate_limit()
def login_user(
    request: Request,
    login_in: UserLogin,
    db: Session = Depends(get_db),
) -> TokenResponse:
    """Authenticate a user and return tokens with account lockout protection.

    Args:
        request: FastAPI request (for client IP and user agent).
        login_in: User login credentials (email and password).
        db: Database session dependency.

    Returns:
        TokenResponse containing access/refresh tokens and user profile.

    Raises:
        HTTPException: 401 if credentials are invalid, user inactive, or account locked,
                       422 if validation fails.
    """
    # Get client IP and user agent for lockout tracking
    from app.core.rate_limiting import get_client_identifier
    client_ip = get_client_identifier(request)
    user_agent = request.headers.get("User-Agent")

    # Check account lockout status before authentication
    is_locked, failed_count, cooldown_remaining = user_service.check_login_attempts(
        db=db, email=login_in.email, ip_address=client_ip
    )
    if is_locked:
        # Record the blocked attempt
        user_service.record_login_attempt(
            db=db,
            email=login_in.email,
            ip_address=client_ip,
            success=False,
            user_agent=user_agent,
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Account temporarily locked due to too many failed attempts. Try again in {cooldown_remaining} minutes.",
            headers={"Retry-After": str(cooldown_remaining * 60)},
        )

    # Authenticate user
    user = user_service.authenticate_user(db=db, email=login_in.email, password=login_in.password)
    if not user:
        # Record failed attempt
        user_service.record_login_attempt(
            db=db,
            email=login_in.email,
            ip_address=client_ip,
            success=False,
            user_agent=user_agent,
        )
        # Generic error message to prevent email enumeration
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    # Record successful attempt
    user_service.record_login_attempt(
        db=db,
        email=login_in.email,
        ip_address=client_ip,
        success=True,
        user_agent=user_agent,
    )

    # Create a new session ID for this login
    import uuid
    session_id = str(uuid.uuid4())
    refresh_token_id = str(uuid.uuid4())
    refresh_token = create_refresh_token(subject=user.id, token_id=refresh_token_id)

    # Create access token with session_id
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        subject=user.id,
        expires_delta=access_token_expires,
        session_id=session_id,
    )

    # Store refresh token in database with session metadata
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    user_service.store_refresh_token(
        db=db,
        user_id=user.id,
        token=refresh_token,
        expires_at=expires_at,
        session_id=session_id,
        device_info=user_agent,
        ip_address=client_ip,
    )

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


@router.post(
    "/refresh",
    response_model=RefreshTokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Refresh Access Token",
    description=(
        "Exchange a valid refresh token for a new access token and refresh token pair. "
        "Implements refresh token rotation: the old refresh token is invalidated "
        "and a new one is issued. Prevents replay attacks by revoking all tokens "
        "if a reused token is detected."
    ),
)
def refresh_token(
    request: Request,
    refresh_in: RefreshTokenRequest,
    db: Session = Depends(get_db),
) -> RefreshTokenResponse:
    """Refresh access token using a refresh token with rotation.

    Args:
        refresh_in: Refresh token request containing the refresh token.
        db: Database session dependency.

    Returns:
        RefreshTokenResponse containing new access/refresh tokens.

    Raises:
        HTTPException: 401 if refresh token is invalid, expired, revoked, or reused.
    """
    try:
        new_access_token, new_refresh_token, new_db_token = (
            user_service.validate_and_rotate_refresh_token(
                db=db,
                token=refresh_in.refresh_token,
            )
        )
    except TokenExpiredError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token expired",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None
    except InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        ) from None

    expires_in = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60

    return RefreshTokenResponse(
        access_token=new_access_token,
        refresh_token=new_refresh_token,
        token_type="bearer",
        expires_in=expires_in,
    )


@router.post(
    "/forgot-password",
    response_model=ForgotPasswordResponse,
    status_code=status.HTTP_200_OK,
    summary="Request Password Reset",
    description=(
        "Request a password reset for the given email address. "
        "Returns a generic response regardless of whether the email exists "
        "to prevent email enumeration. If the email exists, a reset token "
        "is generated and stored (in production, this would be sent via email). "
        "For development/testing, the reset token is logged for verification."
    ),
)
@forgot_password_rate_limit()
def forgot_password(
    request: Request,
    forgot_in: ForgotPasswordRequest,
    db: Session = Depends(get_db),
) -> ForgotPasswordResponse:
    """Request a password reset for the given email.

    Always returns a generic success response to prevent email enumeration.
    If the user exists, generates a secure single-use reset token.

    Args:
        forgot_in: Forgot password request containing email.
        db: Database session dependency.

    Returns:
        Generic ForgotPasswordResponse (same for existing/non-existing emails).

    Raises:
        HTTPException: 422 if validation fails.
    """
    import secrets
    from datetime import datetime, timezone

    # Normalize email
    email = forgot_in.email.strip().lower()

    # Check if user exists (but don't reveal this in response)
    user = user_service.get_user_by_email(db, email)

    if user:
        # Generate a cryptographically secure random token
        raw_token = secrets.token_urlsafe(32)

        # Calculate expiration (default 15 minutes from config)
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(minutes=settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES)

        # Store the token hash in database
        user_service.create_password_reset_token(
            db=db,
            user_id=user.id,
            token=raw_token,
            expires_at=expires_at,
        )

        # DEVELOPMENT/TESTING ONLY: Log the token for verification when explicitly enabled
        # Controlled by LOG_PASSWORD_RESET_TOKENS config (defaults to False, blocked in production)
        if settings.LOG_PASSWORD_RESET_TOKENS:
            logger.info(
                f"DEV/TEST: Password reset token for {email}: {raw_token} "
                f"(expires at {expires_at.isoformat()})"
            )

        # In production, you would send an email here:
        # await send_password_reset_email(email, raw_token)

    # Always return the same generic response
    return ForgotPasswordResponse()


@router.post(
    "/reset-password",
    response_model=ResetPasswordResponse,
    status_code=status.HTTP_200_OK,
    summary="Reset Password",
    description=(
        "Reset user password using a valid reset token. "
        "The token must be valid, unused, and not expired. "
        "On success, the password is updated, all refresh tokens are revoked, "
        "and the old password no longer works."
    ),
)
@reset_password_rate_limit()
def reset_password(
    request: Request,
    reset_in: ResetPasswordRequest,
    db: Session = Depends(get_db),
) -> ResetPasswordResponse:
    """Reset password using a valid reset token.

    Args:
        reset_in: Reset password request containing token and new password.
        db: Database session dependency.

    Returns:
        ResetPasswordResponse confirming successful reset.

    Raises:
        HTTPException: 401 if token is invalid, expired, or already used.
        HTTPException: 422 if validation fails.
    """
    try:
        user_service.reset_password(
            db=db,
            token=reset_in.token,
            new_password=reset_in.new_password,
        )
    except TokenExpiredError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Reset token has expired",
        ) from None
    except InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        ) from None
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        ) from None

    return ResetPasswordResponse()


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Logout",
    description=(
        "Revoke a specific refresh token to log out from a single session. "
        "Requires a valid access token and the refresh token to revoke. "
        "The refresh token must belong to the authenticated user. "
        "Access tokens remain valid until their natural expiry (30 minutes by default)."
    ),
)
def logout(
    request: Request,
    logout_in: LogoutRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    """Revoke a specific refresh token (single-session logout).

    Args:
        logout_in: Request containing the refresh token to revoke.
        current_user: Authenticated user from access token.
        db: Database session dependency.

    Returns:
        204 No Content on success.

    Raises:
        HTTPException: 401 if access token is invalid or refresh token is invalid/expired/revoked
                       or belongs to another user.
    """
    from app.core.security import decode_refresh_token

    # Decode and validate the refresh token
    try:
        payload = decode_refresh_token(logout_in.refresh_token)
    except TokenExpiredError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None
    except InvalidTokenTypeError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None
    except InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None

    # Verify the refresh token belongs to the authenticated user
    token_user_id = payload.get("sub")
    if token_user_id != current_user.id:
        # Return generic 401 to prevent token validity enumeration
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Revoke the specific refresh token
    revoked = user_service.revoke_refresh_token(db=db, token=logout_in.refresh_token)
    if not revoked:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )


@router.post(
    "/logout-all",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Logout All Sessions",
    description=(
        "Revoke all refresh tokens belonging to the authenticated user. "
        "Logs out from all devices and sessions. "
        "Access tokens remain valid until their natural expiry (30 minutes by default)."
    ),
)
def logout_all(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    """Revoke all refresh tokens for the authenticated user (logout from all sessions).

    Args:
        current_user: Authenticated user from access token.
        db: Database session dependency.

    Returns:
        204 No Content on success.
    """
    user_service.revoke_all_user_tokens(db=db, user_id=current_user.id)


@router.get(
    "/sessions",
    response_model=SessionListResponse,
    status_code=status.HTTP_200_OK,
    summary="List Active Sessions",
    description=(
        "Return the authenticated user's active sessions with device information, "
        "IP address, creation time, last used time, and current session indicator."
    ),
)
def list_sessions(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SessionListResponse:
    """List all active sessions for the authenticated user.

    Args:
        request: FastAPI request (for current session identification).
        current_user: Authenticated user from access token.
        db: Database session dependency.

    Returns:
        SessionListResponse containing list of active sessions.
    """
    from app.core.security import decode_access_token

    # Get current session ID from access token
    credentials = request.headers.get("Authorization", "")
    current_session_id = None
    if credentials.startswith("Bearer "):
        try:
            access_token = credentials[7:]
            payload = decode_access_token(access_token)
            current_session_id = payload.get("sid")
        except Exception:
            pass

    # Get all active sessions for the user
    sessions = user_service.get_user_sessions(db=db, user_id=current_user.id)

    # Build session info list
    session_infos = []
    for session in sessions:
        session_sid = session.session_id or session.id
        session_infos.append(SessionInfo(
            session_id=session_sid,
            device_info=session.device_info,
            ip_address=session.ip_address,
            created_at=session.created_at,
            last_used_at=session.last_used_at,
            is_current=(session_sid == current_session_id),
        ))

    return SessionListResponse(sessions=session_infos)


@router.delete(
    "/sessions/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke Session",
    description=(
        "Revoke a specific session belonging to the authenticated user. "
        "Returns 404 if session not found or belongs to another user."
    ),
)
def revoke_session(
    session_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    """Revoke a specific session for the authenticated user.

    Args:
        session_id: Session identifier to revoke.
        current_user: Authenticated user from access token.
        db: Database session dependency.

    Returns:
        204 No Content on success.

    Raises:
        HTTPException: 404 if session not found or belongs to another user.
    """
    # Verify the session belongs to the user and revoke it
    success = user_service.revoke_session(db=db, user_id=current_user.id, session_id=session_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )