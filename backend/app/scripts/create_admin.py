#!/usr/bin/env python
"""Script to promote an existing user to admin role.

Usage:
    python -m app.scripts.create_admin <email>

This script:
- Normalizes the email (lowercase, trim whitespace)
- Verifies the user exists
- Requires explicit confirmation before changing the role
- Is idempotent: promoting an existing admin again is safe
- Refuses execution in production environment
"""

import os
import sys
from typing import Optional
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.database import SessionLocal
from app.core.enums import UserRole
from app.models.user import User
from app.services.user_service import user_service


def promote_to_admin(db: Session, email: str) -> tuple[bool, str]:
    """
    Promote a user to admin role.

    Args:
        db: Database session.
        email: Email of the user to promote.

    Returns:
        Tuple of (success: bool, message: str).
    """
    email = email.strip().lower()

    if not email:
        return False, "Error: Email cannot be empty"

    user = user_service.get_user_by_email(db, email)
    if not user:
        return False, f"Error: User with email '{email}' not found"

    if user.role == UserRole.ADMIN.value:
        return False, f"User '{email}' is already an admin. No changes made."

    user.role = UserRole.ADMIN.value
    db.commit()
    db.refresh(user)

    return True, f"Success! User '{user.email}' is now an admin (role: {user.role})."


def main():
    # Environment guard - refuse execution in production
    environment = settings.ENVIRONMENT
    database_url = settings.DATABASE_URL

    if environment == "production":
        print(f"ERROR: Admin creation script cannot run in production environment.")
        print(f"Environment: {environment}")
        print(f"Database: {database_url}")
        sys.exit(1)

    if not environment or environment.strip() == "":
        print("ERROR: ENVIRONMENT is not set. Refusing to run with ambiguous configuration.")
        sys.exit(1)

    # Display environment info for confirmation
    print(f"Environment: {environment}")
    print(f"Database: {database_url}")
    print()

    if len(sys.argv) != 2:
        print("Usage: python -m app.scripts.create_admin <email>")
        print("Example: python -m app.scripts.create_admin admin@example.com")
        sys.exit(1)

    email = sys.argv[1]

    db = SessionLocal()
    try:
        success, message = promote_to_admin(db, email)
        print(message)
        if not success:
            sys.exit(1)
    except Exception as e:
        db.rollback()
        print(f"Error: {e}")
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()