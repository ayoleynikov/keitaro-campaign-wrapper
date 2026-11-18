"""Build Keitaro Admin API stream payloads (OpenAPI: StreamObject / StreamRequest)."""

from __future__ import annotations

from app.config import get_settings


def build_geo_redirect_stream(
    *,
    campaign_id: int,
    geo_iso: str,
    position: int = 1,
    google_url: str | None = None,
    filter_name: str | None = None,
    action_type: str | None = None,
) -> dict:
    settings = get_settings()
    url = google_url or settings.default_google_redirect
    fname = filter_name or settings.default_country_filter_name
    geo = geo_iso.upper().strip()
    return {
        "campaign_id": campaign_id,
        "type": "regular",
        "name": f"GEO {geo} → Google",
        "position": position,
        "schema": "redirect",
        "action_type": action_type or "http",
        "action_payload": url,
        "state": "active",
        "filters": [
            {
                "name": fname,
                "mode": "accept",
                "payload": [geo],
            }
        ],
    }


def build_offer_fallback_stream(
    *,
    campaign_id: int,
    offer_id: int,
    position: int = 2,
    stream_name: str = "Fallback offer",
) -> dict:
    return {
        "campaign_id": campaign_id,
        "type": "default",
        "name": stream_name,
        "position": position,
        "schema": "landings",
        "action_type": "http",
        "state": "active",
        "offers": [
            {"offer_id": offer_id, "share": 100, "state": "active"},
        ],
    }


def build_offer_rotation_payload(offers: list[dict]) -> dict:
    """Partial PUT body: only `offers` (Keitaro updates fields provided)."""
    return {
        "offers": [
            {
                "offer_id": o["offer_id"],
                "share": o["share"],
                "state": o.get("state", "active"),
            }
            for o in offers
        ]
    }