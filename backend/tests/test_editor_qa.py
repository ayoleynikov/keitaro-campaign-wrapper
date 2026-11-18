"""Release QA coverage — editor edge cases and allocation exact values."""

import pytest

from app.domain.allocation import AllocationError, OfferSlot, recalculate_shares
from app.keitaro import factory
from app.models.stream_workspace import SyncState


def test_allocation_exact_video_triples():
    shares = recalculate_shares([OfferSlot(1), OfferSlot(2), OfferSlot(3)])
    assert [shares[1], shares[2], shares[3]] == [33, 33, 34]


def test_allocation_exact_video_pin_split():
    shares = recalculate_shares(
        [
            OfferSlot(1, pinned=True, pinned_share=25),
            OfferSlot(2),
            OfferSlot(3),
        ]
    )
    assert [shares[1], shares[2], shares[3]] == [25, 37, 38]


@pytest.mark.asyncio
async def test_push_failure_keeps_dirty(api_client):
    create = await api_client.post(
        "/api/campaigns",
        json={
            "name": "Push fail",
            "geo_iso": "DE",
            "offer_id": 5001,
            "domain_id": 1,
            "group_id": 10,
            "traffic_source_id": 100,
        },
    )
    cid = create.json()["campaign_id"]
    sid = next(s for s in create.json()["streams"] if s.get("offers"))["id"]
    await api_client.post(f"/api/campaigns/{cid}/fetch-streams")
    await api_client.post(f"/api/streams/{sid}/offers", json={"offer_id": 5002})

    client = factory._mock_singleton
    assert client is not None
    client.fail_update_stream_ids.add(sid)
    failed = await api_client.post(f"/api/streams/{sid}/push")
    assert failed.status_code == 502

    ws = (await api_client.get(f"/api/streams/{sid}/workspace")).json()
    assert ws["sync_state"] == SyncState.DIRTY.value
    client.fail_update_stream_ids.discard(sid)


@pytest.mark.asyncio
async def test_push_no_active_offers(api_client):
    create = await api_client.post(
        "/api/campaigns",
        json={
            "name": "Empty active",
            "geo_iso": "PL",
            "offer_id": 5003,
            "domain_id": 1,
            "group_id": 10,
            "traffic_source_id": 100,
        },
    )
    cid = create.json()["campaign_id"]
    sid = next(s for s in create.json()["streams"] if s.get("offers"))["id"]
    await api_client.post(f"/api/campaigns/{cid}/fetch-streams")
    await api_client.delete(f"/api/streams/{sid}/offers/5003")
    resp = await api_client.post(f"/api/streams/{sid}/push")
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_cancel_restores_baseline_after_pin_remove_restore(api_client):
    create = await api_client.post(
        "/api/campaigns",
        json={
            "name": "Cancel baseline",
            "geo_iso": "AU",
            "offer_id": 5001,
            "domain_id": 1,
            "group_id": 10,
            "traffic_source_id": 100,
        },
    )
    cid = create.json()["campaign_id"]
    sid = next(s for s in create.json()["streams"] if s.get("offers"))["id"]
    await api_client.post(f"/api/campaigns/{cid}/fetch-streams")
    await api_client.post(f"/api/streams/{sid}/offers", json={"offer_id": 5002})
    await api_client.post(f"/api/streams/{sid}/offers", json={"offer_id": 5003})
    await api_client.post(f"/api/streams/{sid}/push")
    await api_client.post(f"/api/streams/{sid}/offers/5003/pin", json={"share": 25})
    await api_client.delete(f"/api/streams/{sid}/offers/5002")
    await api_client.post(f"/api/streams/{sid}/offers/5002/restore")
    baseline_ws = (await api_client.get(f"/api/streams/{sid}/workspace")).json()
    await api_client.post(f"/api/streams/{sid}/offers", json={"offer_id": 5004})
    cancelled = await api_client.post(f"/api/streams/{sid}/cancel")
    assert cancelled.status_code == 200
    after = cancelled.json()
    assert after["sync_state"] == SyncState.CLEAN.value
    base_active = sorted(o["offer_id"] for o in baseline_ws["offers"] if o["lifecycle"] == "active")
    after_active = sorted(o["offer_id"] for o in after["offers"] if o["lifecycle"] == "active")
    assert after_active == base_active
    assert not any(o["offer_id"] == 5004 for o in after["offers"])


@pytest.mark.asyncio
async def test_fetch_preserves_dirty_unpublished_add(api_client):
    create = await api_client.post(
        "/api/campaigns",
        json={
            "name": "Fetch dirty",
            "geo_iso": "MX",
            "offer_id": 5001,
            "domain_id": 1,
            "group_id": 10,
            "traffic_source_id": 100,
        },
    )
    cid = create.json()["campaign_id"]
    sid = next(s for s in create.json()["streams"] if s.get("offers"))["id"]
    await api_client.post(f"/api/campaigns/{cid}/fetch-streams")
    await api_client.post(f"/api/streams/{sid}/offers", json={"offer_id": 5002})
    refetch = await api_client.post(f"/api/campaigns/{cid}/fetch-streams")
    ws = next(w for w in refetch.json() if w["keitaro_stream_id"] == sid)
    assert ws["sync_state"] == SyncState.DIRTY.value
    assert any(o["offer_id"] == 5002 and o["is_new_unpublished"] for o in ws["offers"])


@pytest.mark.asyncio
async def test_stream_filters_metadata_used_in_campaign_create(api_client):
    from app.keitaro import factory

    client = factory._mock_singleton
    assert client is not None
    client._state["stream_filters"] = [{"value": "country", "tooltip": "Country"}]
    create = await api_client.post(
        "/api/campaigns",
        json={
            "name": "Meta filters",
            "geo_iso": "DE",
            "offer_id": 5002,
            "domain_id": 1,
            "group_id": 10,
            "traffic_source_id": 100,
        },
    )
    assert create.status_code == 200
    geo = next(s for s in create.json()["streams"] if s.get("filters"))
    assert geo["filters"][0]["name"] == "country"