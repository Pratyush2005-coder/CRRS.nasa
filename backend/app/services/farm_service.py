"""Service layer for Farm Profile CRUD operations."""

from datetime import datetime, timezone
from typing import List, Optional, Tuple
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.farm import Farm
from app.schemas.farm import FarmCreate, FarmUpdate


class FarmService:
    """Service handling farm business logic and database interactions."""

    def _prepare_farm_data(self, data: dict, original_obj=None) -> dict:
        """Helper to ensure enum values and nested Pydantic models serialize cleanly."""
        prepared = dict(data)
        if "soil_type" in prepared and prepared["soil_type"] is not None:
            if hasattr(prepared["soil_type"], "value"):
                prepared["soil_type"] = prepared["soil_type"].value
        if "primary_irrigation" in prepared and prepared["primary_irrigation"] is not None:
            if hasattr(prepared["primary_irrigation"], "value"):
                prepared["primary_irrigation"] = prepared["primary_irrigation"].value
        if "previous_crops" in prepared and prepared["previous_crops"] is not None:
            prepared["previous_crops"] = [
                crop.model_dump() if hasattr(crop, "model_dump") else crop
                for crop in prepared["previous_crops"]
            ]
        return prepared

    def create_farm(self, db: Session, farm_in: FarmCreate) -> Farm:
        """Create and persist a new farm profile."""
        data = self._prepare_farm_data(farm_in.model_dump(), farm_in)
        db_farm = Farm(**data)
        db.add(db_farm)
        db.commit()
        db.refresh(db_farm)
        return db_farm

    def get_farm_by_id(self, db: Session, farm_id: str) -> Optional[Farm]:
        """Fetch a single farm profile by UUID."""
        return db.query(Farm).filter(Farm.id == farm_id).first()

    def list_farms(
        self,
        db: Session,
        skip: int = 0,
        limit: int = 20,
        search: Optional[str] = None,
        soil_type: Optional[str] = None,
    ) -> Tuple[List[Farm], int]:
        """List farm profiles with pagination, search, and soil type filtering."""
        query = db.query(Farm)

        if search:
            search_pattern = f"%{search.strip()}%"
            query = query.filter(
                or_(
                    Farm.name.ilike(search_pattern),
                    Farm.farmer_name.ilike(search_pattern),
                    Farm.region.ilike(search_pattern),
                    Farm.country.ilike(search_pattern),
                )
            )

        if soil_type:
            query = query.filter(Farm.soil_type == soil_type)

        total = query.count()
        items = (
            query.order_by(Farm.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )
        return items, total

    def replace_farm(self, db: Session, db_farm: Farm, farm_in: FarmCreate) -> Farm:
        """Full update (PUT) of a farm profile, replacing all updatable fields."""
        data = self._prepare_farm_data(farm_in.model_dump(), farm_in)

        for field, value in data.items():
            setattr(db_farm, field, value)

        db_farm.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(db_farm)
        return db_farm

    def update_farm(self, db: Session, db_farm: Farm, farm_update: FarmUpdate) -> Farm:
        """Partial update (PATCH) of a farm profile for provided fields only."""
        update_data = self._prepare_farm_data(
            farm_update.model_dump(exclude_unset=True),
            farm_update,
        )

        for field, value in update_data.items():
            setattr(db_farm, field, value)

        db_farm.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(db_farm)
        return db_farm

    def delete_farm(self, db: Session, db_farm: Farm) -> None:
        """Delete a farm profile from database."""
        db.delete(db_farm)
        db.commit()


farm_service = FarmService()
