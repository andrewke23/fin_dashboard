"""
backend/db/database.py

Engine, session factory, and the declarative Base that every model inherits.

Design decisions:
- check_same_thread=False is safe here because FastAPI runs in a single process
  with async handlers; SQLAlchemy's scoped session handles per-request isolation.
- We use a regular (sync) session rather than the async variant because SQLite
  doesn't benefit meaningfully from async I/O and keeps the code simpler.
"""

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from backend.config import get_settings

settings = get_settings()

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False},
    # Echo SQL in development; set to False in production if you prefer silence.
    echo=False,
)


# Enable WAL mode for better concurrent read performance (Plaid sync + UI reads).
@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_connection, _connection_record) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """Shared declarative base — all ORM models inherit from this."""
    pass


def get_db():
    """
    FastAPI dependency that yields a database session and ensures it is always
    closed after the request, even if an exception is raised.

    Usage:
        @router.get("/things")
        def list_things(db: Session = Depends(get_db)):
            ...
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
