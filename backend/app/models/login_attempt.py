"""SQLAlchemy ORM model for Login Attempts (Account Lockout)."""

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


class LoginAttempt(Base):
    """Login attempt database entity for account lockout tracking.

    Records failed and successful login attempts per email + IP address
    for sliding-window rate limiting and lockout enforcement.
    """

    __tablename__ = "login_attempts"

    id = Column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        index=True,
        doc="Unique attempt record identifier (UUID v4)",
    )
    email = Column(
        String(255),
        nullable=False,
        doc="Email address used in login attempt",
    )
    ip_address = Column(
        String(45),  # Supports IPv4 (15 chars) and IPv6 (45 chars)
        nullable=False,
        doc="Client IP address",
    )
    success = Column(
        Boolean,
        nullable=False,
        default=False,
        doc="Whether the login attempt was successful",
    )
    user_agent = Column(
        String(500),
        nullable=True,
        doc="Client user agent string",
    )
    attempted_at = Column(
        DateTime(timezone=True),
        default=get_utc_now,
        nullable=False,
        doc="UTC timestamp when login was attempted",
    )

    # Composite indexes for common query patterns
    __table_args__ = (
        Index("ix_login_attempts_email_ip", "email", "ip_address"),
        Index("ix_login_attempts_email_ip_attempted_at", "email", "ip_address", "attempted_at"),
        Index("ix_login_attempts_attempted_at", "attempted_at"),
    )