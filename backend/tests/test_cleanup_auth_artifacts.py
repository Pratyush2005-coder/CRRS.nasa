"""Tests for authentication artifact cleanup functionality."""

import os
from datetime import timedelta, datetime, timezone
import pytest
from sqlalchemy import select

from app.core.config import settings
from app.core.security import (
    create_refresh_token,
    hash_password,
)
from app.models.refresh_token import RefreshToken, hash_token as hash_refresh_token
from app.models.password_reset_token import PasswordResetToken, hash_token as hash_reset_token
from app.models.user import User
from app.services.user_service import UserService
from app.scripts.cleanup_auth_artifacts import cleanup_auth_artifacts


class TestCleanupAuthArtifactsServiceMethods:
    """Tests for UserService cleanup methods."""

    @pytest.fixture
    def test_db(self):
        """Create a test database session."""
        from tests.conftest import TestingSessionLocal
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    @pytest.fixture
    def test_user(self, test_db):
        """Create a test user with properly hashed password."""
        user = User(
            id="test-user-123",
            email="test@example.com",
            hashed_password=hash_password("password123"),
            role="user",
            is_active=True,
        )
        test_db.add(user)
        test_db.commit()
        test_db.refresh(user)
        return user

    def test_cleanup_revoked_refresh_tokens(self, test_db, test_user):
        """cleanup_revoked_refresh_tokens removes old revoked tokens."""
        service = UserService()

        # Create old revoked token (older than retention period)
        old_token = create_refresh_token(subject=test_user.id, token_id="old-token-1")
        old_expires_at = datetime.now(timezone.utc) + timedelta(days=7)
        old_revoked_at = datetime.now(timezone.utc) - timedelta(days=settings.REVOKED_REFRESH_TOKEN_RETENTION_DAYS + 5)
        db_old_token = RefreshToken(
            user_id=test_user.id,
            token_hash=hash_refresh_token(old_token),
            expires_at=old_expires_at,
            is_revoked=True,
            revoked_at=old_revoked_at,
        )
        test_db.add(db_old_token)

        # Create recent revoked token (within retention period)
        recent_token = create_refresh_token(subject=test_user.id, token_id="recent-token-1")
        recent_expires_at = datetime.now(timezone.utc) + timedelta(days=7)
        recent_revoked_at = datetime.now(timezone.utc) - timedelta(days=5)
        db_recent_token = RefreshToken(
            user_id=test_user.id,
            token_hash=hash_refresh_token(recent_token),
            expires_at=recent_expires_at,
            is_revoked=True,
            revoked_at=recent_revoked_at,
        )
        test_db.add(db_recent_token)

        # Create active (non-revoked) token - should not be deleted
        active_token = create_refresh_token(subject=test_user.id, token_id="active-token-1")
        active_expires_at = datetime.now(timezone.utc) + timedelta(days=7)
        db_active_token = RefreshToken(
            user_id=test_user.id,
            token_hash=hash_refresh_token(active_token),
            expires_at=active_expires_at,
            is_revoked=False,
        )
        test_db.add(db_active_token)

        test_db.commit()

        # Run cleanup
        count = service.cleanup_revoked_refresh_tokens(db=test_db)

        assert count == 1

        # Verify only old revoked token was deleted
        remaining = test_db.execute(select(RefreshToken)).scalars().all()
        assert len(remaining) == 2
        assert all(t.token_hash in [hash_refresh_token(recent_token), hash_refresh_token(active_token)] for t in remaining)

    def test_cleanup_revoked_refresh_tokens_zero_retention(self, test_db, test_user, monkeypatch):
        """cleanup_revoked_refresh_tokens with zero retention deletes all revoked tokens."""
        monkeypatch.setattr(settings, "REVOKED_REFRESH_TOKEN_RETENTION_DAYS", 0)

        service = UserService()

        # Create revoked token
        token = create_refresh_token(subject=test_user.id, token_id="token-1")
        expires_at = datetime.now(timezone.utc) + timedelta(days=7)
        revoked_at = datetime.now(timezone.utc) - timedelta(days=1)
        db_token = RefreshToken(
            user_id=test_user.id,
            token_hash=hash_refresh_token(token),
            expires_at=expires_at,
            is_revoked=True,
            revoked_at=revoked_at,
        )
        test_db.add(db_token)
        test_db.commit()

        count = service.cleanup_revoked_refresh_tokens(db=test_db)

        assert count == 1

        remaining = test_db.execute(select(RefreshToken)).scalars().all()
        assert len(remaining) == 0

    def test_cleanup_used_reset_tokens(self, test_db, test_user):
        """cleanup_used_reset_tokens removes old used tokens."""
        service = UserService()

        # Create old used token (older than retention period)
        old_token = "old-reset-token-1"
        old_expires_at = datetime.now(timezone.utc) + timedelta(minutes=15)
        old_used_at = datetime.now(timezone.utc) - timedelta(days=settings.USED_RESET_TOKEN_RETENTION_DAYS + 5)
        db_old_token = PasswordResetToken(
            user_id=test_user.id,
            token_hash=hash_reset_token(old_token),
            expires_at=old_expires_at,
            is_used=True,
            used_at=old_used_at,
        )
        test_db.add(db_old_token)

        # Create recent used token (within retention period)
        recent_token = "recent-reset-token-1"
        recent_expires_at = datetime.now(timezone.utc) + timedelta(minutes=15)
        recent_used_at = datetime.now(timezone.utc) - timedelta(days=5)
        db_recent_token = PasswordResetToken(
            user_id=test_user.id,
            token_hash=hash_reset_token(recent_token),
            expires_at=recent_expires_at,
            is_used=True,
            used_at=recent_used_at,
        )
        test_db.add(db_recent_token)

        # Create unused token - should not be deleted
        unused_token = "unused-reset-token-1"
        unused_expires_at = datetime.now(timezone.utc) + timedelta(minutes=15)
        db_unused_token = PasswordResetToken(
            user_id=test_user.id,
            token_hash=hash_reset_token(unused_token),
            expires_at=unused_expires_at,
            is_used=False,
        )
        test_db.add(db_unused_token)

        test_db.commit()

        # Run cleanup
        count = service.cleanup_used_reset_tokens(db=test_db)

        assert count == 1

        # Verify only old used token was deleted
        remaining = test_db.execute(select(PasswordResetToken)).scalars().all()
        assert len(remaining) == 2
        assert all(t.token_hash in [hash_reset_token(recent_token), hash_reset_token(unused_token)] for t in remaining)

    def test_cleanup_used_reset_tokens_zero_retention(self, test_db, test_user, monkeypatch):
        """cleanup_used_reset_tokens with zero retention deletes all used tokens."""
        monkeypatch.setattr(settings, "USED_RESET_TOKEN_RETENTION_DAYS", 0)

        service = UserService()

        # Create used token
        token = "used-reset-token-1"
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=15)
        used_at = datetime.now(timezone.utc) - timedelta(days=1)
        db_token = PasswordResetToken(
            user_id=test_user.id,
            token_hash=hash_reset_token(token),
            expires_at=expires_at,
            is_used=True,
            used_at=used_at,
        )
        test_db.add(db_token)
        test_db.commit()

        count = service.cleanup_used_reset_tokens(db=test_db)

        assert count == 1

        remaining = test_db.execute(select(PasswordResetToken)).scalars().all()
        assert len(remaining) == 0

    def test_cleanup_expired_unused_reset_tokens(self, test_db, test_user):
        """cleanup_expired_unused_reset_tokens removes old expired unused tokens."""
        service = UserService()

        # Create old expired unused token (older than retention period)
        old_token = "old-expired-unused-token-1"
        old_expires_at = datetime.now(timezone.utc) - timedelta(days=settings.EXPIRED_RESET_TOKEN_RETENTION_DAYS + 5)
        db_old_token = PasswordResetToken(
            user_id=test_user.id,
            token_hash=hash_reset_token(old_token),
            expires_at=old_expires_at,
            is_used=False,
        )
        test_db.add(db_old_token)

        # Create recent expired unused token (within retention period)
        recent_token = "recent-expired-unused-token-1"
        recent_expires_at = datetime.now(timezone.utc) - timedelta(days=2)
        db_recent_token = PasswordResetToken(
            user_id=test_user.id,
            token_hash=hash_reset_token(recent_token),
            expires_at=recent_expires_at,
            is_used=False,
        )
        test_db.add(db_recent_token)

        # Create valid (not expired) unused token - should not be deleted
        valid_token = "valid-unused-token-1"
        valid_expires_at = datetime.now(timezone.utc) + timedelta(minutes=15)
        db_valid_token = PasswordResetToken(
            user_id=test_user.id,
            token_hash=hash_reset_token(valid_token),
            expires_at=valid_expires_at,
            is_used=False,
        )
        test_db.add(db_valid_token)

        test_db.commit()

        # Run cleanup
        count = service.cleanup_expired_unused_reset_tokens(db=test_db)

        assert count == 1

        # Verify only old expired unused token was deleted
        remaining = test_db.execute(select(PasswordResetToken)).scalars().all()
        assert len(remaining) == 2
        assert all(t.token_hash in [hash_reset_token(recent_token), hash_reset_token(valid_token)] for t in remaining)

    def test_cleanup_expired_unused_reset_tokens_zero_retention(self, test_db, test_user, monkeypatch):
        """cleanup_expired_unused_reset_tokens with zero retention deletes all expired unused tokens."""
        monkeypatch.setattr(settings, "EXPIRED_RESET_TOKEN_RETENTION_DAYS", 0)

        service = UserService()

        # Create expired unused token
        token = "expired-unused-token-1"
        expires_at = datetime.now(timezone.utc) - timedelta(days=1)
        db_token = PasswordResetToken(
            user_id=test_user.id,
            token_hash=hash_reset_token(token),
            expires_at=expires_at,
            is_used=False,
        )
        test_db.add(db_token)
        test_db.commit()

        count = service.cleanup_expired_unused_reset_tokens(db=test_db)

        assert count == 1

        remaining = test_db.execute(select(PasswordResetToken)).scalars().all()
        assert len(remaining) == 0

    def test_cleanup_expired_unrevoked_refresh_tokens(self, test_db, test_user):
        """cleanup_expired_unrevoked_refresh_tokens removes old expired unrevoked tokens."""
        service = UserService()

        # Create old expired unrevoked token (older than retention period)
        old_token = create_refresh_token(subject=test_user.id, token_id="old-expired-unrevoked-1")
        old_expires_at = datetime.now(timezone.utc) - timedelta(days=settings.EXPIRED_UNREVOKED_REFRESH_TOKEN_RETENTION_DAYS + 5)
        db_old_token = RefreshToken(
            user_id=test_user.id,
            token_hash=hash_refresh_token(old_token),
            expires_at=old_expires_at,
            is_revoked=False,
        )
        test_db.add(db_old_token)

        # Create recent expired unrevoked token (within retention period)
        recent_token = create_refresh_token(subject=test_user.id, token_id="recent-expired-unrevoked-1")
        recent_expires_at = datetime.now(timezone.utc) - timedelta(days=2)
        db_recent_token = RefreshToken(
            user_id=test_user.id,
            token_hash=hash_refresh_token(recent_token),
            expires_at=recent_expires_at,
            is_revoked=False,
        )
        test_db.add(db_recent_token)

        # Create valid (not expired) unrevoked token - should not be deleted
        valid_token = create_refresh_token(subject=test_user.id, token_id="valid-unrevoked-1")
        valid_expires_at = datetime.now(timezone.utc) + timedelta(days=7)
        db_valid_token = RefreshToken(
            user_id=test_user.id,
            token_hash=hash_refresh_token(valid_token),
            expires_at=valid_expires_at,
            is_revoked=False,
        )
        test_db.add(db_valid_token)

        test_db.commit()

        # Run cleanup
        count = service.cleanup_expired_unrevoked_refresh_tokens(db=test_db)

        assert count == 1

        # Verify only old expired unrevoked token was deleted
        remaining = test_db.execute(select(RefreshToken)).scalars().all()
        assert len(remaining) == 2
        assert all(t.token_hash in [hash_refresh_token(recent_token), hash_refresh_token(valid_token)] for t in remaining)

    def test_cleanup_expired_unrevoked_refresh_tokens_zero_retention(self, test_db, test_user, monkeypatch):
        """cleanup_expired_unrevoked_refresh_tokens with zero retention deletes all expired unrevoked tokens."""
        monkeypatch.setattr(settings, "EXPIRED_UNREVOKED_REFRESH_TOKEN_RETENTION_DAYS", 0)

        service = UserService()

        # Create expired unrevoked token
        token = create_refresh_token(subject=test_user.id, token_id="expired-unrevoked-1")
        expires_at = datetime.now(timezone.utc) - timedelta(days=1)
        db_token = RefreshToken(
            user_id=test_user.id,
            token_hash=hash_refresh_token(token),
            expires_at=expires_at,
            is_revoked=False,
        )
        test_db.add(db_token)
        test_db.commit()

        count = service.cleanup_expired_unrevoked_refresh_tokens(db=test_db)

        assert count == 1

        remaining = test_db.execute(select(RefreshToken)).scalars().all()
        assert len(remaining) == 0

    def test_cleanup_preserves_active_unexpired_refresh_tokens(self, test_db, test_user):
        """cleanup does not delete active unexpired refresh tokens."""
        service = UserService()

        # Create active unrevoked unexpired token
        active_token = create_refresh_token(subject=test_user.id, token_id="active-unrevoked-1")
        active_expires_at = datetime.now(timezone.utc) + timedelta(days=7)
        db_active_token = RefreshToken(
            user_id=test_user.id,
            token_hash=hash_refresh_token(active_token),
            expires_at=active_expires_at,
            is_revoked=False,
        )
        test_db.add(db_active_token)

        # Create old revoked token
        old_revoked_token = create_refresh_token(subject=test_user.id, token_id="old-revoked-1")
        old_revoked_expires = datetime.now(timezone.utc) + timedelta(days=7)
        old_revoked_revoked_at = datetime.now(timezone.utc) - timedelta(days=settings.REVOKED_REFRESH_TOKEN_RETENTION_DAYS + 5)
        db_old_revoked = RefreshToken(
            user_id=test_user.id,
            token_hash=hash_refresh_token(old_revoked_token),
            expires_at=old_revoked_expires,
            is_revoked=True,
            revoked_at=old_revoked_revoked_at,
        )
        test_db.add(db_old_revoked)

        test_db.commit()

        # Run both cleanups
        revoked_count = service.cleanup_revoked_refresh_tokens(db=test_db)
        expired_unrevoked_count = service.cleanup_expired_unrevoked_refresh_tokens(db=test_db)

        # Old revoked should be deleted, active unexpired should be preserved
        assert revoked_count == 1
        assert expired_unrevoked_count == 0

        remaining = test_db.execute(select(RefreshToken)).scalars().all()
        assert len(remaining) == 1
        assert remaining[0].token_hash == hash_refresh_token(active_token)
        assert remaining[0].is_revoked == False

    def test_batch_size_limits_deletion(self, test_db, test_user, monkeypatch):
        """Batch size limits the number of records deleted per batch."""
        # Set batch size to 2
        monkeypatch.setattr(settings, "AUTH_CLEANUP_BATCH_SIZE", 2)
        monkeypatch.setattr(settings, "EXPIRED_UNREVOKED_REFRESH_TOKEN_RETENTION_DAYS", 0)

        service = UserService()

        # Create 5 expired unrevoked tokens
        for i in range(5):
            token = create_refresh_token(subject=test_user.id, token_id=f"expired-batch-{i}")
            expires_at = datetime.now(timezone.utc) - timedelta(days=1)
            db_token = RefreshToken(
                user_id=test_user.id,
                token_hash=hash_refresh_token(token),
                expires_at=expires_at,
                is_revoked=False,
            )
            test_db.add(db_token)
        test_db.commit()

        # Run cleanup - should delete all 5 in batches of 2
        count = service.cleanup_expired_unrevoked_refresh_tokens(db=test_db)

        assert count == 5

        remaining = test_db.execute(select(RefreshToken)).scalars().all()
        assert len(remaining) == 0

    def test_batch_size_validation_zero_rejected(self):
        """AUTH_CLEANUP_BATCH_SIZE rejects zero."""
        from app.core.config import Settings
        import os

        os.environ["SECRET_KEY"] = "test"
        os.environ["AUTH_CLEANUP_BATCH_SIZE"] = "0"
        try:
            Settings()
            assert False, "Expected ValueError"
        except ValueError as e:
            assert "AUTH_CLEANUP_BATCH_SIZE must be positive" in str(e)

    def test_batch_size_validation_negative_rejected(self):
        """AUTH_CLEANUP_BATCH_SIZE rejects negative values."""
        from app.core.config import Settings
        import os

        os.environ["SECRET_KEY"] = "test"
        os.environ["AUTH_CLEANUP_BATCH_SIZE"] = "-1"
        try:
            Settings()
            assert False, "Expected ValueError"
        except ValueError as e:
            assert "AUTH_CLEANUP_BATCH_SIZE must be positive" in str(e)

    def test_cleanup_idempotent(self, test_db, test_user):
        """Running cleanup twice produces same result (idempotent)."""
        service = UserService()

        # Create old expired unrevoked token
        old_token = create_refresh_token(subject=test_user.id, token_id="idempotent-1")
        old_expires_at = datetime.now(timezone.utc) - timedelta(days=settings.EXPIRED_UNREVOKED_REFRESH_TOKEN_RETENTION_DAYS + 5)
        db_old_token = RefreshToken(
            user_id=test_user.id,
            token_hash=hash_refresh_token(old_token),
            expires_at=old_expires_at,
            is_revoked=False,
        )
        test_db.add(db_old_token)
        test_db.commit()

        # First cleanup
        count1 = service.cleanup_expired_unrevoked_refresh_tokens(db=test_db)
        assert count1 == 1

        # Second cleanup
        count2 = service.cleanup_expired_unrevoked_refresh_tokens(db=test_db)
        assert count2 == 0

        remaining = test_db.execute(select(RefreshToken)).scalars().all()
        assert len(remaining) == 0


