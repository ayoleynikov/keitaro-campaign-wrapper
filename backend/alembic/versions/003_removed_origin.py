"""removed_origin on stream offer bindings

Revision ID: 003
Revises: 002
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "stream_offer_bindings",
        sa.Column("removed_origin", sa.String(length=16), nullable=False, server_default="none"),
    )


def downgrade() -> None:
    op.drop_column("stream_offer_bindings", "removed_origin")