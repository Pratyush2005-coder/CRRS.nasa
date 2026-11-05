"""SQLAlchemy ORM model for Farm Profiles."""

import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    JSON,
    String,
)
from sqlalchemy.orm import relationship
from app.core.database import Base


def get_utc_now() -> datetime:
    """Return current UTC datetime."""
    return datetime.now(timezone.utc)


class Farm(Base):
    """Farm profile database entity."""

    __tablename__ = "farms"

    id = Column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        index=True,
        doc="Unique farm identifier (UUID v4)",
    )
    name = Column(
        String(150),
        nullable=False,
        index=True,
        doc="Name or identifier of the farm / field",
    )
    farmer_name = Column(
        String(100),
        nullable=True,
        index=True,
        doc="Name of primary farmer or estate manager",
    )
    latitude = Column(
        Float,
        nullable=False,
        doc="Latitude coordinate in decimal degrees (-90.0 to 90.0)",
    )
    longitude = Column(
        Float,
        nullable=False,
        doc="Longitude coordinate in decimal degrees (-180.0 to 180.0)",
    )
    elevation_m = Column(
        Float,
        nullable=True,
        doc="Elevation above sea level in meters",
    )
    region = Column(
        String(100),
        nullable=True,
        index=True,
        doc="Sub-national administrative region (state, province, district)",
    )
    country = Column(
        String(100),
        nullable=True,
        doc="Country name or ISO code",
    )
    total_area_hectares = Column(
        Float,
        nullable=False,
        doc="Total cultivable area in hectares",
    )
    soil_type = Column(
        String(50),
        nullable=False,
        doc="Dominant soil classification",
    )
    soil_ph = Column(
        Float,
        nullable=True,
        doc="Measured soil pH level (3.0 to 10.0)",
    )
    organic_matter_pct = Column(
        Float,
        nullable=True,
        doc="Soil organic matter percentage (0.0 to 100.0)",
    )
    primary_irrigation = Column(
        String(50),
        nullable=False,
        default="rainfed",
        doc="Primary irrigation infrastructure type",
    )
    current_crop = Column(
        String(100),
        nullable=True,
        doc="Crop currently standing in the field",
    )
    current_crop_planting_date = Column(
        Date,
        nullable=True,
        doc="Planting date for current crop",
    )
    previous_crops = Column(
        JSON,
        nullable=False,
        default=list,
        doc="List of historical crop records with harvest seasons and yields",
    )
    created_at = Column(
        DateTime(timezone=True),
        default=get_utc_now,
        nullable=False,
        doc="UTC timestamp when farm profile was created",
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=get_utc_now,
        onupdate=get_utc_now,
        nullable=False,
        doc="UTC timestamp when farm profile was last updated",
    )
    owner_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        doc="Foreign key to user who owns this farm (nullable for legacy farms)",
    )
    owner = relationship("User", back_populates="farms", foreign_keys=[owner_id])