class TestCleanupAuthArtifactsScript:
    """Tests for the standalone cleanup_auth_artifacts script function."""

    @pytest.fixture
    def test_db(self, setup_test_db):
        """Create a test database session."""
        from tests.conftest import TestingSessionLocal
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    @pytest.fixture
    def test_user(self, test_db):
        """Create a test user with properly hashed password."""
        user = User(
            id="test-user-123",
            email="test@example.com",
            hashed_password=hash_password("password123"),
            role="user",
            is_active=True,
        )
        test_db.add(user)
        test_db.commit()
        test_db.refresh(user)
        return user

    def test_cleanup_auth_artifacts_dry_run(self, test_db, test_user):
        """cleanup_auth_artifacts dry_run mode reports counts without deleting."""
        # Create tokens that would be cleaned up
        old_revoked_token = create_refresh_token(subject=test_user.id, token_id="old-revoked-1")
        old_revoked_expires = datetime.now(timezone.utc) + timedelta(days=7)
        old_revoked_revoked_at = datetime.now(timezone.utc) - timedelta(days=settings.REVOKED_REFRESH_TOKEN_RETENTION_DAYS + 5)
        db_old_revoked = RefreshToken(
            user_id=test_user.id,
            token_hash=hash_refresh_token(old_revoked_token),
            expires_at=old_revoked_expires,
            is_revoked=True,
            revoked_at=old_revoked_revoked_at,
        )
        test_db.add(db_old_revoked)

        old_used_token = "old-used-reset-1"
        old_used_expires = datetime.now(timezone.utc) + timedelta(minutes=15)
        old_used_used_at = datetime.now(timezone.utc) - timedelta(days=settings.USED_RESET_TOKEN_RETENTION_DAYS + 5)
        db_old_used = PasswordResetToken(
            user_id=test_user.id,
            token_hash=hash_reset_token(old_used_token),
            expires_at=old_used_expires,
            is_used=True,
            used_at=old_used_used_at,
        )
        test_db.add(db_old_used)

        old_expired_unused_token = "old-expired-unused-reset-1"
        old_expired_unused_expires = datetime.now(timezone.utc) - timedelta(days=settings.EXPIRED_RESET_TOKEN_RETENTION_DAYS + 5)
        db_old_expired_unused = PasswordResetToken(
            user_id=test_user.id,
            token_hash=hash_reset_token(old_expired_unused_token),
            expires_at=old_expired_unused_expires,
            is_used=False,
        )
        test_db.add(db_old_expired_unused)

        test_db.commit()

        # Verify initial state - should have 1 refresh token and 2 reset tokens
        initial_refresh = len(test_db.execute(select(RefreshToken)).scalars().all())
        initial_reset = len(test_db.execute(select(PasswordResetToken)).scalars().all())
        assert initial_refresh == 1
        assert initial_reset == 2

        # Run dry-run
        results = cleanup_auth_artifacts(test_db, dry_run=True, verbose=False)

        assert results["revoked_refresh_tokens"] == 1
        assert results["used_reset_tokens"] == 1
        assert results["expired_unused_reset_tokens"] == 1

        # Verify nothing was actually deleted
        refresh_count = len(test_db.execute(select(RefreshToken)).scalars().all())
        reset_count = len(test_db.execute(select(PasswordResetToken)).scalars().all())
        assert refresh_count == initial_refresh
        assert reset_count == initial_reset

    def test_cleanup_auth_artifacts_actual_deletion(self, test_db, test_user):
        """cleanup_auth_artifacts actually deletes tokens when not in dry-run mode."""
        # Create tokens that would be cleaned up
        old_revoked_token = create_refresh_token(subject=test_user.id, token_id="old-revoked-1")
        old_revoked_expires = datetime.now(timezone.utc) + timedelta(days=7)
        old_revoked_revoked_at = datetime.now(timezone.utc) - timedelta(days=settings.REVOKED_REFRESH_TOKEN_RETENTION_DAYS + 5)
        db_old_revoked = RefreshToken(
            user_id=test_user.id,
            token_hash=hash_refresh_token(old_revoked_token),
            expires_at=old_revoked_expires,
            is_revoked=True,
            revoked_at=old_revoked_revoked_at,
        )
        test_db.add(db_old_revoked)

        old_used_token = "old-used-reset-1"
        old_used_expires = datetime.now(timezone.utc) + timedelta(minutes=15)
        old_used_used_at = datetime.now(timezone.utc) - timedelta(days=settings.USED_RESET_TOKEN_RETENTION_DAYS + 5)
        db_old_used = PasswordResetToken(
            user_id=test_user.id,
            token_hash=hash_reset_token(old_used_token),
            expires_at=old_used_expires,
            is_used=True,
            used_at=old_used_used_at,
        )
        test_db.add(db_old_used)

        old_expired_unused_token = "old-expired-unused-reset-1"
        old_expired_unused_expires = datetime.now(timezone.utc) - timedelta(days=settings.EXPIRED_RESET_TOKEN_RETENTION_DAYS + 5)
        db_old_expired_unused = PasswordResetToken(
            user_id=test_user.id,
            token_hash=hash_reset_token(old_expired_unused_token),
            expires_at=old_expired_unused_expires,
            is_used=False,
        )
        test_db.add(db_old_expired_unused)

        test_db.commit()

        # Run actual cleanup
        results = cleanup_auth_artifacts(test_db, dry_run=False, verbose=False)

        assert results["revoked_refresh_tokens"] == 1
        assert results["used_reset_tokens"] == 1
        assert results["expired_unused_reset_tokens"] == 1

        # Verify tokens were actually deleted
        refresh_count = len(test_db.execute(select(RefreshToken)).scalars().all())
        reset_count = len(test_db.execute(select(PasswordResetToken)).scalars().all())
        assert refresh_count == 0
        assert reset_count == 0

    def test_cleanup_auth_artifacts_preserves_valid_tokens(self, test_db, test_user):
        """cleanup_auth_artifacts preserves valid (non-expired, non-revoked, etc.) tokens."""
        # Create valid tokens that should NOT be deleted
        valid_refresh_token = create_refresh_token(subject=test_user.id, token_id="valid-refresh-1")
        valid_refresh_expires = datetime.now(timezone.utc) + timedelta(days=7)
        db_valid_refresh = RefreshToken(
            user_id=test_user.id,
            token_hash=hash_refresh_token(valid_refresh_token),
            expires_at=valid_refresh_expires,
            is_revoked=False,
        )
        test_db.add(db_valid_refresh)

        valid_unused_token = "valid-unused-reset-1"
        valid_unused_expires = datetime.now(timezone.utc) + timedelta(minutes=15)
        db_valid_unused = PasswordResetToken(
            user_id=test_user.id,
            token_hash=hash_reset_token(valid_unused_token),
            expires_at=valid_unused_expires,
            is_used=False,
        )
        test_db.add(db_valid_unused)

        recent_revoked_token = create_refresh_token(subject=test_user.id, token_id="recent-revoked-1")
        recent_revoked_expires = datetime.now(timezone.utc) + timedelta(days=7)
        recent_revoked_revoked_at = datetime.now(timezone.utc) - timedelta(days=5)
        db_recent_revoked = RefreshToken(
            user_id=test_user.id,
            token_hash=hash_refresh_token(recent_revoked_token),
            expires_at=recent_revoked_expires,
            is_revoked=True,
            revoked_at=recent_revoked_revoked_at,
        )
        test_db.add(db_recent_revoked)

        recent_used_token = "recent-used-reset-1"
        recent_used_expires = datetime.now(timezone.utc) + timedelta(minutes=15)
        recent_used_used_at = datetime.now(timezone.utc) - timedelta(days=5)
        db_recent_used = PasswordResetToken(
            user_id=test_user.id,
            token_hash=hash_reset_token(recent_used_token),
            expires_at=recent_used_expires,
            is_used=True,
            used_at=recent_used_used_at,
        )
        test_db.add(db_recent_used)

        test_db.commit()

        # Run actual cleanup
        results = cleanup_auth_artifacts(test_db, dry_run=False, verbose=False)

        assert results["revoked_refresh_tokens"] == 0
        assert results["used_reset_tokens"] == 0
        assert results["expired_unused_reset_tokens"] == 0
        assert results["expired_unrevoked_refresh_tokens"] == 0

        # Verify all tokens preserved
        refresh_count = len(test_db.execute(select(RefreshToken)).scalars().all())
        reset_count = len(test_db.execute(select(PasswordResetToken)).scalars().all())
        assert refresh_count == 2
        assert reset_count == 2

    def test_cleanup_auth_artifacts_dry_run_includes_expired_unrevoked(self, test_db, test_user):
        """cleanup_auth_artifacts dry_run reports expired unrevoked refresh tokens."""
        # Create old expired unrevoked token
        old_expired_unrevoked = create_refresh_token(subject=test_user.id, token_id="old-expired-unrevoked-1")
        old_expired_unrevoked_expires = datetime.now(timezone.utc) - timedelta(days=settings.EXPIRED_UNREVOKED_REFRESH_TOKEN_RETENTION_DAYS + 5)
        db_old_expired_unrevoked = RefreshToken(
            user_id=test_user.id,
            token_hash=hash_refresh_token(old_expired_unrevoked),
            expires_at=old_expired_unrevoked_expires,
            is_revoked=False,
        )
        test_db.add(db_old_expired_unrevoked)
        test_db.commit()

        # Run dry-run
        results = cleanup_auth_artifacts(test_db, dry_run=True, verbose=False)

        assert results["expired_unrevoked_refresh_tokens"] == 1

        # Verify nothing was actually deleted
        refresh_count = len(test_db.execute(select(RefreshToken)).scalars().all())
        assert refresh_count == 1

    def test_cleanup_auth_artifacts_actual_deletion_includes_expired_unrevoked(self, test_db, test_user):
        """cleanup_auth_artifacts actually deletes expired unrevoked refresh tokens."""
        # Create old expired unrevoked token
        old_expired_unrevoked = create_refresh_token(subject=test_user.id, token_id="old-expired-unrevoked-1")
        old_expired_unrevoked_expires = datetime.now(timezone.utc) - timedelta(days=settings.EXPIRED_UNREVOKED_REFRESH_TOKEN_RETENTION_DAYS + 5)
        db_old_expired_unrevoked = RefreshToken(
            user_id=test_user.id,
            token_hash=hash_refresh_token(old_expired_unrevoked),
            expires_at=old_expired_unrevoked_expires,
            is_revoked=False,
        )
        test_db.add(db_old_expired_unrevoked)
        test_db.commit()

        # Run actual cleanup
        results = cleanup_auth_artifacts(test_db, dry_run=False, verbose=False)

        assert results["expired_unrevoked_refresh_tokens"] == 1

        # Verify token was deleted
        refresh_count = len(test_db.execute(select(RefreshToken)).scalars().all())
        assert refresh_count == 0


