import pytest

from app.models.stream_workspace import OfferLifecycle, SyncState


@pytest.mark.asyncio
async def test_fetch_add_push_cancel(api_client):
    create = await api_client.post(
        "/api/campaigns",
        json={
            "name": "Editor Flow",
            "geo_iso": "AU",
            "offer_id": 5001,
            "domain_id": 1,
            "group_id": 10,
            "traffic_source_id": 100,
        },
    )
    campaign_id = create.json()["campaign_id"]
    streams = create.json()["streams"]
    offer_stream = next(s for s in streams if s.get("offers"))
    stream_id = offer_stream["id"]

    fetched = await api_client.post(f"/api/campaigns/{campaign_id}/fetch-streams")
    assert fetched.status_code == 200
    ws = next(w for w in fetched.json() if w["keitaro_stream_id"] == stream_id)
    assert ws["sync_state"] == SyncState.CLEAN.value

    added = await api_client.post(f"/api/streams/{stream_id}/offers", json={"offer_id": 5002})
    assert added.status_code == 200
    body = added.json()
    assert body["sync_state"] == SyncState.DIRTY.value
    active_shares = [o["share"] for o in body["offers"] if o["lifecycle"] == "active"]
    assert sum(active_shares) == 100

    cancelled = await api_client.post(f"/api/streams/{stream_id}/cancel")
    assert cancelled.status_code == 200
    assert cancelled.json()["sync_state"] == SyncState.CLEAN.value
    assert len([o for o in cancelled.json()["offers"] if o["lifecycle"] == "active"]) == 1

    await api_client.post(f"/api/streams/{stream_id}/offers", json={"offer_id": 5002})
    pushed = await api_client.post(f"/api/streams/{stream_id}/push")
    assert pushed.status_code == 200
    assert pushed.json()["sync_state"] == SyncState.CLEAN.value

    upstream = await api_client.get(f"/api/campaigns/{campaign_id}/streams")
    kt = next(s for s in upstream.json() if s["id"] == stream_id)
    assert len(kt["offers"]) == 2


@pytest.mark.asyncio
async def test_remove_restore_archive(api_client):
    create = await api_client.post(
        "/api/campaigns",
        json={
            "name": "Remove Flow",
            "geo_iso": "RO",
            "offer_id": 5003,
            "domain_id": 1,
            "group_id": 10,
            "traffic_source_id": 101,
        },
    )
    campaign_id = create.json()["campaign_id"]
    stream_id = next(s for s in create.json()["streams"] if s.get("offers"))["id"]
    await api_client.post(f"/api/campaigns/{campaign_id}/fetch-streams")
    await api_client.post(f"/api/streams/{stream_id}/offers", json={"offer_id": 5001})

    removed = await api_client.delete(f"/api/streams/{stream_id}/offers/5001")
    row = next(o for o in removed.json()["offers"] if o["offer_id"] == 5001)
    assert row["lifecycle"] == OfferLifecycle.REMOVED.value
    assert row["share"] == 0
    assert row["state_label"] is None
    assert removed.json()["sync_state"] == SyncState.DIRTY.value

    pushed = await api_client.post(f"/api/streams/{stream_id}/push")
    archived = next(o for o in pushed.json()["offers"] if o["offer_id"] == 5001)
    assert archived["lifecycle"] == OfferLifecycle.ARCHIVED.value
    assert archived["can_bring_back"] is True

    restored = await api_client.post(f"/api/streams/{stream_id}/offers/5001/restore")
    assert next(o for o in restored.json()["offers"] if o["offer_id"] == 5001)["lifecycle"] == "active"


@pytest.mark.asyncio
async def test_fetch_reconcile_upstream_removal(api_client):
    create = await api_client.post(
        "/api/campaigns",
        json={
            "name": "Reconcile",
            "geo_iso": "MX",
            "offer_id": 5001,
            "domain_id": 1,
            "group_id": 10,
            "traffic_source_id": 100,
        },
    )
    campaign_id = create.json()["campaign_id"]
    stream_id = next(s for s in create.json()["streams"] if s.get("offers"))["id"]
    await api_client.post(f"/api/campaigns/{campaign_id}/fetch-streams")
    await api_client.post(f"/api/streams/{stream_id}/offers", json={"offer_id": 5002})
    await api_client.post(f"/api/streams/{stream_id}/push")

    from app.keitaro import factory

    client = factory._mock_singleton
    assert client is not None
    for s in client._state["streams"]:
        if s["id"] == stream_id:
            s["offers"] = [o for o in s.get("offers", []) if o["offer_id"] != 5002]

    refetched = await api_client.post(f"/api/campaigns/{campaign_id}/fetch-streams")
    ws = next(w for w in refetched.json() if w["keitaro_stream_id"] == stream_id)
    ghost = next(o for o in ws["offers"] if o["offer_id"] == 5002)
    assert ghost["lifecycle"] == OfferLifecycle.REMOVED.value
    assert ghost["state_label"] == "removed"
    assert ws["sync_state"] == SyncState.CLEAN.value


@pytest.mark.asyncio
async def test_cancel_restores_four_quarters(api_client):
    create = await api_client.post(
        "/api/campaigns",
        json={
            "name": "Cancel video",
            "geo_iso": "AU",
            "offer_id": 5001,
            "domain_id": 1,
            "group_id": 10,
            "traffic_source_id": 100,
        },
    )
    campaign_id = create.json()["campaign_id"]
    stream_id = next(s for s in create.json()["streams"] if s.get("offers"))["id"]
    await api_client.post(f"/api/campaigns/{campaign_id}/fetch-streams")
    for oid in (5002, 5003, 5004):
        await api_client.post(f"/api/streams/{stream_id}/offers", json={"offer_id": oid})
    await api_client.post(f"/api/streams/{stream_id}/push")
    await api_client.post(f"/api/streams/{stream_id}/offers", json={"offer_id": 5005})
    cancelled = await api_client.post(f"/api/streams/{stream_id}/cancel")
    active = [o for o in cancelled.json()["offers"] if o["lifecycle"] == "active"]
    assert len(active) == 4
    assert sorted(o["share"] for o in active) == [25, 25, 25, 25]
    assert cancelled.json()["sync_state"] == SyncState.CLEAN.value


@pytest.mark.asyncio
async def test_pin_and_push(api_client):
    create = await api_client.post(
        "/api/campaigns",
        json={
            "name": "Pin Flow",
            "geo_iso": "PL",
            "offer_id": 5003,
            "domain_id": 1,
            "group_id": 10,
            "traffic_source_id": 100,
        },
    )
    campaign_id = create.json()["campaign_id"]
    stream_id = next(s for s in create.json()["streams"] if s.get("offers"))["id"]
    await api_client.post(f"/api/campaigns/{campaign_id}/fetch-streams")
    await api_client.post(f"/api/streams/{stream_id}/offers", json={"offer_id": 5001})

    pinned = await api_client.post(f"/api/streams/{stream_id}/offers/5003/pin", json={"share": 25})
    assert pinned.status_code == 200
    shares = {o["offer_id"]: o["share"] for o in pinned.json()["offers"] if o["lifecycle"] == "active"}
    assert shares[5003] == 25
    assert sum(shares.values()) == 100

    bad = await api_client.post(f"/api/streams/{stream_id}/offers/5001/pin", json={"share": 80})
    assert bad.status_code == 422