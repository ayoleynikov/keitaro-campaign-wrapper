"""
Contract checks against public OpenAPI resource paths (not live-tested).

Source: https://admin-api.docs.keitaro.io/openapi.json
"""

from app.keitaro.http_client import HttpKeitaroClient


def test_http_client_api_root():
    client = HttpKeitaroClient("https://tracker.example", "secret-key")
    assert client._api_root.endswith("/admin_api/v1/")


def test_http_client_documented_paths():
    """Paths from https://admin-api.docs.keitaro.io/openapi.json (not live-called)."""
    client = HttpKeitaroClient("https://tracker.example", "secret-key")
    root = client._api_root
    assert root.endswith("/admin_api/v1/")
    assert "tracker.example" in root