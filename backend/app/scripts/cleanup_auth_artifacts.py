#!/usr/bin/env python
"""Standalone script to clean up expired authentication artifacts.

This script removes:
- Revoked refresh tokens older than REVOKED_REFRESH_TOKEN_RETENTION_DAYS (default 30 days)
- Used password reset tokens older than USED_RESET_TOKEN_RETENTION_DAYS (default 30 days)
- Expired (unused) password reset tokens older than EXPIRED_RESET_TOKEN_RETENTION_DAYS (default 7 days)
- Expired (unrevoked) refresh tokens older than EXPIRED_UNREVOKED_REFRESH_TOKEN_RETENTION_DAYS (default 7 days)
- Old login attempt records beyond lockout window + cooldown + buffer

Usage:
    python -m app.scripts.cleanup_auth_artifacts [--dry-run] [--verbose]

Options:
    --dry-run    Show what would be deleted without actually deleting
    --verbose    Show detailed output
    --help       Show this help message

Environment:
    - Reads configuration from .env file via Settings
    - Refuses execution in production environment unless --force-production is used
"""

import os
import sys
import argparse
from typing import Optional
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.database import SessionLocal
from app.services.user_service import user_service


def cleanup_auth_artifacts(
    db: Session,
    dry_run: bool = False,
    verbose: bool = False,
) -> dict:
    """
    Clean up expired authentication artifacts.

    Args:
        db: Database session.
        dry_run: If True, only show what would be deleted.
        verbose: If True, show detailed output.

    Returns:
        Dictionary with counts of deleted items by category.
    """
    results = {
        "revoked_refresh_tokens": 0,
        "used_reset_tokens": 0,
        "expired_unused_reset_tokens": 0,
        "expired_unrevoked_refresh_tokens": 0,
        "login_attempts": 0,
    }

    if verbose:
        print(f"Configuration:")
        print(f"  REVOKED_REFRESH_TOKEN_RETENTION_DAYS: {settings.REVOKED_REFRESH_TOKEN_RETENTION_DAYS}")
        print(f"  USED_RESET_TOKEN_RETENTION_DAYS: {settings.USED_RESET_TOKEN_RETENTION_DAYS}")
        print(f"  EXPIRED_RESET_TOKEN_RETENTION_DAYS: {settings.EXPIRED_RESET_TOKEN_RETENTION_DAYS}")
        print(f"  EXPIRED_UNREVOKED_REFRESH_TOKEN_RETENTION_DAYS: {settings.EXPIRED_UNREVOKED_REFRESH_TOKEN_RETENTION_DAYS}")
        print(f"  LOGIN_ATTEMPT_WINDOW_MINUTES: {settings.LOGIN_ATTEMPT_WINDOW_MINUTES}")
        print(f"  LOGIN_ATTEMPT_COOLDOWN_MINUTES: {settings.LOGIN_ATTEMPT_COOLDOWN_MINUTES}")
        print(f"  AUTH_CLEANUP_BATCH_SIZE: {settings.AUTH_CLEANUP_BATCH_SIZE}")
        print()

    if dry_run:
        print("DRY RUN MODE - No changes will be made")
        print()

    # Clean up revoked refresh tokens
    if verbose:
        print("Cleaning up revoked refresh tokens...")
    if not dry_run:
        count = user_service.cleanup_revoked_refresh_tokens(db)
    else:
        # For dry run, we need to count without deleting
        from datetime import datetime, timezone, timedelta
        from app.models.refresh_token import RefreshToken
        from sqlalchemy import select
        cutoff = datetime.now(timezone.utc) - timedelta(days=settings.REVOKED_REFRESH_TOKEN_RETENTION_DAYS)
        count = len(db.execute(
            select(RefreshToken).where(
                RefreshToken.is_revoked == True,
                RefreshToken.revoked_at < cutoff,
            )
        ).scalars().all())
    results["revoked_refresh_tokens"] = count
    if verbose or count > 0:
        print(f"  {'Would delete' if dry_run else 'Deleted'} {count} revoked refresh token(s)")

    # Clean up used password reset tokens
    if verbose:
        print("Cleaning up used password reset tokens...")
    if not dry_run:
        count = user_service.cleanup_used_reset_tokens(db)
    else:
        from datetime import datetime, timezone, timedelta
        from app.models.password_reset_token import PasswordResetToken
        from sqlalchemy import select
        cutoff = datetime.now(timezone.utc) - timedelta(days=settings.USED_RESET_TOKEN_RETENTION_DAYS)
        count = len(db.execute(
            select(PasswordResetToken).where(
                PasswordResetToken.is_used == True,
                PasswordResetToken.used_at < cutoff,
            )
        ).scalars().all())
    results["used_reset_tokens"] = count
    if verbose or count > 0:
        print(f"  {'Would delete' if dry_run else 'Deleted'} {count} used reset token(s)")

    # Clean up expired (unused) password reset tokens
    if verbose:
        print("Cleaning up expired (unused) password reset tokens...")
    if not dry_run:
        count = user_service.cleanup_expired_unused_reset_tokens(db)
    else:
        from datetime import datetime, timezone, timedelta
        from app.models.password_reset_token import PasswordResetToken
        from sqlalchemy import select
        cutoff = datetime.now(timezone.utc) - timedelta(days=settings.EXPIRED_RESET_TOKEN_RETENTION_DAYS)
        count = len(db.execute(
            select(PasswordResetToken).where(
                PasswordResetToken.is_used == False,
                PasswordResetToken.expires_at < cutoff,
            )
        ).scalars().all())
    results["expired_unused_reset_tokens"] = count
    if verbose or count > 0:
        print(f"  {'Would delete' if dry_run else 'Deleted'} {count} expired unused reset token(s)")

    # Clean up expired (unrevoked) refresh tokens
    if verbose:
        print("Cleaning up expired (unrevoked) refresh tokens...")
    if not dry_run:
        count = user_service.cleanup_expired_unrevoked_refresh_tokens(db)
    else:
        from datetime import datetime, timezone, timedelta
        from app.models.refresh_token import RefreshToken
        from sqlalchemy import select
        cutoff = datetime.now(timezone.utc) - timedelta(days=settings.EXPIRED_UNREVOKED_REFRESH_TOKEN_RETENTION_DAYS)
        count = len(db.execute(
            select(RefreshToken).where(
                RefreshToken.is_revoked == False,
                RefreshToken.expires_at < cutoff,
            )
        ).scalars().all())
    results["expired_unrevoked_refresh_tokens"] = count
    if verbose or count > 0:
        print(f"  {'Would delete' if dry_run else 'Deleted'} {count} expired unrevoked refresh token(s)")

    # Clean up old login attempt records
    if verbose:
        print("Cleaning up old login attempt records...")
    if not dry_run:
        count = user_service.cleanup_login_attempts(db)
    else:
        from datetime import datetime, timezone, timedelta
        from app.models.login_attempt import LoginAttempt
        from sqlalchemy import select
        retention_minutes = (
            settings.LOGIN_ATTEMPT_WINDOW_MINUTES
            + settings.LOGIN_ATTEMPT_COOLDOWN_MINUTES
            + 60  # 1 hour buffer
        )
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=retention_minutes)
        count = len(db.execute(
            select(LoginAttempt).where(
                LoginAttempt.attempted_at < cutoff,
            )
        ).scalars().all())
    results["login_attempts"] = count
    if verbose or count > 0:
        print(f"  {'Would delete' if dry_run else 'Deleted'} {count} login attempt record(s)")

    total = sum(results.values())
    if verbose or total > 0:
        print()
        print(f"Total: {'would be deleted' if dry_run else 'deleted'} {total} authentication artifact(s)")

    return results


def main():
    parser = argparse.ArgumentParser(
        description="Clean up expired authentication artifacts (refresh tokens, password reset tokens)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be deleted without actually deleting",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show detailed output",
    )
    parser.add_argument(
        "--force-production",
        action="store_true",
        help="Allow execution in production environment (use with caution)",
    )

    args = parser.parse_args()

    # Environment guard - refuse execution in production unless forced
    environment = settings.ENVIRONMENT
    database_url = settings.DATABASE_URL

    if environment == "production" and not args.force_production:
        print(f"ERROR: Cleanup script cannot run in production environment without --force-production flag.")
        print(f"Environment: {environment}")
        print(f"Database: {database_url}")
        print("Use --force-production to override (not recommended).")
        sys.exit(1)

    if not environment or environment.strip() == "":
        print("ERROR: ENVIRONMENT is not set. Refusing to run with ambiguous configuration.")
        sys.exit(1)

    # Display environment info
    print(f"Environment: {environment}")
    print(f"Database: {database_url}")
    print()

    db = SessionLocal()
    try:
        cleanup_auth_artifacts(db, dry_run=args.dry_run, verbose=args.verbose)
    except Exception as e:
        db.rollback()
        print(f"Error: {e}")
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()