from __future__ import annotations

from functools import lru_cache

from app.config import Settings, get_settings
from app.keitaro.errors import KeitaroError
from app.keitaro.http_client import HttpKeitaroClient
from app.keitaro.mock_client import MockKeitaroClient
from app.keitaro.protocol import KeitaroClient

_mock_singleton: MockKeitaroClient | None = None


def get_keitaro_client(settings: Settings | None = None) -> KeitaroClient:
    settings = settings or get_settings()
    mode = settings.keitaro_mode.lower().strip()
    if mode == "mock":
        global _mock_singleton
        if _mock_singleton is None:
            _mock_singleton = MockKeitaroClient()
        return _mock_singleton
    if mode == "live":
        if not settings.keitaro_base_url or not settings.keitaro_api_key:
            raise KeitaroError("KEITARO_BASE_URL and KEITARO_API_KEY are required in live mode")
        return HttpKeitaroClient(
            settings.keitaro_base_url,
            settings.keitaro_api_key,
            timeout=settings.keitaro_timeout_seconds,
            allowed_origin=settings.keitaro_allowed_origin or None,
            forbid_delete=settings.keitaro_forbid_delete,
        )
    raise KeitaroError(f"Unknown KEITARO_MODE: {settings.keitaro_mode}")