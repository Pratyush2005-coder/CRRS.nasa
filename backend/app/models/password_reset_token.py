"""SQLAlchemy ORM model for Password Reset Tokens."""

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
    """Hash a reset token using SHA-256 for secure storage.

    Args:
        token: Raw reset token string.

    Returns:
        Hex-encoded SHA-256 hash of the token.
    """
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class PasswordResetToken(Base):
    """Password reset token database entity for secure password recovery.

    Stores only hashed token identifiers, never raw tokens.
    Single-use tokens that expire after a short window (default 15 minutes).
    """

    __tablename__ = "password_reset_tokens"

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
        doc="Foreign key to user who owns this reset token",
    )
    token_hash = Column(
        String(64),  # SHA-256 hex digest length
        nullable=False,
        unique=True,
        index=True,
        doc="SHA-256 hash of the raw reset token",
    )
    is_used = Column(
        Boolean,
        nullable=False,
        default=False,
        doc="Whether this token has been consumed (single-use enforcement)",
    )
    created_at = Column(
        DateTime(timezone=True),
        default=get_utc_now,
        nullable=False,
        doc="UTC timestamp when token was issued",
    )
    used_at = Column(
        DateTime(timezone=True),
        nullable=True,
        doc="UTC timestamp when token was consumed",
    )
    expires_at = Column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        doc="UTC timestamp when token expires (default 15 minutes)",
    )
    user = relationship("User", back_populates="password_reset_tokens")