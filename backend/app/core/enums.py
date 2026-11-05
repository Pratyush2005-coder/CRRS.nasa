"""Core enumerations for the application."""

from enum import Enum


class UserRole(str, Enum):
    """User role enumeration.

    Single source of truth for user roles across models, schemas, and dependencies.
    """

    USER = "user"
    ADMIN = "admin"