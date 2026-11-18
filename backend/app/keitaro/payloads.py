from __future__ import annotations

from typing import Any

from app.keitaro.errors import KeitaroValidationError

_CONTAINER_KEYS = ("items", "offers", "data", "results", "rows")


def as_resource_list(payload: Any, *, what: str = "resource") -> list:
    """Normalize a Keitaro list payload.

    Official OpenAPI types GET /offers as a top-level array. Some payloads may wrap
    the array; we accept documented-style arrays and a short list of common wrappers
    so a wrapped body is not silently searched as a mapping of keys.
    """
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in _CONTAINER_KEYS:
            value = payload.get(key)
            if isinstance(value, list):
                return value
        raise KeitaroValidationError(
            f"Unexpected {what} payload shape (object without a list container)",
            status_code=502,
        )
    raise KeitaroValidationError(f"Unexpected {what} payload type: {type(payload).__name__}", status_code=502)


def offer_id_of(row: dict) -> int | None:
    raw = row.get("id")
    if raw is None:
        raw = row.get("offer_id")
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None
