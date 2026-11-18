"""Resolve SQLite paths relative to the backend package root (not process cwd)."""

from __future__ import annotations

import os
import stat
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = BACKEND_ROOT.parent


class SqliteDatabaseStartupError(RuntimeError):
    """SQLite is missing, mis-located, or not writable — startup should abort with this message."""


def default_sqlite_file() -> Path:
    return BACKEND_ROOT / "data" / "app.db"


def normalize_sqlite_database_url(database_url: str) -> str:
    if not database_url.startswith("sqlite"):
        return database_url
    if database_url.startswith("sqlite:///:memory:"):
        return database_url

    prefix = "sqlite:///"
    if not database_url.startswith(prefix):
        return database_url

    remainder = database_url[len(prefix) :]
    # Absolute Unix path in SQLAlchemy form: sqlite:////var/tmp/x.db
    if remainder.startswith("/"):
        path = Path(remainder)
    else:
        if remainder.startswith("./"):
            remainder = remainder[2:]
        path = (BACKEND_ROOT / remainder).resolve()

    return f"sqlite:///{path.as_posix()}"


def sqlite_file_from_url(database_url: str) -> Path | None:
    if not database_url.startswith("sqlite") or ":memory:" in database_url:
        return None
    normalized = normalize_sqlite_database_url(database_url)
    prefix = "sqlite:///"
    if not normalized.startswith(prefix):
        return None
    return Path(normalized[len(prefix) :])


def ensure_sqlite_database_ready(database_url: str) -> Path:
    """
    Ensure parent directory exists and the database file can be created/opened for writing.
    Raises SqliteDatabaseStartupError with non-destructive recovery steps.
    """
    db_path = sqlite_file_from_url(database_url)
    if db_path is None:
        raise SqliteDatabaseStartupError("Unsupported or in-memory SQLite URL; nothing to prepare.")

    data_dir = db_path.parent
    try:
        data_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise SqliteDatabaseStartupError(
            _recovery_message(
                db_path,
                f"Cannot create database directory {data_dir}: {exc}",
            )
        ) from exc

    if not os.access(data_dir, os.W_OK | os.X_OK):
        raise SqliteDatabaseStartupError(
            _recovery_message(
                db_path,
                f"Database directory is not writable: {data_dir} (uid={os.getuid()}, cwd={os.getcwd()}).",
            )
        )

    if db_path.exists():
        mode = db_path.stat().st_mode
        if not os.access(db_path, os.W_OK):
            raise SqliteDatabaseStartupError(
                _recovery_message(
                    db_path,
                    f"Database file exists but is read-only (mode {stat.filemode(mode)}). "
                    "Fix ownership or permissions without deleting the file.",
                )
            )
    else:
        try:
            db_path.touch(exist_ok=True)
        except OSError as exc:
            raise SqliteDatabaseStartupError(
                _recovery_message(db_path, f"Cannot create database file {db_path}: {exc}")
            ) from exc

    # Probe write with SQLite itself (journal files must be writable too).
    import sqlite3

    try:
        conn = sqlite3.connect(str(db_path), timeout=5)
        try:
            conn.execute("PRAGMA user_version")
            conn.execute("CREATE TABLE IF NOT EXISTS __startup_write_probe (id INTEGER PRIMARY KEY)")
            conn.execute("INSERT INTO __startup_write_probe (id) VALUES (1) ON CONFLICT(id) DO NOTHING")
            conn.commit()
        finally:
            conn.close()
    except sqlite3.OperationalError as exc:
        raise SqliteDatabaseStartupError(
            _recovery_message(
                db_path,
                f"SQLite refused a write ({exc}). "
                "If you replaced or removed the file while the API was running, stop uvicorn and start it again "
                "so it reopens the file — do not delete the database to fix this.",
            )
        ) from exc

    return db_path


def _recovery_message(db_path: Path, detail: str) -> str:
    alt = f"sqlite:///{(BACKEND_ROOT / 'data' / 'app-isolated.db').resolve().as_posix()}"
    return (
        f"{detail}\n\n"
        f"Database path (resolved): {db_path}\n"
        f"Backend root: {BACKEND_ROOT}\n\n"
        "Non-destructive recovery:\n"
        "1. Stop all uvicorn/python processes using this database, then start again (reopen after file moves).\n"
        "2. Ensure `backend/data/` is owned by your user and writable: `chmod u+rwX backend/data` and fix file mode.\n"
        f"3. For an isolated QA copy, set DATABASE_URL={alt} and run `alembic upgrade head` (keeps existing app.db intact).\n"
        "4. Never remove `app.db` while the server is running — that leaves open handles on a deleted inode (readonly errors)."
    )