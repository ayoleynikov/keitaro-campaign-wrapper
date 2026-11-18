from app.domain.streams import build_geo_redirect_stream, build_offer_fallback_stream


def test_geo_stream_payload():
    payload = build_geo_redirect_stream(campaign_id=99, geo_iso="de", position=1)
    assert payload["campaign_id"] == 99
    assert payload["position"] == 1
    assert payload["type"] == "regular"
    assert payload["filters"][0]["payload"] == ["DE"]
    assert "google" in payload["action_payload"].lower()


def test_fallback_stream():
    payload = build_offer_fallback_stream(campaign_id=1, offer_id=5001, position=2)
    assert payload["type"] == "default"
    assert payload["offers"][0]["share"] == 100