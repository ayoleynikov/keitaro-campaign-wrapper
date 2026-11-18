from __future__ import annotations

from functools import lru_cache

from app.config import get_settings
from app.keitaro.factory import get_keitaro_client


@lru_cache
def _filter_cache_key() -> str:
    return get_settings().keitaro_mode


async def resolve_country_filter_name() -> str:
    """
    Resolve country filter key from GET /stream_filters when live/mock provides catalog.
    Falls back to settings.default_country_filter_name.
    """
    _ = _filter_cache_key()
    client = get_keitaro_client()
    filters = await client.list_stream_filters()
    candidates = ("country", "geo", "country_code", "countries")
    values = {str(f.get("value", "")).lower(): f.get("value") for f in filters}
    for c in candidates:
        if c in values:
            return str(values[c])
    for f in filters:
        val = str(f.get("value", ""))
        if "country" in val.lower():
            return val
    return get_settings().default_country_filter_name


async def resolve_redirect_action_type() -> str:
    client = get_keitaro_client()
    actions = await client.list_streams_actions()
    for a in actions:
        key = str(a.get("key") or a.get("value") or "").lower()
        name = str(a.get("name") or "").lower()
        if key == "http" or name in {"http", "httpredirect"}:
            return str(a.get("key") or a.get("value") or "http")
    return "http"
