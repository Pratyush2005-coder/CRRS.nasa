"""Database engine and session management using SQLAlchemy 2.0."""

import logging
import time
from pathlib import Path
from typing import Generator
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from sqlalchemy.pool import QueuePool, NullPool
from app.core.config import settings

# Configure module logger
logger = logging.getLogger(__name__)

# Resolve SQLite database path and ensure directory exists
db_url = settings.DATABASE_URL
connect_args = {}

# Configure pool and connect_args based on database type
is_sqlite = db_url.startswith("sqlite")
is_postgresql = db_url.startswith("postgresql") or db_url.startswith("postgres")

if is_sqlite:
    connect_args["check_same_thread"] = False
    # SQLite uses NullPool (no connection pooling)
    pool_class = NullPool
    pool_kwargs = {}
    db_path_str = db_url.replace("sqlite:///", "")
    if db_path_str and not db_path_str.startswith(":memory:"):
        db_path = Path(db_path_str)
        if not db_path.is_absolute():
            backend_dir = Path(__file__).resolve().parent.parent.parent
            full_db_path = (backend_dir / db_path).resolve()
            full_db_path.parent.mkdir(parents=True, exist_ok=True)
            db_url = f"sqlite:///{full_db_path.as_posix()}"
        else:
            db_path.parent.mkdir(parents=True, exist_ok=True)
elif is_postgresql:
    # PostgreSQL: add connect_timeout to connect_args (driver-specific)
    # Works with psycopg2, psycopg, asyncpg
    connect_args["connect_timeout"] = settings.DATABASE_CONNECT_TIMEOUT
    # Use QueuePool with configured settings
    pool_class = QueuePool
    pool_kwargs = {
        "pool_size": settings.DATABASE_POOL_SIZE,
        "max_overflow": settings.DATABASE_MAX_OVERFLOW,
        "pool_timeout": settings.DATABASE_POOL_TIMEOUT,
        "pool_recycle": settings.DATABASE_POOL_RECYCLE,
        "pool_pre_ping": settings.DATABASE_POOL_PRE_PING,
    }
else:
    # Other databases: use default pooling behavior
    pool_class = QueuePool
    pool_kwargs = {
        "pool_size": settings.DATABASE_POOL_SIZE,
        "max_overflow": settings.DATABASE_MAX_OVERFLOW,
        "pool_timeout": settings.DATABASE_POOL_TIMEOUT,
        "pool_recycle": settings.DATABASE_POOL_RECYCLE,
        "pool_pre_ping": settings.DATABASE_POOL_PRE_PING,
    }

engine = create_engine(
    db_url,
    connect_args=connect_args,
    poolclass=pool_class,
    **pool_kwargs,
    echo=settings.DATABASE_ECHO,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """
    Dependency for providing an isolated database session per request.

    Session lifecycle:
    - Creates a new session for each request
    - Yields session to the request handler
    - Rolls back transaction on exception (does not commit automatically)
    - Always closes session in finally block
    - Does not rollback after successful requests (caller manages commits)
    """
    db = SessionLocal()
    try:
        yield db
    except Exception:
        # Roll back the transaction on any exception
        # This ensures no partial transaction state leaks
        try:
            db.rollback()
        except Exception:
            # Rollback itself failed - log but don't raise
            # The session will be closed in finally block
            pass
        raise
    finally:
        # Always close the session, regardless of success or failure
        try:
            db.close()
        except Exception:
            # Close failed - log but don't raise to avoid masking original error
            pass


def init_db(max_retries: int = 3, retry_backoff: float = 1.0) -> None:
    """
    Initialize database tables for all registered models.

    Args:
        max_retries: Maximum number of initialization attempts (default: 3)
        retry_backoff: Seconds to wait between retries (default: 1.0)

    Behavior:
        - Imports all models to register them with Base.metadata
        - Calls Base.metadata.create_all() to create tables
        - Retries on transient SQLAlchemy errors with bounded backoff
        - Fails fast on non-transient errors (e.g., programming errors)
        - Does not expose database credentials or full connection URLs in logs
        - Does not replace Alembic migrations - this is for development/test only

    Raises:
        SQLAlchemyError: If initialization fails after all retries
    """
    import app.models.farm  # noqa: F401
    import app.models.user  # noqa: F401
    import app.models.refresh_token  # noqa: F401
    import app.models.password_reset_token  # noqa: F401

    # Log safe database info (no credentials, no full URL)
    db_type = "sqlite" if is_sqlite else "postgresql" if is_postgresql else "unknown"
    logger.info(f"Initializing database (type: {db_type}, retries: {max_retries})")

    last_exception = None
    for attempt in range(1, max_retries + 1):
        try:
            Base.metadata.create_all(bind=engine)
            logger.info("Database initialization completed successfully")
            return
        except SQLAlchemyError as e:
            last_exception = e
            # Sanitize error message to avoid leaking sensitive info
            error_msg = str(e).lower()
            is_transient = any(
                keyword in error_msg
                for keyword in [
                    "connection",
                    "timeout",
                    "temporarily",
                    "unavailable",
                    "refused",
                    "reset",
                    "network",
                    "dns",
                    "resolve",
                    "unable to open",
                    "database file",
                    "disk i/o",
                    "io error",
                ]
            )

            if attempt < max_retries and is_transient:
                wait_time = retry_backoff * attempt  # Linear backoff
                logger.warning(
                    f"Database initialization attempt {attempt}/{max_retries} failed "
                    f"(transient error). Retrying in {wait_time:.1f}s..."
                )
                time.sleep(wait_time)
                continue
            else:
                # Non-transient error or last attempt - log failure and re-raise
                logger.error(
                    f"Database initialization failed after {attempt} attempt(s): "
                    f"{type(e).__name__}"
                )
                raise
        except Exception as e:
            # Unexpected error - log and re-raise immediately
            logger.error(f"Database initialization failed with unexpected error: {type(e).__name__}")
            raise

    # Should not reach here, but safety net
    if last_exception:
        raise last_exception


def check_database_connectivity() -> bool:
    """
    Check database connectivity by executing a lightweight query.

    Returns:
        True if database is reachable, False otherwise.

    This function is safe to call from health checks. It never raises
    exceptions and never exposes database credentials or internal errors.
    """
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        # Catch all exceptions to ensure health check never crashes
        # Log the error internally if needed, but return False for health check
        return False