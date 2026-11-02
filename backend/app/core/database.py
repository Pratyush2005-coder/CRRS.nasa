"""Database engine and session management using SQLAlchemy 2.0."""

from pathlib import Path
from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from app.core.config import settings

# Resolve SQLite database path and ensure directory exists
db_url = settings.DATABASE_URL
connect_args = {}

if db_url.startswith("sqlite"):
    connect_args["check_same_thread"] = False
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

engine = create_engine(
    db_url,
    connect_args=connect_args,
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """Dependency for providing an isolated database session per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Initialize database tables for all registered models."""
    import app.models.farm  # noqa: F401
    Base.metadata.create_all(bind=engine)
