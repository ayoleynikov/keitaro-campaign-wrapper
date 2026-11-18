from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.allocation import AllocationError, OfferSlot, recalculate_shares
from app.keitaro.errors import KeitaroError
from app.keitaro.protocol import KeitaroClient
from app.live_guards import assert_campaign_id_allowed, assert_stream_write_allowed, write_allowlist_name
from app.models.stream_workspace import (
    OfferLifecycle,
    RemovedOrigin,
    StreamOfferBinding,
    StreamWorkspace,
    StreamWorkspaceEvent,
    SyncState,
)


class StreamEditorService:
    def __init__(self, client: KeitaroClient, db: Session) -> None:
        self._client = client
        self._db = db

    def _log(self, workspace_id: int, action: str, detail: dict | None = None) -> None:
        self._db.add(
            StreamWorkspaceEvent(
                workspace_id=workspace_id,
                action=action,
                detail_json=json.dumps(detail or {}, ensure_ascii=False),
            )
        )

    def _snapshot_bindings(self, workspace: StreamWorkspace) -> list[dict]:
        return [
            {
                "offer_id": b.offer_id,
                "share": b.share,
                "lifecycle": b.lifecycle,
                "is_pinned": b.is_pinned,
                "pinned_share": b.pinned_share,
                "is_new_unpublished": b.is_new_unpublished,
                "removed_origin": b.removed_origin,
            }
            for b in workspace.offers
        ]

    def _display_state(self, binding: StreamOfferBinding) -> str | None:
        if binding.lifecycle == OfferLifecycle.ACTIVE.value:
            return None
        if (
            binding.lifecycle == OfferLifecycle.REMOVED.value
            and binding.removed_origin == RemovedOrigin.UPSTREAM.value
        ):
            return "removed"
        return None

    def _save_baseline(self, workspace: StreamWorkspace) -> None:
        workspace.baseline_json = json.dumps(
            {"offers": self._snapshot_bindings(workspace)},
            ensure_ascii=False,
        )

    def _apply_recalc(self, workspace: StreamWorkspace) -> None:
        slots = [
            OfferSlot(
                offer_id=b.offer_id,
                removed=b.lifecycle != OfferLifecycle.ACTIVE.value,
                pinned=b.is_pinned,
                pinned_share=b.pinned_share if b.is_pinned else None,
            )
            for b in workspace.offers
        ]
        shares = recalculate_shares(slots)
        for b in workspace.offers:
            b.share = shares[b.offer_id]

    def _workspace_dto(self, workspace: StreamWorkspace) -> dict[str, Any]:
        return {
            "keitaro_stream_id": workspace.keitaro_stream_id,
            "keitaro_campaign_id": workspace.keitaro_campaign_id,
            "name": workspace.name,
            "has_offers": workspace.has_offers,
            "sync_state": workspace.sync_state,
            "offers": [
                {
                    "offer_id": b.offer_id,
                    "share": b.share,
                    "lifecycle": b.lifecycle,
                    "is_pinned": b.is_pinned,
                    "pinned_share": b.pinned_share,
                    "is_new_unpublished": b.is_new_unpublished,
                    "can_bring_back": b.lifecycle
                    in (OfferLifecycle.REMOVED.value, OfferLifecycle.ARCHIVED.value),
                    "removed_origin": b.removed_origin,
                    "state_label": self._display_state(b),
                }
                for b in workspace.offers
            ],
        }

    async def fetch_streams(self, campaign_id: int) -> list[dict[str, Any]]:
        if write_allowlist_name():
            await assert_campaign_id_allowed(self._client, campaign_id)
        upstream_streams = await self._client.list_streams(campaign_id)
        result: list[dict[str, Any]] = []

        for stream in upstream_streams:
            sid = int(stream["id"])
            offers = stream.get("offers") or []
            has_offers = len(offers) > 0

            workspace = self._db.scalar(
                select(StreamWorkspace).where(StreamWorkspace.keitaro_stream_id == sid)
            )
            if workspace is None:
                workspace = StreamWorkspace(
                    keitaro_stream_id=sid,
                    keitaro_campaign_id=campaign_id,
                    name=stream.get("name", ""),
                    has_offers=has_offers,
                    sync_state=SyncState.CLEAN.value,
                )
                self._db.add(workspace)
                self._db.flush()
            else:
                workspace.name = stream.get("name", workspace.name)
                workspace.has_offers = has_offers

            if not has_offers:
                self._log(workspace.id, "fetch_no_offers", {"stream_id": sid})
                self._db.commit()
                result.append(self._workspace_dto(workspace))
                continue

            upstream_ids = {int(o["offer_id"]): int(o.get("share", 0)) for o in offers}
            known_by_offer = {b.offer_id: b for b in workspace.offers}

            for oid, share in upstream_ids.items():
                row = known_by_offer.get(oid)
                if row is None:
                    workspace.offers.append(
                        StreamOfferBinding(
                            offer_id=oid,
                            share=share,
                            lifecycle=OfferLifecycle.ACTIVE.value,
                            is_new_unpublished=False,
                        )
                    )
                    continue
                if row.lifecycle in (
                    OfferLifecycle.REMOVED.value,
                    OfferLifecycle.ARCHIVED.value,
                ):
                    continue
                row.lifecycle = OfferLifecycle.ACTIVE.value
                if not row.is_pinned:
                    row.share = share
                else:
                    row.pinned_share = row.pinned_share or row.share
                row.is_new_unpublished = False

            for oid, row in list(known_by_offer.items()):
                if oid in upstream_ids:
                    continue
                if row.is_new_unpublished and workspace.sync_state == SyncState.DIRTY.value:
                    continue
                row.lifecycle = OfferLifecycle.REMOVED.value
                row.share = 0
                row.is_pinned = False
                row.pinned_share = None
                row.removed_origin = RemovedOrigin.UPSTREAM.value

            active_rows = [b for b in workspace.offers if b.lifecycle == OfferLifecycle.ACTIVE.value]
            if active_rows and not any(b.is_pinned for b in active_rows):
                self._apply_recalc(workspace)

            has_unpublished = any(b.is_new_unpublished for b in workspace.offers)
            if workspace.sync_state == SyncState.DIRTY.value and has_unpublished:
                self._log(
                    workspace.id,
                    "fetch_keep_dirty",
                    {"upstream_offers": list(upstream_ids.keys())},
                )
            else:
                self._save_baseline(workspace)
                workspace.sync_state = SyncState.CLEAN.value
                self._log(workspace.id, "fetch", {"upstream_offers": list(upstream_ids.keys())})
            self._db.commit()
            self._db.refresh(workspace)
            result.append(self._workspace_dto(workspace))

        return result

    def get_workspace(self, stream_id: int) -> dict[str, Any]:
        workspace = self._db.scalar(
            select(StreamWorkspace).where(StreamWorkspace.keitaro_stream_id == stream_id)
        )
        if not workspace:
            raise KeyError(f"No workspace for stream {stream_id}; run fetch-streams first")
        return self._workspace_dto(workspace)

    def _get_workspace(self, stream_id: int) -> StreamWorkspace:
        workspace = self._db.scalar(
            select(StreamWorkspace).where(StreamWorkspace.keitaro_stream_id == stream_id)
        )
        if not workspace:
            raise KeyError(f"No workspace for stream {stream_id}")
        if not workspace.has_offers:
            raise AllocationError("This stream has no offer rotation in the wrapper")
        return workspace

    def add_offer(self, stream_id: int, offer_id: int) -> dict[str, Any]:
        workspace = self._get_workspace(stream_id)
        if any(b.offer_id == offer_id and b.lifecycle == OfferLifecycle.ACTIVE.value for b in workspace.offers):
            raise AllocationError("Offer already active on this stream")
        existing = next((b for b in workspace.offers if b.offer_id == offer_id), None)
        if existing:
            existing.lifecycle = OfferLifecycle.ACTIVE.value
            existing.is_new_unpublished = True
            existing.is_pinned = False
            existing.pinned_share = None
            existing.removed_origin = RemovedOrigin.NONE.value
        else:
            workspace.offers.append(
                StreamOfferBinding(
                    offer_id=offer_id,
                    share=0,
                    lifecycle=OfferLifecycle.ACTIVE.value,
                    is_new_unpublished=True,
                    removed_origin=RemovedOrigin.NONE.value,
                )
            )
        self._apply_recalc(workspace)
        workspace.sync_state = SyncState.DIRTY.value
        self._log(workspace.id, "add", {"offer_id": offer_id})
        self._db.commit()
        self._db.refresh(workspace)
        return self._workspace_dto(workspace)

    def remove_offer(self, stream_id: int, offer_id: int) -> dict[str, Any]:
        workspace = self._get_workspace(stream_id)
        row = next((b for b in workspace.offers if b.offer_id == offer_id), None)
        if not row or row.lifecycle != OfferLifecycle.ACTIVE.value:
            raise AllocationError("Offer not found or already removed")
        row.lifecycle = OfferLifecycle.REMOVED.value
        row.share = 0
        row.is_pinned = False
        row.pinned_share = None
        row.removed_origin = RemovedOrigin.LOCAL.value
        self._apply_recalc(workspace)
        workspace.sync_state = SyncState.DIRTY.value
        self._log(workspace.id, "remove", {"offer_id": offer_id})
        self._db.commit()
        self._db.refresh(workspace)
        return self._workspace_dto(workspace)

    def restore_offer(self, stream_id: int, offer_id: int) -> dict[str, Any]:
        workspace = self._get_workspace(stream_id)
        row = next((b for b in workspace.offers if b.offer_id == offer_id), None)
        if not row or row.lifecycle not in (
            OfferLifecycle.REMOVED.value,
            OfferLifecycle.ARCHIVED.value,
        ):
            raise AllocationError("Offer is not in removed/archive state")
        row.lifecycle = OfferLifecycle.ACTIVE.value
        row.is_pinned = False
        row.pinned_share = None
        row.removed_origin = RemovedOrigin.NONE.value
        self._apply_recalc(workspace)
        workspace.sync_state = SyncState.DIRTY.value
        self._log(workspace.id, "restore", {"offer_id": offer_id})
        self._db.commit()
        self._db.refresh(workspace)
        return self._workspace_dto(workspace)

    def pin_offer(self, stream_id: int, offer_id: int, share: int | None = None) -> dict[str, Any]:
        workspace = self._get_workspace(stream_id)
        row = next(
            (b for b in workspace.offers if b.offer_id == offer_id and b.lifecycle == OfferLifecycle.ACTIVE.value),
            None,
        )
        if not row:
            raise AllocationError("Active offer not found")
        pin_val = share if share is not None else row.share
        if pin_val < 0 or pin_val > 100:
            raise AllocationError("Invalid pin share")
        other_pinned = sum(
            int(b.pinned_share or 0)
            for b in workspace.offers
            if b.is_pinned and b.offer_id != offer_id and b.lifecycle == OfferLifecycle.ACTIVE.value
        )
        if other_pinned + pin_val > 100:
            raise AllocationError("Pinned shares cannot exceed 100%")
        row.is_pinned = True
        row.pinned_share = pin_val
        row.share = pin_val
        self._apply_recalc(workspace)
        workspace.sync_state = SyncState.DIRTY.value
        self._log(workspace.id, "pin", {"offer_id": offer_id, "share": pin_val})
        self._db.commit()
        self._db.refresh(workspace)
        return self._workspace_dto(workspace)

    def unpin_offer(self, stream_id: int, offer_id: int) -> dict[str, Any]:
        workspace = self._get_workspace(stream_id)
        row = next((b for b in workspace.offers if b.offer_id == offer_id), None)
        if not row or not row.is_pinned:
            raise AllocationError("Offer is not pinned")
        row.is_pinned = False
        row.pinned_share = None
        self._apply_recalc(workspace)
        workspace.sync_state = SyncState.DIRTY.value
        self._log(workspace.id, "unpin", {"offer_id": offer_id})
        self._db.commit()
        self._db.refresh(workspace)
        return self._workspace_dto(workspace)

    def cancel(self, stream_id: int) -> dict[str, Any]:
        workspace = self._get_workspace(stream_id)
        if workspace.sync_state != SyncState.DIRTY.value:
            return self._workspace_dto(workspace)

        if not workspace.baseline_json:
            for row in list(workspace.offers):
                if row.is_new_unpublished:
                    workspace.offers.remove(row)
                    self._db.delete(row)
            workspace.sync_state = SyncState.CLEAN.value
            self._db.commit()
            return self._workspace_dto(workspace)

        baseline = json.loads(workspace.baseline_json)
        for row in list(workspace.offers):
            self._db.delete(row)
        workspace.offers.clear()
        self._db.flush()
        for snap in baseline.get("offers", []):
            workspace.offers.append(
                StreamOfferBinding(
                    offer_id=int(snap["offer_id"]),
                    share=int(snap["share"]),
                    lifecycle=str(snap["lifecycle"]),
                    is_pinned=bool(snap.get("is_pinned")),
                    pinned_share=snap.get("pinned_share"),
                    is_new_unpublished=bool(snap.get("is_new_unpublished")),
                    removed_origin=str(snap.get("removed_origin", RemovedOrigin.NONE.value)),
                )
            )

        workspace.sync_state = SyncState.CLEAN.value
        self._log(workspace.id, "cancel", {})
        self._db.commit()
        self._db.refresh(workspace)
        return self._workspace_dto(workspace)

    async def push(self, stream_id: int) -> dict[str, Any]:
        if write_allowlist_name():
            await assert_stream_write_allowed(self._client, stream_id)
        workspace = self._get_workspace(stream_id)
        if write_allowlist_name():
            await assert_campaign_id_allowed(self._client, int(workspace.keitaro_campaign_id))
        if workspace.sync_state != SyncState.DIRTY.value:
            return self._workspace_dto(workspace)

        active = [b for b in workspace.offers if b.lifecycle == OfferLifecycle.ACTIVE.value]
        if not active:
            raise AllocationError("Cannot push stream with no active offers")

        self._apply_recalc(workspace)
        payload_offers = [
            {"offer_id": b.offer_id, "share": b.share, "state": "active"}
            for b in active
        ]

        try:
            await self._client.update_stream(stream_id, {"offers": payload_offers})
        except KeitaroError:
            self._log(workspace.id, "push_failed", {"offers": payload_offers})
            self._db.commit()
            raise

        for b in workspace.offers:
            if b.lifecycle == OfferLifecycle.REMOVED.value and b.removed_origin == RemovedOrigin.LOCAL.value:
                b.lifecycle = OfferLifecycle.ARCHIVED.value
                b.share = 0
            b.is_new_unpublished = False

        workspace.sync_state = SyncState.CLEAN.value
        self._save_baseline(workspace)
        self._log(workspace.id, "push", {"offers": payload_offers})
        self._db.commit()
        self._db.refresh(workspace)
        return self._workspace_dto(workspace)