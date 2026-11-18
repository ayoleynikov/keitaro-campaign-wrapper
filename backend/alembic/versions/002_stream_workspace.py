"""stream workspace editor state

Revision ID: 002
Revises: 001
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "stream_workspaces",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("keitaro_stream_id", sa.Integer(), nullable=False),
        sa.Column("keitaro_campaign_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=256), nullable=False),
        sa.Column("has_offers", sa.Boolean(), nullable=False),
        sa.Column("sync_state", sa.String(length=16), nullable=False),
        sa.Column("baseline_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_stream_workspaces_keitaro_campaign_id"), "stream_workspaces", ["keitaro_campaign_id"])
    op.create_index(op.f("ix_stream_workspaces_keitaro_stream_id"), "stream_workspaces", ["keitaro_stream_id"], unique=True)

    op.create_table(
        "stream_offer_bindings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("offer_id", sa.Integer(), nullable=False),
        sa.Column("share", sa.Integer(), nullable=False),
        sa.Column("lifecycle", sa.String(length=16), nullable=False),
        sa.Column("is_pinned", sa.Boolean(), nullable=False),
        sa.Column("pinned_share", sa.Integer(), nullable=True),
        sa.Column("is_new_unpublished", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["stream_workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_id", "offer_id", name="uq_workspace_offer"),
    )
    op.create_index(op.f("ix_stream_offer_bindings_offer_id"), "stream_offer_bindings", ["offer_id"])

    op.create_table(
        "stream_workspace_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("detail_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["stream_workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("stream_workspace_events")
    op.drop_table("stream_offer_bindings")
    op.drop_index(op.f("ix_stream_workspaces_keitaro_stream_id"), table_name="stream_workspaces")
    op.drop_index(op.f("ix_stream_workspaces_keitaro_campaign_id"), table_name="stream_workspaces")
    op.drop_table("stream_workspaces")