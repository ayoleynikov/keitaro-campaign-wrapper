import os

import pytest
from httpx import ASGITransport, AsyncClient

from app.config import get_settings
from app.db.session import get_session_factory, init_db, reset_engine
from app.keitaro.mock_client import MockKeitaroClient
from app.main import app


@pytest.fixture(autouse=True)
def mock_env(monkeypatch, tmp_path):
    monkeypatch.setenv("KEITARO_MODE", "mock")
    # Isolate from any live-QA env on the box.
    for key in (
        "KEITARO_WRITE_ALLOWLIST_NAME",
        "KEITARO_DISABLE_COMPENSATION",
        "KEITARO_FORBID_DELETE",
        "KEITARO_CREATE_CAMPAIGN_STATE",
        "KEITARO_API_KEY",
        "KEITARO_BASE_URL",
        "KEITARO_ALLOWED_ORIGIN",
    ):
        monkeypatch.delenv(key, raising=False)
    db_file = tmp_path / "pytest.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_file}")
    get_settings.cache_clear()
    reset_engine()
    from app.keitaro import factory

    factory._mock_singleton = MockKeitaroClient()
    init_db()
    yield
    factory._mock_singleton = None
    reset_engine()
    get_settings.cache_clear()


@pytest.fixture
def db_session():
    init_db()
    db = get_session_factory()()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
async def api_client(mock_env):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client