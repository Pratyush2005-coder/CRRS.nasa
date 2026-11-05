"""Pydantic schemas for User authentication."""

from datetime import datetime
from typing import List
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from app.core.enums import UserRole


class UserBase(BaseModel):
    """Base user schema with common fields."""

    email: EmailStr = Field(
        ...,
        description="User email address (normalized to lowercase)",
        examples=["farmer@example.com"],
    )


class UserCreate(UserBase):
    """Schema for user registration request."""

    password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="User password (minimum 8 characters)",
        examples=["SecurePass123"],
    )

    def __init__(self, **data):
        # Normalize email before validation
        if "email" in data and isinstance(data["email"], str):
            data["email"] = data["email"].strip().lower()
        if "password" in data and isinstance(data["password"], str):
            # Don't strip password - user might intentionally use leading/trailing spaces
            # But reject if whitespace-only
            if not data["password"].strip():
                raise ValueError("Password cannot be empty or whitespace-only")
        super().__init__(**data)


class UserLogin(BaseModel):
    """Schema for user login request."""

    email: EmailStr = Field(
        ...,
        description="User email address",
        examples=["farmer@example.com"],
    )
    password: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="User password",
        examples=["SecurePass123"],
    )

    def __init__(self, **data):
        # Normalize email before validation
        if "email" in data and isinstance(data["email"], str):
            data["email"] = data["email"].strip().lower()
        super().__init__(**data)


class TokenResponse(BaseModel):
    """Schema for successful login response."""

    access_token: str = Field(..., description="JWT access token")
    refresh_token: str = Field(..., description="JWT refresh token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(..., description="Access token lifetime in seconds")
    user: "UserResponse" = Field(..., description="Authenticated user profile")


class UserResponse(UserBase):
    """Schema for user registration response (safe fields only)."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique user identifier (UUID v4)")
    role: UserRole = Field(..., description="User role: 'user' or 'admin'")
    is_active: bool = Field(..., description="Whether the user account is active")
    created_at: datetime = Field(..., description="UTC timestamp when user was created")
    updated_at: datetime = Field(..., description="UTC timestamp when user was last updated")


class SessionInfo(BaseModel):
    """Schema for session information response."""

    model_config = ConfigDict(from_attributes=True)

    session_id: str = Field(..., description="Stable session identifier")
    device_info: str | None = Field(None, description="Client device/browser information")
    ip_address: str | None = Field(None, description="Client IP address at session creation")
    created_at: datetime = Field(..., description="UTC timestamp when session was created")
    last_used_at: datetime | None = Field(None, description="UTC timestamp when session was last used")
    is_current: bool = Field(..., description="Whether this is the current session (based on access token)")


class SessionListResponse(BaseModel):
    """Schema for session list response."""

    sessions: List["SessionInfo"] = Field(..., description="List of active sessions")


# Resolve forward reference
TokenResponse.model_rebuild()
SessionListResponse.model_rebuild()