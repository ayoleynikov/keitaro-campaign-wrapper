from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings
from app.db.base import Base

_engine: Engine | None = None
_SessionLocal: sessionmaker | None = None


def _build_engine() -> Engine:
    settings = get_settings()
    connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
    return create_engine(settings.database_url, connect_args=connect_args)


def get_engine() -> Engine:
    global _engine, _SessionLocal
    settings = get_settings()
    if _engine is None:
        _engine = _build_engine()
        _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)
    return _engine


def get_session_factory() -> sessionmaker:
    global _SessionLocal
    get_engine()
    assert _SessionLocal is not None
    return _SessionLocal


def init_db() -> None:
    settings = get_settings()
    if settings.database_url.startswith("sqlite"):
        from app.db.sqlite_paths import ensure_sqlite_database_ready

        ensure_sqlite_database_ready(settings.database_url)
    Base.metadata.create_all(bind=get_engine())


def get_db() -> Generator[Session, None, None]:
    db = get_session_factory()()
    try:
        yield db
    finally:
        db.close()


def reset_engine() -> None:
    """Test helper: drop cached engine after settings change."""
    global _engine, _SessionLocal
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _SessionLocal = None