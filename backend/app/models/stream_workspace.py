from __future__ import annotations

import enum
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class SyncState(str, enum.Enum):
    CLEAN = "clean"
    DIRTY = "dirty"


class OfferLifecycle(str, enum.Enum):
    ACTIVE = "active"
    REMOVED = "removed"
    ARCHIVED = "archived"


class RemovedOrigin(str, enum.Enum):
    NONE = "none"
    LOCAL = "local"
    UPSTREAM = "upstream"


class StreamWorkspace(Base):
    __tablename__ = "stream_workspaces"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    keitaro_stream_id: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    keitaro_campaign_id: Mapped[int] = mapped_column(Integer, index=True)
    name: Mapped[str] = mapped_column(String(256), default="")
    has_offers: Mapped[bool] = mapped_column(Boolean, default=True)
    sync_state: Mapped[str] = mapped_column(String(16), default=SyncState.CLEAN.value)
    baseline_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    offers: Mapped[list[StreamOfferBinding]] = relationship(
        back_populates="workspace",
        cascade="all, delete-orphan",
        order_by="StreamOfferBinding.id",
    )


class StreamOfferBinding(Base):
    __tablename__ = "stream_offer_bindings"
    __table_args__ = (UniqueConstraint("workspace_id", "offer_id", name="uq_workspace_offer"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("stream_workspaces.id", ondelete="CASCADE"))
    offer_id: Mapped[int] = mapped_column(Integer, index=True)
    share: Mapped[int] = mapped_column(Integer, default=0)
    lifecycle: Mapped[str] = mapped_column(String(16), default=OfferLifecycle.ACTIVE.value)
    is_pinned: Mapped[bool] = mapped_column(Boolean, default=False)
    pinned_share: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_new_unpublished: Mapped[bool] = mapped_column(Boolean, default=False)
    removed_origin: Mapped[str] = mapped_column(String(16), default=RemovedOrigin.NONE.value)

    workspace: Mapped[StreamWorkspace] = relationship(back_populates="offers")


class StreamWorkspaceEvent(Base):
    __tablename__ = "stream_workspace_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("stream_workspaces.id", ondelete="CASCADE"))
    action: Mapped[str] = mapped_column(String(32))
    detail_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )