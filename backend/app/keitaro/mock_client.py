from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from app.keitaro.errors import KeitaroValidationError

_FIXTURE_PATH = Path(__file__).parent / "fixtures" / "seed.json"


class MockKeitaroClient:
    """Deterministic in-memory Keitaro Admin API (contract aligned with OpenAPI paths)."""

    def __init__(self) -> None:
        self._state: dict[str, Any] = copy.deepcopy(json.loads(_FIXTURE_PATH.read_text(encoding="utf-8")))
        self.fail_update_stream_ids: set[int] = set()

    def reset(self) -> None:
        self._state = copy.deepcopy(json.loads(_FIXTURE_PATH.read_text(encoding="utf-8")))

    async def list_domains(self) -> list[dict[str, Any]]:
        return copy.deepcopy(self._state["domains"])

    async def list_groups(self, group_type: str = "campaigns") -> list[dict[str, Any]]:
        return [g for g in self._state["groups"] if g.get("type") == group_type]

    async def list_traffic_sources(self) -> list[dict[str, Any]]:
        return copy.deepcopy(self._state["traffic_sources"])

    async def list_offers(self) -> list[dict[str, Any]]:
        return copy.deepcopy(self._state["offers"])

    async def list_deleted_offers(self) -> list[dict[str, Any]]:
        return copy.deepcopy(self._state.get("deleted_offers") or [])

    async def search_offers(self, query: str, *, limit: int = 20) -> list[dict[str, Any]]:
        q = query.lower().strip()
        results = []
        for offer in self._state["offers"]:
            if q in str(offer["id"]) or q in offer.get("name", "").lower():
                results.append(copy.deepcopy(offer))
            if len(results) >= limit:
                break
        return results

    async def list_campaigns(self, *, offset: int = 0, limit: int = 100) -> list[dict[str, Any]]:
        items = sorted(self._state["campaigns"], key=lambda c: c["id"])
        return copy.deepcopy(items[offset : offset + limit])

    async def get_campaign(self, campaign_id: int) -> dict[str, Any]:
        for c in self._state["campaigns"]:
            if c["id"] == campaign_id:
                return copy.deepcopy(c)
        raise KeitaroValidationError(f"Campaign {campaign_id} not found", status_code=404)

    async def create_campaign(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not payload.get("name") or not payload.get("alias"):
            raise KeitaroValidationError("alias and name are required", status_code=400)
        cid = self._state["next_campaign_id"]
        self._state["next_campaign_id"] += 1
        campaign = {
            "id": cid,
            "alias": payload["alias"],
            "name": payload["name"],
            "type": payload.get("type", "position"),
            "state": payload.get("state", "active"),
            "domain_id": payload.get("domain_id"),
            "group_id": payload.get("group_id"),
            "traffic_source_id": payload.get("traffic_source_id"),
            "cookies_ttl": payload.get("cookies_ttl", 24),
        }
        self._state["campaigns"].append(campaign)
        return copy.deepcopy(campaign)

    async def update_campaign(self, campaign_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        campaign = await self.get_campaign(campaign_id)
        campaign.update({k: v for k, v in payload.items() if v is not None})
        for i, c in enumerate(self._state["campaigns"]):
            if c["id"] == campaign_id:
                self._state["campaigns"][i] = {**c, **payload}
                break
        return copy.deepcopy(campaign)

    async def delete_campaign(self, campaign_id: int) -> None:
        self._state["campaigns"] = [c for c in self._state["campaigns"] if c["id"] != campaign_id]
        self._state["streams"] = [s for s in self._state["streams"] if s.get("campaign_id") != campaign_id]

    async def list_streams(self, campaign_id: int) -> list[dict[str, Any]]:
        streams = [s for s in self._state["streams"] if s.get("campaign_id") == campaign_id]
        return sorted(copy.deepcopy(streams), key=lambda s: s.get("position", 0))

    async def get_stream(self, stream_id: int) -> dict[str, Any]:
        for s in self._state["streams"]:
            if s["id"] == stream_id:
                return copy.deepcopy(s)
        raise KeitaroValidationError(f"Stream {stream_id} not found", status_code=404)

    async def create_stream(self, payload: dict[str, Any]) -> dict[str, Any]:
        required = ["campaign_id", "schema", "type", "name", "action_type"]
        missing = [k for k in required if k not in payload]
        if missing:
            raise KeitaroValidationError(f"Missing fields: {missing}", status_code=400)
        sid = self._state["next_stream_id"]
        self._state["next_stream_id"] += 1
        stream = {"id": sid, **copy.deepcopy(payload)}
        self._state["streams"].append(stream)
        return copy.deepcopy(stream)

    async def update_stream(self, stream_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        if stream_id in self.fail_update_stream_ids:
            from app.keitaro.errors import KeitaroValidationError

            raise KeitaroValidationError("Simulated upstream failure", status_code=502)
        await self.get_stream(stream_id)
        for i, s in enumerate(self._state["streams"]):
            if s["id"] == stream_id:
                merged = {**s, **copy.deepcopy(payload)}
                self._state["streams"][i] = merged
                return copy.deepcopy(merged)
        raise KeitaroValidationError(f"Stream {stream_id} not found", status_code=404)

    async def delete_stream(self, stream_id: int) -> None:
        self._state["streams"] = [s for s in self._state["streams"] if s["id"] != stream_id]

    async def list_stream_filters(self) -> list[dict[str, Any]]:
        return copy.deepcopy(self._state.get("stream_filters", []))

    async def list_streams_actions(self) -> list[dict[str, Any]]:
        return copy.deepcopy(self._state.get("streams_actions", []))