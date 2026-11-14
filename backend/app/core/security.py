"""Security utilities for password hashing and JWT token management."""

import time
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from jwt import PyJWTError as JWTError, ExpiredSignatureError, ImmatureSignatureError, InvalidIssuedAtError
from jwt.exceptions import InvalidSubjectError as PyJWTInvalidSubjectError
from passlib.context import CryptContext

from app.core.config import settings


# Password hashing context using pbkdf2_sha256 with explicit rounds
# OWASP recommends 600,000 iterations for PBKDF2-HMAC-SHA256 (2024)
# This avoids the bcrypt 72-byte limit and passlib/bcrypt 4.0+ compatibility issues.
# pbkdf2_sha256 is a NIST-approved password hashing algorithm with configurable rounds.
PBKDF2_ROUNDS = 600_000

pwd_context = CryptContext(
    schemes=["pbkdf2_sha256"],
    default="pbkdf2_sha256",
    pbkdf2_sha256__rounds=PBKDF2_ROUNDS,
    deprecated="auto",
)


class TokenType:
    """Token type constants to distinguish access and refresh tokens."""

    ACCESS = "access"
    REFRESH = "refresh"


# Maximum allowed length for JWT subject claim
MAX_SUBJECT_LENGTH = 256

# Clock skew tolerance for iat validation (seconds)
IAT_CLOCK_SKEW_TOLERANCE = 30


class SecurityError(Exception):
    """Base exception for security-related errors."""

    pass


class TokenExpiredError(SecurityError):
    """Raised when a token has expired."""

    pass


class InvalidTokenError(SecurityError):
    """Raised when a token is invalid, malformed, or has wrong signature."""

    pass


class InvalidTokenTypeError(InvalidTokenError):
    """Raised when a token type doesn't match expected type."""

    pass


class InvalidSubjectError(SecurityError):
    """Raised when a token subject is invalid."""

    pass


class MissingSecretKeyError(SecurityError):
    """Raised when SECRET_KEY is not configured."""

    pass


def _validate_secret_key() -> None:
    """Validate that SECRET_KEY is configured.

    Raises:
        MissingSecretKeyError: If SECRET_KEY is not set or is empty.
    """
    if not settings.SECRET_KEY or not settings.SECRET_KEY.strip():
        raise MissingSecretKeyError(
            "SECRET_KEY is not configured. "
            "Set the SECRET_KEY environment variable for authentication to work."
        )


def _validate_subject(subject: str) -> None:
    """Validate JWT subject claim.

    Args:
        subject: Subject string to validate.

    Raises:
        InvalidSubjectError: If subject is empty, whitespace-only, or too long.
    """
    if not subject or not subject.strip():
        raise InvalidSubjectError("Subject cannot be empty or whitespace-only")
    if len(subject) > MAX_SUBJECT_LENGTH:
        raise InvalidSubjectError(
            f"Subject exceeds maximum length of {MAX_SUBJECT_LENGTH} characters"
        )


def _validate_iat(iat: int) -> None:
    """Validate issued-at timestamp against clock skew.

    Args:
        iat: Unix timestamp from token's 'iat' claim.

    Raises:
        InvalidTokenError: If iat is significantly in the future.
    """
    now = int(datetime.now(timezone.utc).timestamp())
    if iat > now + IAT_CLOCK_SKEW_TOLERANCE:
        raise InvalidTokenError(
            f"Token issued in the future (iat={iat}, now={now}, "
            f"skew tolerance={IAT_CLOCK_SKEW_TOLERANCE}s)"
        )