class TestCleanupConfigurationValidators:
    """Tests for cleanup configuration validators."""

    def test_revoked_refresh_token_retention_validator_positive(self):
        """REVOKED_REFRESH_TOKEN_RETENTION_DAYS accepts positive values."""
        from app.core.config import Settings
        import os

        os.environ["SECRET_KEY"] = "test"
        os.environ["REVOKED_REFRESH_TOKEN_RETENTION_DAYS"] = "30"
        os.environ["USED_RESET_TOKEN_RETENTION_DAYS"] = "30"
        os.environ["EXPIRED_RESET_TOKEN_RETENTION_DAYS"] = "7"
        os.environ["EXPIRED_UNREVOKED_REFRESH_TOKEN_RETENTION_DAYS"] = "7"
        os.environ["AUTH_CLEANUP_BATCH_SIZE"] = "500"
        settings = Settings()
        assert settings.REVOKED_REFRESH_TOKEN_RETENTION_DAYS == 30

    def test_revoked_refresh_token_retention_validator_zero(self):
        """REVOKED_REFRESH_TOKEN_RETENTION_DAYS accepts zero."""
        from app.core.config import Settings
        import os

        os.environ["SECRET_KEY"] = "test"
        os.environ["REVOKED_REFRESH_TOKEN_RETENTION_DAYS"] = "0"
        os.environ["USED_RESET_TOKEN_RETENTION_DAYS"] = "30"
        os.environ["EXPIRED_RESET_TOKEN_RETENTION_DAYS"] = "7"
        os.environ["EXPIRED_UNREVOKED_REFRESH_TOKEN_RETENTION_DAYS"] = "7"
        os.environ["AUTH_CLEANUP_BATCH_SIZE"] = "500"
        settings = Settings()
        assert settings.REVOKED_REFRESH_TOKEN_RETENTION_DAYS == 0

    def test_revoked_refresh_token_retention_validator_negative_fails(self):
        """REVOKED_REFRESH_TOKEN_RETENTION_DAYS rejects negative values."""
        from app.core.config import Settings
        import os

        os.environ["SECRET_KEY"] = "test"
        os.environ["REVOKED_REFRESH_TOKEN_RETENTION_DAYS"] = "-1"
        try:
            Settings()
            assert False, "Expected ValueError"
        except ValueError as e:
            assert "REVOKED_REFRESH_TOKEN_RETENTION_DAYS must be non-negative" in str(e)

    def test_used_reset_token_retention_validator_negative_fails(self):
        """USED_RESET_TOKEN_RETENTION_DAYS rejects negative values."""
        from app.core.config import Settings
        import os

        os.environ["SECRET_KEY"] = "test"
        os.environ["USED_RESET_TOKEN_RETENTION_DAYS"] = "-1"
        try:
            Settings()
            assert False, "Expected ValueError"
        except ValueError as e:
            assert "USED_RESET_TOKEN_RETENTION_DAYS must be non-negative" in str(e)

    def test_expired_reset_token_retention_validator_negative_fails(self):
        """EXPIRED_RESET_TOKEN_RETENTION_DAYS rejects negative values."""
        from app.core.config import Settings
        import os

        os.environ["SECRET_KEY"] = "test"
        os.environ["EXPIRED_RESET_TOKEN_RETENTION_DAYS"] = "-1"
        try:
            Settings()
            assert False, "Expected ValueError"
        except ValueError as e:
            assert "EXPIRED_RESET_TOKEN_RETENTION_DAYS must be non-negative" in str(e)

    def test_expired_unrevoked_refresh_token_retention_validator_negative_fails(self):
        """EXPIRED_UNREVOKED_REFRESH_TOKEN_RETENTION_DAYS rejects negative values."""
        from app.core.config import Settings
        import os

        os.environ["SECRET_KEY"] = "test"
        os.environ["EXPIRED_UNREVOKED_REFRESH_TOKEN_RETENTION_DAYS"] = "-1"
        try:
            Settings()
            assert False, "Expected ValueError"
        except ValueError as e:
            assert "EXPIRED_UNREVOKED_REFRESH_TOKEN_RETENTION_DAYS must be non-negative" in str(e)

    def test_auth_cleanup_batch_size_validator_positive(self):
        """AUTH_CLEANUP_BATCH_SIZE accepts positive values."""
        from app.core.config import Settings
        import os

        os.environ["SECRET_KEY"] = "test"
        os.environ["REVOKED_REFRESH_TOKEN_RETENTION_DAYS"] = "30"
        os.environ["USED_RESET_TOKEN_RETENTION_DAYS"] = "30"
        os.environ["EXPIRED_RESET_TOKEN_RETENTION_DAYS"] = "7"
        os.environ["EXPIRED_UNREVOKED_REFRESH_TOKEN_RETENTION_DAYS"] = "7"
        os.environ["AUTH_CLEANUP_BATCH_SIZE"] = "500"
        settings = Settings()
        assert settings.AUTH_CLEANUP_BATCH_SIZE == 500

    def test_auth_cleanup_batch_size_validator_zero_fails(self):
        """AUTH_CLEANUP_BATCH_SIZE rejects zero."""
        from app.core.config import Settings
        import os

        os.environ["SECRET_KEY"] = "test"
        os.environ["AUTH_CLEANUP_BATCH_SIZE"] = "0"
        try:
            Settings()
            assert False, "Expected ValueError"
        except ValueError as e:
            assert "AUTH_CLEANUP_BATCH_SIZE must be positive" in str(e)

    def test_auth_cleanup_batch_size_validator_negative_fails(self):
        """AUTH_CLEANUP_BATCH_SIZE rejects negative values."""
        from app.core.config import Settings
        import os

        os.environ["SECRET_KEY"] = "test"
        os.environ["AUTH_CLEANUP_BATCH_SIZE"] = "-1"
        try:
            Settings()
            assert False, "Expected ValueError"
        except ValueError as e:
            assert "AUTH_CLEANUP_BATCH_SIZE must be positive" in str(e)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])