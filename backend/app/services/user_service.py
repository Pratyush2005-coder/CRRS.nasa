"""Service layer for User authentication and management."""

from datetime import datetime, timezone, timedelta
from typing import Optional, List
from sqlalchemy import select, delete
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import (
    hash_password,
    verify_password,
    create_refresh_token,
    rotate_refresh_token,
    decode_refresh_token,
    InvalidTokenError,
    TokenExpiredError,
)
from app.models.user import User
from app.models.refresh_token import RefreshToken, hash_token as hash_refresh_token
from app.models.password_reset_token import PasswordResetToken, hash_token as hash_reset_token
from app.models.login_attempt import LoginAttempt
from app.schemas.user import UserCreate


class UserService:
    """Service handling user business logic and database interactions."""

    def get_user_by_email(self, db: Session, email: str) -> Optional[User]:
        """Fetch a user by email (case-insensitive)."""
        normalized_email = email.strip().lower()
        return db.execute(
            select(User).where(User.email == normalized_email)
        ).scalar_one_or_none()

    def get_user_by_id(self, db: Session, user_id: str) -> Optional[User]:
        """Fetch a user by UUID."""
        return db.execute(
            select(User).where(User.id == user_id)
        ).scalar_one_or_none()

    def create_user(self, db: Session, user_in: UserCreate) -> User:
        """Create and persist a new user with hashed password.

        Args:
            db: Database session.
            user_in: Validated user creation data.

        Returns:
            Created User object.

        Raises:
            ValueError: If email already exists.
        """
        normalized_email = user_in.email.strip().lower()

        # Check for existing user (prevents race condition in most cases)
        existing = self.get_user_by_email(db, normalized_email)
        if existing:
            raise ValueError("Email already registered")

        # Hash password
        hashed_password = hash_password(user_in.password)

        # Create user with server-side defaults
        db_user = User(
            email=normalized_email,
            hashed_password=hashed_password,
            role="user",  # Default role assigned server-side
            is_active=True,  # Default active status
        )

        try:
            db.add(db_user)
            db.commit()
            db.refresh(db_user)
            return db_user
        except IntegrityError:
            db.rollback()
            # Race condition: another request inserted the same email
            raise ValueError("Email already registered")

    def authenticate_user(self, db: Session, email: str, password: str) -> Optional[User]:
        """Authenticate a user by email and password.

        Args:
            db: Database session.
            email: User email (will be normalized).
            password: Plaintext password to verify.

        Returns:
            User object if authentication succeeds, None otherwise.
        """
        user = self.get_user_by_email(db, email)
        if not user:
            return None

        # Reject inactive users
        if not user.is_active:
            return None

        # Verify password
        if not verify_password(password, user.hashed_password):
            return None

        return user

    def store_refresh_token(
        self,
        db: Session,
        user_id: str,
        token: str,
        expires_at: datetime,
        session_id: str | None = None,
        device_info: str | None = None,
        ip_address: str | None = None,
    ) -> RefreshToken:
        """Store a refresh token hash in the database.

        Args:
            db: Database session.
            user_id: User identifier.
            token: Raw refresh token (will be hashed before storage).
            expires_at: Token expiration timestamp.
            session_id: Optional stable session identifier for device tracking.
            device_info: Optional client device/browser information.
            ip_address: Optional client IP address.

        Returns:
            Created RefreshToken object.
        """
        token_hash = hash_refresh_token(token)
        refresh_token = RefreshToken(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
            is_revoked=False,
            session_id=session_id,
            device_info=device_info,
            ip_address=ip_address,
            last_used_at=datetime.now(timezone.utc),
        )
        db.add(refresh_token)
        db.commit()
        db.refresh(refresh_token)
        return refresh_token

    def validate_and_rotate_refresh_token(
        self,
        db: Session,
        token: str,
    ) -> tuple[str, str, RefreshToken]:
        """Validate a refresh token and rotate it (invalidate old, create new).

        This implements secure refresh token rotation:
        1. Decode and validate the JWT
        2. Look up the token hash in database with row lock for concurrency safety
        3. Check if token is revoked or expired
        4. Mark old token as revoked
        5. Create and store new refresh token (preserving session_id)
        6. Return new access token, new refresh token, and new RefreshToken record

        Args:
            db: Database session.
            token: Raw refresh token from client.

        Returns:
            Tuple of (new_access_token, new_refresh_token, new_refresh_token_record).

        Raises:
            InvalidTokenError: If token is invalid, revoked, reused, or malformed.
            TokenExpiredError: If token has expired.
        """
        # Decode and validate the JWT
        try:
            payload = decode_refresh_token(token)
        except TokenExpiredError:
            raise
        except InvalidTokenError:
            raise InvalidTokenError("Invalid refresh token")

        user_id = payload.get("sub")
        old_token_id = payload.get("jti")

        if not user_id:
            raise InvalidTokenError("Invalid refresh token: missing subject")

        # Look up the token in database with row-level lock for concurrent safety
        # Note: SQLite does not support SELECT FOR UPDATE; this is effective for PostgreSQL
        # In SQLite, the UNIQUE constraint on token_hash + transaction isolation provides safety
        token_hash = hash_refresh_token(token)
        db_token = db.execute(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash).with_for_update()
        ).scalar_one_or_none()

        if not db_token:
            # Token not found in database - possible replay attack or already rotated
            raise InvalidTokenError("Invalid refresh token: token not found or already used")

        # Check if token is revoked
        if db_token.is_revoked:
            # Token was already used (rotation replay attack) - revoke all user tokens for security
            self._revoke_all_user_tokens(db, user_id)
            raise InvalidTokenError("Invalid refresh token: token already used (possible replay attack)")

        # Check if token is expired (database-level check)
        now = datetime.now(timezone.utc)
        # Handle both naive and aware datetimes for SQLite compatibility
        expires_at = db_token.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at <= now:
            raise TokenExpiredError("Refresh token has expired")

        # Check if user exists and is active
        user = self.get_user_by_id(db, user_id)
        if not user or not user.is_active:
            raise InvalidTokenError("Invalid refresh token: user not found or inactive")

        # Preserve session_id for session continuity across token rotations
        session_id = db_token.session_id
        device_info = db_token.device_info
        ip_address = db_token.ip_address

        # Rotate: mark old token as revoked
        db_token.is_revoked = True
        db_token.revoked_at = now

        # Create new refresh token with new JTI
        import uuid
        new_token_id = str(uuid.uuid4())
        expires_delta = timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        new_refresh_token = create_refresh_token(
            subject=user_id,
            expires_delta=expires_delta,
            token_id=new_token_id,
        )

        # Store new token in database with preserved session metadata
        new_expires_at = now + expires_delta
        new_db_token = RefreshToken(
            user_id=user_id,
            token_hash=hash_refresh_token(new_refresh_token),
            expires_at=new_expires_at,
            is_revoked=False,
            session_id=session_id,
            device_info=device_info,
            ip_address=ip_address,
            last_used_at=now,
        )
        db.add(new_db_token)

        # Create new access token with session_id
        from app.core.security import create_access_token
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        new_access_token = create_access_token(
            subject=user_id,
            expires_delta=access_token_expires,
            session_id=session_id,
        )

        db.commit()
        db.refresh(new_db_token)

        return new_access_token, new_refresh_token, new_db_token

    def _revoke_all_user_tokens(self, db: Session, user_id: str) -> None:
        """Revoke all refresh tokens for a user (security measure).

        Called when a replay attack is detected.

        Args:
            db: Database session.
            user_id: User identifier.
        """
        now = datetime.now(timezone.utc)
        tokens = db.execute(
            select(RefreshToken)
            .where(RefreshToken.user_id == user_id)
            .where(RefreshToken.is_revoked == False)
        ).scalars().all()

        for token in tokens:
            token.is_revoked = True
            token.revoked_at = now

        if tokens:
            db.commit()

    def revoke_refresh_token(self, db: Session, token: str) -> bool:
        """Revoke a specific refresh token (logout).

        Args:
            db: Database session.
            token: Raw refresh token to revoke.

        Returns:
            True if token was found and revoked, False otherwise.
        """
        token_hash = hash_refresh_token(token)
        db_token = db.execute(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        ).scalar_one_or_none()

        if not db_token or db_token.is_revoked:
            return False

        db_token.is_revoked = True
        db_token.revoked_at = datetime.now(timezone.utc)
        db.commit()
        return True

    def revoke_all_user_tokens(self, db: Session, user_id: str) -> int:
        """Revoke all refresh tokens for a user.

        Args:
            db: Database session.
            user_id: User identifier.

        Returns:
            Number of tokens revoked.
        """
        now = datetime.now(timezone.utc)
        tokens = db.execute(
            select(RefreshToken)
            .where(RefreshToken.user_id == user_id)
            .where(RefreshToken.is_revoked == False)
        ).scalars().all()

        count = 0
        for token in tokens:
            token.is_revoked = True
            token.revoked_at = now
            count += 1

        if count > 0:
            db.commit()

        return count

    def cleanup_expired_tokens(self, db: Session) -> int:
        """Remove expired revoked tokens from database (maintenance).

        Args:
            db: Database session.

        Returns:
            Number of tokens removed.
        """
        now = datetime.now(timezone.utc)
        result = db.execute(
            delete(RefreshToken).where(
                RefreshToken.is_revoked == True,
                RefreshToken.revoked_at < now - timedelta(days=30)
            )
        )
        db.commit()
        return result.rowcount

    # ==================== Session Management Methods ====================

    def get_user_sessions(self, db: Session, user_id: str) -> List[RefreshToken]:
        """Get all active (non-revoked, non-expired) sessions for a user.

        Returns tokens grouped by session_id with the most recent token per session.

        Args:
            db: Database session.
            user_id: User identifier.

        Returns:
            List of RefreshToken objects representing active sessions.
        """
        now = datetime.now(timezone.utc)

        # Get all non-revoked, non-expired tokens for the user
        tokens = db.execute(
            select(RefreshToken)
            .where(RefreshToken.user_id == user_id)
            .where(RefreshToken.is_revoked == False)
            .where(RefreshToken.expires_at > now)
            .order_by(RefreshToken.session_id, RefreshToken.created_at.desc())
        ).scalars().all()

        # Group by session_id, keeping the most recent token per session
        sessions = {}
        for token in tokens:
            session_id = token.session_id or token.id
            if session_id not in sessions:
                sessions[session_id] = token

        # Sort by last_used_at descending (most recently used first)
        return sorted(sessions.values(), key=lambda t: t.last_used_at or t.created_at, reverse=True)

    def get_session_by_id(self, db: Session, user_id: str, session_id: str) -> Optional[RefreshToken]:
        """Get a specific session by session_id for a user.

        Args:
            db: Database session.
            user_id: User identifier.
            session_id: Session identifier to look up.

        Returns:
            RefreshToken if found and belongs to user, None otherwise.
        """
        now = datetime.now(timezone.utc)

        # Find the most recent non-revoked, non-expired token with this session_id
        token = db.execute(
            select(RefreshToken)
            .where(RefreshToken.user_id == user_id)
            .where(RefreshToken.session_id == session_id)
            .where(RefreshToken.is_revoked == False)
            .where(RefreshToken.expires_at > now)
            .order_by(RefreshToken.created_at.desc())
        ).scalar_one_or_none()

        return token

    def revoke_session(self, db: Session, user_id: str, session_id: str) -> bool:
        """Revoke a specific session (all tokens in that session) for a user.

        Args:
            db: Database session.
            user_id: User identifier.
            session_id: Session identifier to revoke.

        Returns:
            True if session was found and revoked, False otherwise.
        """
        now = datetime.now(timezone.utc)

        # Find all non-revoked tokens with this session_id for the user
        tokens = db.execute(
            select(RefreshToken)
            .where(RefreshToken.user_id == user_id)
            .where(RefreshToken.session_id == session_id)
            .where(RefreshToken.is_revoked == False)
        ).scalars().all()

        if not tokens:
            return False

        count = 0
        for token in tokens:
            token.is_revoked = True
            token.revoked_at = now
            count += 1

        if count > 0:
            db.commit()

        return True

    def update_session_last_used(self, db: Session, token: str) -> bool:
        """Update the last_used_at timestamp for a refresh token.

        Called when a refresh token is used for token rotation.

        Args:
            db: Database session.
            token: Raw refresh token.

        Returns:
            True if token was found and updated, False otherwise.
        """
        token_hash = hash_refresh_token(token)
        db_token = db.execute(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        ).scalar_one_or_none()

        if not db_token:
            return False

        db_token.last_used_at = datetime.now(timezone.utc)
        db.commit()
        return True

    # ==================== Password Reset Methods ====================

    def create_password_reset_token(
        self,
        db: Session,
        user_id: str,
        token: str,
        expires_at: datetime,
    ) -> PasswordResetToken:
        """Store a password reset token hash in the database.

        Args:
            db: Database session.
            user_id: User identifier.
            token: Raw reset token (will be hashed before storage).
            expires_at: Token expiration timestamp.

        Returns:
            Created PasswordResetToken object.
        """
        token_hash = hash_reset_token(token)
        reset_token = PasswordResetToken(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
            is_used=False,
        )
        db.add(reset_token)
        db.commit()
        db.refresh(reset_token)
        return reset_token

    def validate_and_consume_reset_token(
        self,
        db: Session,
        token: str,
    ) -> PasswordResetToken:
        """Validate a password reset token and mark it as consumed (single-use).

        Args:
            db: Database session.
            token: Raw reset token from client.

        Returns:
            The validated PasswordResetToken object.

        Raises:
            InvalidTokenError: If token is invalid, already used, or malformed.
            TokenExpiredError: If token has expired.
        """
        # Hash the token to look it up
        token_hash = hash_reset_token(token)

        # Look up the token in database with row-level lock for concurrent safety
        db_token = db.execute(
            select(PasswordResetToken)
            .where(PasswordResetToken.token_hash == token_hash)
            .with_for_update()
        ).scalar_one_or_none()

        if not db_token:
            raise InvalidTokenError("Invalid or expired reset token")

        # Check if token is already used
        if db_token.is_used:
            raise InvalidTokenError("Reset token has already been used")

        # Check if token is expired
        now = datetime.now(timezone.utc)
        expires_at = db_token.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at <= now:
            raise TokenExpiredError("Reset token has expired")

        # Verify user exists and is active
        user = self.get_user_by_id(db, db_token.user_id)
        if not user or not user.is_active:
            raise InvalidTokenError("Invalid or expired reset token")

        # Mark token as used atomically
        db_token.is_used = True
        db_token.used_at = now
        db.commit()
        db.refresh(db_token)

        return db_token

    def reset_password(
        self,
        db: Session,
        token: str,
        new_password: str,
    ) -> bool:
        """Reset user password using a valid reset token.

        This method:
        1. Validates and consumes the reset token (single-use)
        2. Hashes the new password
        3. Updates the user's password
        4. Revokes all active refresh tokens for the user (security measure)
        5. Cleans up any other unused reset tokens for the user

        Args:
            db: Database session.
            token: Raw reset token from client.
            new_password: New plaintext password.

        Returns:
            True if password was successfully reset.

        Raises:
            InvalidTokenError: If token is invalid, already used, or malformed.
            TokenExpiredError: If token has expired.
            ValueError: If new password is empty.
        """
        if not new_password or not new_password.strip():
            raise ValueError("New password cannot be empty")

        # Validate and consume the reset token
        db_token = self.validate_and_consume_reset_token(db, token)

        # Hash the new password
        hashed_password = hash_password(new_password)

        # Update user's password
        user = self.get_user_by_id(db, db_token.user_id)
        user.hashed_password = hashed_password
        user.updated_at = datetime.now(timezone.utc)

        # Revoke all refresh tokens for this user (security: invalidate all sessions)
        self.revoke_all_user_tokens(db, user.id)

        # Clean up any other unused reset tokens for this user
        self._cleanup_user_reset_tokens(db, user.id)

        db.commit()
        return True

    def _cleanup_user_reset_tokens(self, db: Session, user_id: str) -> int:
        """Remove all unused reset tokens for a user after successful reset.

        Args:
            db: Database session.
            user_id: User identifier.

        Returns:
            Number of tokens removed.
        """
        result = db.execute(
            delete(PasswordResetToken).where(
                PasswordResetToken.user_id == user_id,
                PasswordResetToken.is_used == False,
            )
        )
        return result.rowcount

    def cleanup_expired_reset_tokens(self, db: Session) -> int:
        """Remove expired reset tokens from database (maintenance).

        Args:
            db: Database session.

        Returns:
            Number of tokens removed.
        """
        now = datetime.now(timezone.utc)
        result = db.execute(
            delete(PasswordResetToken).where(
                PasswordResetToken.expires_at < now,
            )
        )
        db.commit()
        return result.rowcount

    def cleanup_revoked_refresh_tokens(self, db: Session) -> int:
        """Remove revoked refresh tokens older than retention period.

        Args:
            db: Database session.

        Returns:
            Number of tokens removed.
        """
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(days=settings.REVOKED_REFRESH_TOKEN_RETENTION_DAYS)
        # Store cutoff as naive datetime to match database storage format
        cutoff_naive = cutoff.replace(tzinfo=None)

        total_deleted = 0
        batch_size = settings.AUTH_CLEANUP_BATCH_SIZE

        while True:
            # Select IDs of eligible tokens in batches
            token_ids = db.execute(
                select(RefreshToken.id).where(
                    RefreshToken.is_revoked == True,
                    RefreshToken.revoked_at < cutoff_naive,
                ).limit(batch_size)
            ).scalars().all()

            if not token_ids:
                break

            # Delete the selected tokens
            result = db.execute(
                delete(RefreshToken).where(RefreshToken.id.in_(token_ids))
            )
            db.commit()
            total_deleted += result.rowcount

            # If we deleted fewer than batch_size, we're done
            if result.rowcount < batch_size:
                break

        return total_deleted

    def cleanup_used_reset_tokens(self, db: Session) -> int:
        """Remove used password reset tokens older than retention period.

        Args:
            db: Database session.

        Returns:
            Number of tokens removed.
        """
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(days=settings.USED_RESET_TOKEN_RETENTION_DAYS)
        # Store cutoff as naive datetime to match database storage format
        cutoff_naive = cutoff.replace(tzinfo=None)

        total_deleted = 0
        batch_size = settings.AUTH_CLEANUP_BATCH_SIZE

        while True:
            # Select IDs of eligible tokens in batches
            token_ids = db.execute(
                select(PasswordResetToken.id).where(
                    PasswordResetToken.is_used == True,
                    PasswordResetToken.used_at < cutoff_naive,
                ).limit(batch_size)
            ).scalars().all()

            if not token_ids:
                break

            # Delete the selected tokens
            result = db.execute(
                delete(PasswordResetToken).where(PasswordResetToken.id.in_(token_ids))
            )
            db.commit()
            total_deleted += result.rowcount

            # If we deleted fewer than batch_size, we're done
            if result.rowcount < batch_size:
                break

        return total_deleted

    def cleanup_expired_unrevoked_refresh_tokens(self, db: Session) -> int:
        """Remove expired (unrevoked) refresh tokens older than retention period.

        Args:
            db: Database session.

        Returns:
            Number of tokens removed.
        """
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(days=settings.EXPIRED_UNREVOKED_REFRESH_TOKEN_RETENTION_DAYS)
        # Store cutoff as naive datetime to match database storage format
        cutoff_naive = cutoff.replace(tzinfo=None)

        total_deleted = 0
        batch_size = settings.AUTH_CLEANUP_BATCH_SIZE

        while True:
            # Select IDs of eligible tokens in batches
            token_ids = db.execute(
                select(RefreshToken.id).where(
                    RefreshToken.is_revoked == False,
                    RefreshToken.expires_at < cutoff_naive,
                ).limit(batch_size)
            ).scalars().all()

            if not token_ids:
                break

            # Delete the selected tokens
            result = db.execute(
                delete(RefreshToken).where(RefreshToken.id.in_(token_ids))
            )
            db.commit()
            total_deleted += result.rowcount

            # If we deleted fewer than batch_size, we're done
            if result.rowcount < batch_size:
                break

        return total_deleted

    def cleanup_expired_unused_reset_tokens(self, db: Session) -> int:
        """Remove expired (unused) password reset tokens older than retention period.

        Args:
            db: Database session.

        Returns:
            Number of tokens removed.
        """
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(days=settings.EXPIRED_RESET_TOKEN_RETENTION_DAYS)
        # Store cutoff as naive datetime to match database storage format
        cutoff_naive = cutoff.replace(tzinfo=None)

        total_deleted = 0
        batch_size = settings.AUTH_CLEANUP_BATCH_SIZE

        while True:
            # Select IDs of eligible tokens in batches
            token_ids = db.execute(
                select(PasswordResetToken.id).where(
                    PasswordResetToken.is_used == False,
                    PasswordResetToken.expires_at < cutoff_naive,
                ).limit(batch_size)
            ).scalars().all()

            if not token_ids:
                break

            # Delete the selected tokens
            result = db.execute(
                delete(PasswordResetToken).where(PasswordResetToken.id.in_(token_ids))
            )
            db.commit()
            total_deleted += result.rowcount

            # If we deleted fewer than batch_size, we're done
            if result.rowcount < batch_size:
                break

        return total_deleted

    # ==================== Account Lockout Methods ====================

    def check_login_attempts(self, db: Session, email: str, ip_address: str) -> tuple[bool, int, Optional[int]]:
        """Check if an email+IP combination is locked out due to failed login attempts.

        Implements sliding-window policy: counts failed attempts in the last
        LOGIN_ATTEMPT_WINDOW_MINUTES. If count >= LOGIN_ATTEMPT_MAX_ATTEMPTS,
        the account is locked for LOGIN_ATTEMPT_COOLDOWN_MINUTES.

        Args:
            db: Database session.
            email: Email address (will be normalized).
            ip_address: Client IP address.

        Returns:
            Tuple of (is_locked, failed_count, cooldown_remaining_minutes).
            - is_locked: True if currently locked out
            - failed_count: Number of failed attempts in current window
            - cooldown_remaining_minutes: Minutes remaining in lockout, or None if not locked
        """
        from app.models.login_attempt import LoginAttempt

        normalized_email = email.strip().lower()
        now = datetime.now(timezone.utc)
        window_start = now - timedelta(minutes=settings.LOGIN_ATTEMPT_WINDOW_MINUTES)

        # Count failed attempts in the sliding window
        failed_count = db.execute(
            select(LoginAttempt).where(
                LoginAttempt.email == normalized_email,
                LoginAttempt.ip_address == ip_address,
                LoginAttempt.success == False,
                LoginAttempt.attempted_at >= window_start,
            )
        ).scalars().all()

        count = len(failed_count)

        # Check if already locked out
        if count >= settings.LOGIN_ATTEMPT_MAX_ATTEMPTS:
            # Find the earliest failed attempt in the window to calculate cooldown
            earliest_attempt = min(failed_count, key=lambda a: a.attempted_at)
            lockout_until = earliest_attempt.attempted_at + timedelta(minutes=settings.LOGIN_ATTEMPT_COOLDOWN_MINUTES)
            if lockout_until.tzinfo is None:
                lockout_until = lockout_until.replace(tzinfo=timezone.utc)

            if now < lockout_until:
                cooldown_remaining = int((lockout_until - now).total_seconds() / 60) + 1
                return True, count, cooldown_remaining
            else:
                # Lockout period has expired
                return False, count, None

        return False, count, None

    def record_login_attempt(
        self,
        db: Session,
        email: str,
        ip_address: str,
        success: bool,
        user_agent: Optional[str] = None,
    ) -> LoginAttempt:
        """Record a login attempt (success or failure).

        Args:
            db: Database session.
            email: Email address (will be normalized).
            ip_address: Client IP address.
            success: Whether the login attempt succeeded.
            user_agent: Optional client user agent string.

        Returns:
            Created LoginAttempt record.
        """
        from app.models.login_attempt import LoginAttempt

        normalized_email = email.strip().lower()

        attempt = LoginAttempt(
            email=normalized_email,
            ip_address=ip_address,
            success=success,
            user_agent=user_agent,
        )
        db.add(attempt)
        db.commit()
        db.refresh(attempt)
        return attempt

    def cleanup_login_attempts(self, db: Session) -> int:
        """Remove old login attempt records beyond the lockout window.

        Keeps records for the window + cooldown period to ensure lockout
        enforcement works correctly, then deletes older records in batches.

        Args:
            db: Database session.

        Returns:
            Number of records removed.
        """
        from app.models.login_attempt import LoginAttempt

        now = datetime.now(timezone.utc)
        # Retain for window + cooldown + buffer to ensure lockout enforcement
        retention_minutes = (
            settings.LOGIN_ATTEMPT_WINDOW_MINUTES
            + settings.LOGIN_ATTEMPT_COOLDOWN_MINUTES
            + 60  # 1 hour buffer
        )
        cutoff = now - timedelta(minutes=retention_minutes)
        cutoff_naive = cutoff.replace(tzinfo=None)

        total_deleted = 0
        batch_size = settings.AUTH_CLEANUP_BATCH_SIZE

        while True:
            # Select IDs of eligible records in batches
            attempt_ids = db.execute(
                select(LoginAttempt.id).where(
                    LoginAttempt.attempted_at < cutoff_naive,
                ).limit(batch_size)
            ).scalars().all()

            if not attempt_ids:
                break

            # Delete the selected records
            result = db.execute(
                delete(LoginAttempt).where(LoginAttempt.id.in_(attempt_ids))
            )
            db.commit()
            total_deleted += result.rowcount

            # If we deleted fewer than batch_size, we're done
            if result.rowcount < batch_size:
                break

        return total_deleted


user_service = UserService()