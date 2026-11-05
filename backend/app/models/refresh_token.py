"""SQLAlchemy ORM model for Refresh Tokens."""

import hashlib
import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    String,
)
from sqlalchemy.orm import relationship
from app.core.database import Base


def get_utc_now() -> datetime:
    """Return current UTC datetime."""
    return datetime.now(timezone.utc)


def hash_token(token: str) -> str:
    """Hash a refresh token using SHA-256 for secure storage.

    Args:
        token: Raw refresh token string.

    Returns:
        Hex-encoded SHA-256 hash of the token.
    """
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class RefreshToken(Base):
    """Refresh token database entity for rotation and revocation tracking.

    Stores only hashed token identifiers, never raw tokens.
    Includes session metadata for device/session management.
    """

    __tablename__ = "refresh_tokens"

    id = Column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        index=True,
        doc="Unique token record identifier (UUID v4)",
    )
    user_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="Foreign key to user who owns this refresh token",
    )
    # Session ID: stable identifier across token rotations for the same device/session
    session_id = Column(
        String(36),
        nullable=True,
        index=True,
        doc="Stable session identifier across token rotations (UUID v4)",
    )
    token_hash = Column(
        String(64),  # SHA-256 hex digest length
        nullable=False,
        unique=True,
        index=True,
        doc="SHA-256 hash of the raw refresh token",
    )
    is_revoked = Column(
        Boolean,
        nullable=False,
        default=False,
        doc="Whether this token has been revoked/rotated",
    )
    created_at = Column(
        DateTime(timezone=True),
        default=get_utc_now,
        nullable=False,
        doc="UTC timestamp when token was issued",
    )
    revoked_at = Column(
        DateTime(timezone=True),
        nullable=True,
        doc="UTC timestamp when token was revoked (rotation or logout)",
    )
    expires_at = Column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        doc="UTC timestamp when token expires",
    )
    # Session metadata fields
    device_info = Column(
        String(512),
        nullable=True,
        doc="Client device/browser information (User-Agent or parsed)",
    )
    ip_address = Column(
        String(45),  # IPv6 max length
        nullable=True,
        doc="Client IP address at token creation",
    )
    last_used_at = Column(
        DateTime(timezone=True),
        nullable=True,
        doc="UTC timestamp when token was last used for refresh",
    )
    user = relationship("User", back_populates="refresh_tokens")