import pytest

from app.config import get_settings
from app.keitaro.errors import KeitaroValidationError
from app.keitaro.http_client import HttpKeitaroClient
from app.keitaro.payloads import as_resource_list, offer_id_of


def test_as_resource_list_accepts_array():
    rows = as_resource_list([{"id": 1}, {"id": 2}])
    assert len(rows) == 2


def test_as_resource_list_unwraps_common_containers():
    inner = [{"id": 10}]
    for key in ("items", "offers", "data", "results", "rows"):
        assert as_resource_list({key: inner}) == inner


def test_as_resource_list_rejects_bare_object():
    with pytest.raises(KeitaroValidationError):
        as_resource_list({"total": 1, "id": 5})


def test_offer_id_prefers_id_then_offer_id():
    assert offer_id_of({"id": 101, "offer_id": 1}) == 101
    assert offer_id_of({"offer_id": 42}) == 42


@pytest.mark.asyncio
async def test_http_client_unwraps_wrapped_offers_and_searches_offer_id():
    client = HttpKeitaroClient("https://tracker.example", "dummy-key", allowed_origin="https://tracker.example")

    async def fake_request(method, path, *, json_body=None):
        assert method == "GET"
        if path == "offers":
            return {"items": [{"offer_id": 11, "name": "One"}, {"id": 22, "name": "Two"}]}
        raise AssertionError(path)

    client._request = fake_request  # type: ignore[method-assign]
    listed = await client.list_offers()
    assert [offer_id_of(o) for o in listed] == [11, 22]
    found = await client.search_offers("2")
    assert [offer_id_of(o) for o in found] == [22]
    none = await client.search_offers("zzz")
    assert none == []


@pytest.mark.asyncio
async def test_offers_stats_mock(api_client):
    response = await api_client.get("/api/references/offers/stats")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["count"] == 5
    assert body["deleted_count"] == 0


@pytest.mark.asyncio
async def test_allowlist_scopes_campaign_index(api_client, monkeypatch):
    created = await api_client.post(
        "/api/campaigns",
        json={
            "name": "allowlisted_demo_campaign",
            "geo_iso": "AU",
            "offer_id": 5001,
            "domain_id": 1,
            "group_id": 10,
            "traffic_source_id": 100,
        },
    )
    assert created.status_code == 200, created.text
    other = await api_client.post(
        "/api/campaigns",
        json={
            "name": "someone_else_should_hide",
            "geo_iso": "MX",
            "offer_id": 5002,
            "domain_id": 1,
            "group_id": 10,
            "traffic_source_id": 100,
        },
    )
    assert other.status_code == 200, other.text
    monkeypatch.setenv("KEITARO_WRITE_ALLOWLIST_NAME", "allowlisted_demo_campaign")
    get_settings.cache_clear()
    try:
        listed = await api_client.get("/api/campaigns")
        assert listed.status_code == 200
        names = [c["name"] for c in listed.json()]
        assert names == ["allowlisted_demo_campaign"]
    finally:
        monkeypatch.delenv("KEITARO_WRITE_ALLOWLIST_NAME", raising=False)
        get_settings.cache_clear()
