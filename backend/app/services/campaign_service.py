from __future__ import annotations

import json
import re
from typing import Any

from sqlalchemy.orm import Session

from app.config import get_settings
from app.domain.allocation import normalize_shares
from app.domain.streams import build_geo_redirect_stream, build_offer_fallback_stream, build_offer_rotation_payload
from app.keitaro.errors import KeitaroError, KeitaroTimeoutError, PartialCreateError, WriteGuardError
from app.keitaro.protocol import KeitaroClient
from app.live_guards import (
    assert_campaign_name_allowed,
    assert_stream_write_allowed,
    write_allowlist_name,
)
from app.models.operation import Operation, OperationStatus
from app.services.metadata_service import resolve_country_filter_name, resolve_redirect_action_type


def _slug_from_name(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug[:64] or "campaign"


class CampaignService:
    def __init__(self, client: KeitaroClient, db: Session) -> None:
        self._client = client
        self._db = db

    async def find_campaign_by_name(self, name: str) -> dict[str, Any] | None:
        offset = 0
        limit = 100
        seen: set[int] = set()
        while offset <= 10000:
            batch = await self._client.list_campaigns(offset=offset, limit=limit)
            if not batch:
                return None
            for campaign in batch:
                try:
                    cid = int(campaign.get("id"))
                except (TypeError, ValueError):
                    continue
                if cid in seen:
                    return None
                seen.add(cid)
                if campaign.get("name") == name:
                    return campaign
            if len(batch) < limit:
                return None
            offset += limit
        return None

    async def create_campaign_with_streams(self, data: dict[str, Any]) -> tuple[Operation, dict[str, Any]]:
        settings = get_settings()
        name = data["name"]
        assert_campaign_name_allowed(name)

        existing = await self.find_campaign_by_name(name)
        if existing:
            raise WriteGuardError(
                f"Campaign {name!r} already exists upstream (id={existing.get('id')}); refusing to create another",
                status_code=409,
            )

        op = Operation(
            kind="create_campaign",
            status=OperationStatus.IN_PROGRESS.value,
            request_payload=json.dumps(data, ensure_ascii=False),
        )
        self._db.add(op)
        self._db.commit()
        self._db.refresh(op)

        created: dict[str, list[int]] = {"campaign_ids": [], "stream_ids": []}
        try:
            alias = data.get("alias") or _slug_from_name(data["name"])
            state = (settings.keitaro_create_campaign_state or "active").strip().lower()
            if state not in {"active", "disabled"}:
                state = "active"
            campaign_payload = {
                "name": data["name"],
                "alias": alias,
                "type": "position",
                "domain_id": data["domain_id"],
                "group_id": data["group_id"],
                "traffic_source_id": data["traffic_source_id"],
                "state": state,
            }
            try:
                campaign = await self._client.create_campaign(campaign_payload)
            except KeitaroTimeoutError:
                after = await self.find_campaign_by_name(name)
                if after:
                    cid = int(after["id"])
                    created["campaign_ids"].append(cid)
                    op.status = OperationStatus.FAILED.value
                    op.keitaro_campaign_id = cid
                    op.created_resource_ids = json.dumps(created)
                    op.error_message = (
                        "Timeout after campaign POST; campaign already exists upstream. "
                        "Not retrying and not deleting."
                    )
                    self._db.commit()
                    raise PartialCreateError(op.error_message, status_code=504) from None
                raise

            cid = int(campaign["id"])
            created["campaign_ids"].append(cid)

            filter_name = await resolve_country_filter_name()
            action_type = await resolve_redirect_action_type()
            stream_geo = await self._client.create_stream(
                build_geo_redirect_stream(
                    campaign_id=cid,
                    geo_iso=data["geo_iso"],
                    position=1,
                    filter_name=filter_name,
                    action_type=action_type,
                )
            )
            created["stream_ids"].append(int(stream_geo["id"]))

            stream_offer = await self._client.create_stream(
                build_offer_fallback_stream(
                    campaign_id=cid,
                    offer_id=int(data["offer_id"]),
                    position=2,
                )
            )
            created["stream_ids"].append(int(stream_offer["id"]))

            op.status = OperationStatus.SUCCEEDED.value
            op.keitaro_campaign_id = cid
            op.created_resource_ids = json.dumps(created)
            self._db.commit()

            return op, {
                "campaign": campaign,
                "streams": [stream_geo, stream_offer],
            }
        except PartialCreateError:
            raise
        except KeitaroError as exc:
            if not settings.keitaro_disable_compensation:
                await self._compensate(created)
                op.status = (
                    OperationStatus.COMPENSATED.value
                    if created["campaign_ids"] or created["stream_ids"]
                    else OperationStatus.FAILED.value
                )
            else:
                op.status = OperationStatus.FAILED.value
            op.error_message = str(exc)
            if created.get("campaign_ids"):
                op.keitaro_campaign_id = created["campaign_ids"][0]
            op.created_resource_ids = json.dumps(created)
            self._db.commit()
            if settings.keitaro_disable_compensation and (
                created["campaign_ids"] or created["stream_ids"]
            ):
                raise PartialCreateError(
                    "Partial campaign/stream create failed; compensation DELETE skipped. "
                    f"created={created}. original={exc}",
                    status_code=exc.status_code or 502,
                ) from exc
            raise
        except Exception as exc:
            if not settings.keitaro_disable_compensation:
                await self._compensate(created)
                op.status = OperationStatus.FAILED.value
            else:
                op.status = OperationStatus.FAILED.value
            op.error_message = str(exc)
            if created.get("campaign_ids"):
                op.keitaro_campaign_id = created["campaign_ids"][0]
            op.created_resource_ids = json.dumps(created)
            self._db.commit()
            if settings.keitaro_disable_compensation and (
                created["campaign_ids"] or created["stream_ids"]
            ):
                raise PartialCreateError(
                    "Partial campaign/stream create failed; compensation DELETE skipped. "
                    f"created={created}. original={exc}",
                    status_code=500,
                ) from exc
            raise

    async def _compensate(self, created: dict[str, list[int]]) -> None:
        if get_settings().keitaro_disable_compensation or get_settings().keitaro_forbid_delete:
            return
        for sid in reversed(created.get("stream_ids", [])):
            try:
                await self._client.delete_stream(sid)
            except KeitaroError:
                pass
        for cid in created.get("campaign_ids", []):
            try:
                await self._client.delete_campaign(cid)
            except KeitaroError:
                pass

    async def update_stream_offers(
        self,
        stream_id: int,
        offers: list[tuple[int, int | float | None]],
    ) -> dict[str, Any]:
        if write_allowlist_name():
            await assert_stream_write_allowed(self._client, stream_id)
        stream = await self._client.get_stream(stream_id)
        normalized = normalize_shares(offers)
        payload = build_offer_rotation_payload(
            [{"offer_id": oid, "share": share, "state": "active"} for oid, share in normalized]
        )
        updated = await self._client.update_stream(stream_id, payload)
        op = Operation(
            kind="update_stream_offers",
            status=OperationStatus.SUCCEEDED.value,
            request_payload=json.dumps({"stream_id": stream_id, "offers": payload["offers"]}),
            keitaro_campaign_id=stream.get("campaign_id"),
        )
        self._db.add(op)
        self._db.commit()
        return updated
