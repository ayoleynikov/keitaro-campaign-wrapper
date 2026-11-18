import os
from pathlib import Path

import pytest

from app.db.sqlite_paths import (
    BACKEND_ROOT,
    SqliteDatabaseStartupError,
    default_sqlite_file,
    ensure_sqlite_database_ready,
    normalize_sqlite_database_url,
)


def test_normalize_relative_url_ignores_cwd(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    url = normalize_sqlite_database_url("sqlite:///./data/app.db")
    assert url == f"sqlite:///{default_sqlite_file().as_posix()}"


def test_ensure_sqlite_ready_creates_writable_file(tmp_path: Path) -> None:
    db = tmp_path / "nested" / "qa.db"
    url = f"sqlite:///{db.as_posix()}"
    ensure_sqlite_database_ready(url)
    assert db.is_file()
    assert os.access(db, os.W_OK)


def test_ensure_sqlite_readonly_file_raises(tmp_path: Path) -> None:
    db = tmp_path / "readonly.db"
    db.write_text("")
    db.chmod(0o444)
    url = f"sqlite:///{db.as_posix()}"
    with pytest.raises(SqliteDatabaseStartupError) as exc:
        ensure_sqlite_database_ready(url)
    assert "read-only" in str(exc.value).lower() or "readonly" in str(exc.value).lower()
    assert "Non-destructive recovery" in str(exc.value)
    db.chmod(0o644)


def test_backend_root_points_at_backend_package() -> None:
    assert (BACKEND_ROOT / "app" / "config.py").is_file()