import pytest

from app.config import get_settings
from app.keitaro.errors import PartialCreateError, WriteGuardError
from app.keitaro.http_client import HttpKeitaroClient, _normalize_api_root
from app.keitaro.mock_client import MockKeitaroClient
from app.models.operation import Operation, OperationStatus
from app.services.campaign_service import CampaignService
from app.services.metadata_service import resolve_redirect_action_type
from app.keitaro.factory import get_keitaro_client


def test_normalize_api_root_does_not_double_prefix():
    origin, root = _normalize_api_root("https://tracker.example/admin_api/v1")
    assert origin == "https://tracker.example"
    assert root == "https://tracker.example/admin_api/v1/"
    origin2, root2 = _normalize_api_root("https://tracker.example")
    assert origin2 == "https://tracker.example"
    assert root2 == "https://tracker.example/admin_api/v1/"


def test_http_client_rejects_non_https_origin():
    with pytest.raises(WriteGuardError):
        HttpKeitaroClient("http://tracker.example", "secret-key", allowed_origin="https://tracker.example")


@pytest.mark.asyncio
async def test_allowlist_blocks_other_campaign_names(api_client, monkeypatch):
    monkeypatch.setenv("KEITARO_WRITE_ALLOWLIST_NAME", "allowlisted_demo_campaign")
    get_settings.cache_clear()
    try:
        response = await api_client.post(
            "/api/campaigns",
            json={
                "name": "someone_else",
                "geo_iso": "AU",
                "offer_id": 5002,
                "domain_id": 1,
                "group_id": 10,
                "traffic_source_id": 100,
            },
        )
        assert response.status_code == 403
    finally:
        monkeypatch.delenv("KEITARO_WRITE_ALLOWLIST_NAME", raising=False)
        get_settings.cache_clear()


@pytest.mark.asyncio
async def test_duplicate_name_refuses_second_create(api_client):
    body = {
        "name": "Unique Dup Guard",
        "geo_iso": "AU",
        "offer_id": 5002,
        "domain_id": 1,
        "group_id": 10,
        "traffic_source_id": 100,
    }
    first = await api_client.post("/api/campaigns", json=body)
    assert first.status_code == 200, first.text
    second = await api_client.post("/api/campaigns", json=body)
    assert second.status_code == 409


@pytest.mark.asyncio
async def test_compensation_disabled_keeps_partial_campaign(monkeypatch, db_session):
    monkeypatch.setenv("KEITARO_DISABLE_COMPENSATION", "true")
    monkeypatch.setenv("KEITARO_FORBID_DELETE", "true")
    get_settings.cache_clear()
    client = MockKeitaroClient()

    async def fail_second_stream(payload):
        if payload.get("type") == "default":
            raise WriteGuardError("injected stream failure", status_code=500)
        return await MockKeitaroClient.create_stream(client, payload)

    client.create_stream = fail_second_stream  # type: ignore[method-assign]
    service = CampaignService(client, db_session)
    with pytest.raises(PartialCreateError):
        await service.create_campaign_with_streams(
            {
                "name": "Partial Keep Me",
                "geo_iso": "AU",
                "offer_id": 5002,
                "domain_id": 1,
                "group_id": 10,
                "traffic_source_id": 100,
            }
        )
    remaining = await client.find_campaigns() if hasattr(client, "find_campaigns") else await client.list_campaigns()
    names = [c["name"] for c in remaining]
    assert "Partial Keep Me" in names
    # streams: geo should remain
    campaign = next(c for c in remaining if c["name"] == "Partial Keep Me")
    streams = await client.list_streams(campaign["id"])
    assert len(streams) == 1
    monkeypatch.delenv("KEITARO_DISABLE_COMPENSATION", raising=False)
    monkeypatch.delenv("KEITARO_FORBID_DELETE", raising=False)
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_create_disabled_state(monkeypatch, api_client):
    monkeypatch.setenv("KEITARO_CREATE_CAMPAIGN_STATE", "disabled")
    get_settings.cache_clear()
    try:
        response = await api_client.post(
            "/api/campaigns",
            json={
                "name": "Disabled Campaign",
                "geo_iso": "AU",
                "offer_id": 5002,
                "domain_id": 1,
                "group_id": 10,
                "traffic_source_id": 100,
            },
        )
        assert response.status_code == 200, response.text
        cid = response.json()["campaign_id"]
        got = await api_client.get(f"/api/campaigns/{cid}")
        assert got.json()["state"] == "disabled"
    finally:
        monkeypatch.delenv("KEITARO_CREATE_CAMPAIGN_STATE", raising=False)
        get_settings.cache_clear()


@pytest.mark.asyncio
async def test_resolve_action_type_prefers_key():
    from app.keitaro import factory

    factory._mock_singleton = MockKeitaroClient()
    factory._mock_singleton._state["streams_actions"] = [
        {"key": "http", "name": "HttpRedirect", "type": "redirect"},
        {"key": "js", "name": "Js", "type": "redirect"},
    ]
    assert await resolve_redirect_action_type() == "http"


@pytest.mark.asyncio
async def test_list_campaigns_by_name(api_client):
    body = {
        "name": "Lookup By Name",
        "geo_iso": "MX",
        "offer_id": 5001,
        "domain_id": 1,
        "group_id": 10,
        "traffic_source_id": 100,
    }
    created = await api_client.post("/api/campaigns", json=body)
    assert created.status_code == 200
    found = await api_client.get("/api/campaigns", params={"name": "Lookup By Name"})
    assert found.status_code == 200
    rows = found.json()
    assert len(rows) == 1
    assert rows[0]["id"] == created.json()["campaign_id"]
    missing = await api_client.get("/api/campaigns", params={"name": "does-not-exist-xyz"})
    assert missing.json() == []
