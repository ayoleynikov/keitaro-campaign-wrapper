import pytest

from app.models.operation import Operation, OperationStatus


@pytest.mark.asyncio
async def test_create_campaign_mock(api_client, db_session):
    body = {
        "name": "Test DE Campaign",
        "geo_iso": "DE",
        "offer_id": 5002,
        "domain_id": 1,
        "group_id": 10,
        "traffic_source_id": 100,
    }
    response = await api_client.post("/api/campaigns", json=body)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["campaign_id"] >= 2000
    assert len(data["streams"]) == 2
    streams = await api_client.get(f"/api/campaigns/{data['campaign_id']}/streams")
    assert streams.status_code == 200
    listed = streams.json()
    assert listed[0]["position"] <= listed[1]["position"]

    op = db_session.get(Operation, data["operation_id"])
    assert op.status == OperationStatus.SUCCEEDED.value


@pytest.mark.asyncio
async def test_update_stream_offers(api_client):
    create = await api_client.post(
        "/api/campaigns",
        json={
            "name": "Editor Campaign",
            "geo_iso": "PL",
            "offer_id": 5003,
            "domain_id": 1,
            "group_id": 10,
            "traffic_source_id": 101,
        },
    )
    campaign_id = create.json()["campaign_id"]
    streams = (await api_client.get(f"/api/campaigns/{campaign_id}/streams")).json()
    rotation = next(s for s in streams if s.get("offers"))
    stream_id = rotation["id"]
    update = await api_client.put(
        f"/api/campaigns/streams/{stream_id}/offers",
        json={"offers": [{"offer_id": 5003, "weight": 60}, {"offer_id": 5001, "weight": 40}]},
    )
    assert update.status_code == 200
    shares = {o["offer_id"]: o["share"] for o in update.json()["offers"]}
    assert sum(shares.values()) == 100
    assert shares[5003] == 60


@pytest.mark.asyncio
async def test_invalid_geo(api_client):
    response = await api_client.post(
        "/api/campaigns",
        json={
            "name": "Bad",
            "geo_iso": "DEU",
            "offer_id": 1,
            "domain_id": 1,
            "group_id": 10,
            "traffic_source_id": 100,
        },
    )
    assert response.status_code == 422