def hash_password(password: str) -> str:
    """Hash a plaintext password using pbkdf2_sha256 with 600,000 rounds.

    Args:
        password: Plaintext password to hash.

    Returns:
        PBKDF2-SHA256 hashed password string.

    Raises:
        ValueError: If password is empty or None.
        SecurityError: If hashing fails.
    """
    if not password:
        raise ValueError("Password cannot be empty")

    try:
        # pbkdf2_sha256 handles passwords of any length
        # Uses configured 600,000 rounds per OWASP 2024 recommendation
        hashed = pwd_context.hash(password)
        return hashed
    except Exception as e:
        raise SecurityError(f"Password hashing failed: {type(e).__name__}") from e


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against a pbkdf2_sha256 hash.

    Compatible with hashes generated with different round counts.
    passlib automatically handles verification regardless of the rounds used.

    Args:
        plain_password: Plaintext password to verify.
        hashed_password: Stored pbkdf2_sha256 hash to verify against.

    Returns:
        True if password matches, False otherwise.
    """
    if not plain_password or not hashed_password:
        return False

    try:
        # passlib.verify handles timing-safe comparison
        # Automatically uses the rounds from the stored hash
        return pwd_context.verify(plain_password, hashed_password)
    except Exception:
        # Invalid hash format, wrong algorithm, etc. - treat as mismatch
        return False


def create_access_token(
    subject: str,
    *,
    expires_delta: Optional[timedelta] = None,
    session_id: Optional[str] = None,
) -> str:
    """Create a JWT access token.

    Args:
        subject: User identifier (typically user ID). Must be non-empty,
                 non-whitespace, and <= 256 characters.
        expires_delta: Optional custom expiration. Defaults to ACCESS_TOKEN_EXPIRE_MINUTES.
        session_id: Optional session identifier for session tracking.

    Returns:
        Encoded JWT access token string.

    Raises:
        InvalidSubjectError: If subject is invalid.
        MissingSecretKeyError: If SECRET_KEY is not configured.
        SecurityError: If token encoding fails.
    """
    _validate_secret_key()
    _validate_subject(subject)

    if expires_delta is None:
        expires_delta = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    now = datetime.now(timezone.utc)
    expire = now + expires_delta

    to_encode = {
        "sub": subject,
        "type": TokenType.ACCESS,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }

    if session_id:
        to_encode["sid"] = session_id

    try:
        encoded_jwt = jwt.encode(
            to_encode,
            settings.SECRET_KEY,
            algorithm=settings.ALGORITHM,
        )
        return encoded_jwt
    except Exception as e:
        raise SecurityError(f"Access token creation failed: {type(e).__name__}") from e


def create_refresh_token(
    subject: str,
    *,
    expires_delta: Optional[timedelta] = None,
    token_id: Optional[str] = None,
) -> str:
    """Create a JWT refresh token.

    Args:
        subject: User identifier (typically user ID). Must be non-empty,
                 non-whitespace, and <= 256 characters.
        expires_delta: Optional custom expiration. Defaults to REFRESH_TOKEN_EXPIRE_DAYS.
        token_id: Optional unique identifier for the token (UUID). If provided, included as 'jti' claim.

    Returns:
        Encoded JWT refresh token string.

    Raises:
        InvalidSubjectError: If subject is invalid.
        MissingSecretKeyError: If SECRET_KEY is not configured.
        SecurityError: If token encoding fails.
    """
    _validate_secret_key()
    _validate_subject(subject)

    if expires_delta is None:
        expires_delta = timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

    now = datetime.now(timezone.utc)
    expire = now + expires_delta

    to_encode = {
        "sub": subject,
        "type": TokenType.REFRESH,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }

    if token_id:
        to_encode["jti"] = token_id

    try:
        encoded_jwt = jwt.encode(
            to_encode,
            settings.SECRET_KEY,
            algorithm=settings.ALGORITHM,
        )
        return encoded_jwt
    except Exception as e:
        raise SecurityError(f"Refresh token creation failed: {type(e).__name__}") from e


def decode_token(token: str, *, expected_type: Optional[str] = None) -> dict:
    """Decode and validate a JWT token.

    Args:
        token: JWT token string to decode.
        expected_type: Optional expected token type (TokenType.ACCESS or TokenType.REFRESH).
                       If provided, validates the token type claim matches.

    Returns:
        Decoded token payload as dictionary.

    Raises:
        MissingSecretKeyError: If SECRET_KEY is not configured.
        TokenExpiredError: If token has expired.
        InvalidTokenError: If token is malformed, has invalid signature, missing claims,
                           invalid subject, or iat in the future beyond clock skew.
        InvalidTokenTypeError: If token type doesn't match expected_type.
    """
    _validate_secret_key()

    if not token or not token.strip():
        raise InvalidTokenError("Token is empty")

    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
            options={"verify_iat": True},  # Explicitly verify iat claim
        )
    except ExpiredSignatureError as e:
        raise TokenExpiredError("Token has expired") from e
    except ImmatureSignatureError as e:
        # Token issued in the future (iat claim)
        raise InvalidTokenError(f"Token issued in the future: {e}") from e
    except InvalidIssuedAtError as e:
        # iat claim is not a valid integer
        raise InvalidTokenError(f"Invalid 'iat' claim: {e}") from e
    except PyJWTInvalidSubjectError as e:
        # PyJWT validates sub claim type by default
        raise InvalidTokenError(f"Token 'sub' claim must be a string") from e
    except JWTError as e:
        # Provide more specific error messages for common JWT validation failures
        error_msg = str(e).lower()
        if "signature" in error_msg or "invalid" in error_msg:
            raise InvalidTokenError("Invalid token signature") from e
        raise InvalidTokenError(f"Invalid token: {type(e).__name__}") from e

    # Validate required claims
    if "sub" not in payload:
        raise InvalidTokenError("missing 'sub'")
    if "type" not in payload:
        raise InvalidTokenError("missing 'type'")
    if "exp" not in payload:
        raise InvalidTokenError("missing 'exp'")
    if "iat" not in payload:
        raise InvalidTokenError("missing 'iat'")

    # Validate subject
    subject = payload.get("sub")
    if not isinstance(subject, str):
        raise InvalidTokenError("Token 'sub' claim must be a string")
    try:
        _validate_subject(subject)
    except InvalidSubjectError as e:
        raise InvalidTokenError(str(e)) from e

    # Validate iat (issued at) - reject tokens issued in the future beyond clock skew
    iat = payload.get("iat")
    if not isinstance(iat, int):
        raise InvalidTokenError("Token 'iat' claim must be an integer")
    _validate_iat(iat)

    # Validate token type if expected_type is provided
    if expected_type is not None:
        token_type = payload.get("type")
        if token_type != expected_type:
            raise InvalidTokenTypeError(
                f"Expected token type '{expected_type}', got '{token_type}'"
            )

    return payload


def decode_access_token(token: str) -> dict:
    """Decode and validate an access token.

    Args:
        token: JWT access token string.

    Returns:
        Decoded token payload.

    Raises:
        TokenExpiredError: If token has expired.
        InvalidTokenError: If token is invalid.
        InvalidTokenTypeError: If token is not an access token.
    """
    return decode_token(token, expected_type=TokenType.ACCESS)


def decode_refresh_token(token: str) -> dict:
    """Decode and validate a refresh token.

    Args:
        token: JWT refresh token string.

    Returns:
        Decoded token payload.

    Raises:
        TokenExpiredError: If token has expired.
        InvalidTokenError: If token is invalid.
        InvalidTokenTypeError: If token is not a refresh token.
    """
    return decode_token(token, expected_type=TokenType.REFRESH)


def rotate_refresh_token(
    subject: str,
    *,
    old_token_id: str,
    expires_delta: Optional[timedelta] = None,
) -> tuple[str, str]:
    """Create a new refresh token and return both the new token and its ID.

    This function is used for refresh token rotation. The caller is responsible
    for revoking the old token in the database.

    Args:
        subject: User identifier.
        old_token_id: The JTI (JWT ID) of the token being rotated.
        expires_delta: Optional custom expiration.

    Returns:
        Tuple of (new_refresh_token, new_token_id).

    Raises:
        InvalidSubjectError: If subject is invalid.
        MissingSecretKeyError: If SECRET_KEY is not configured.
        SecurityError: If token encoding fails.
    """
    import uuid
    new_token_id = str(uuid.uuid4())
    new_token = create_refresh_token(
        subject=subject,
        expires_delta=expires_delta,
        token_id=new_token_id,
    )
    return new_token, new_token_id