"""SQLAlchemy ORM model for Users."""

import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    String,
)
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.core.enums import UserRole


def get_utc_now() -> datetime:
    """Return current UTC datetime."""
    return datetime.now(timezone.utc)


class User(Base):
    """User database entity."""

    __tablename__ = "users"

    id = Column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        index=True,
        doc="Unique user identifier (UUID v4)",
    )
    email = Column(
        String(255),
        nullable=False,
        unique=True,
        index=True,
        doc="User email address (unique)",
    )
    hashed_password = Column(
        String(255),
        nullable=False,
        doc="PBKDF2-SHA256 hashed password",
    )
    role = Column(
        String(20),
        nullable=False,
        default=UserRole.USER.value,
        doc="User role: 'user' or 'admin'",
    )
    is_active = Column(
        Boolean,
        nullable=False,
        default=True,
        doc="Whether the user account is active",
    )
    created_at = Column(
        DateTime(timezone=True),
        default=get_utc_now,
        nullable=False,
        doc="UTC timestamp when user was created",
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=get_utc_now,
        onupdate=get_utc_now,
        nullable=False,
        doc="UTC timestamp when user was last updated",
    )
    farms = relationship("Farm", back_populates="owner", foreign_keys="Farm.owner_id")
    refresh_tokens = relationship("RefreshToken", back_populates="user", cascade="all, delete-orphan")
    password_reset_tokens = relationship("PasswordResetToken", back_populates="user", cascade="all, delete-orphan")