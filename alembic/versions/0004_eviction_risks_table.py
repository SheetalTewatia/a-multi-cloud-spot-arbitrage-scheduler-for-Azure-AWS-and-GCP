"""eviction risks table: p_evict per hour for each (cloud, region, instance type)

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-26

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | Sequence[str] | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "eviction_risks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("cloud", sa.String(length=10), nullable=False),
        sa.Column("region", sa.String(length=40), nullable=False),
        sa.Column("instance_type", sa.String(length=40), nullable=False),
        sa.Column("bucket", sa.String(length=10), nullable=False),
        sa.Column("p_evict_hour", sa.Double(), nullable=False),
        sa.Column("source", sa.String(length=30), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_eviction_risks_latest",
        "eviction_risks",
        ["cloud", "region", "instance_type", "collected_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_eviction_risks_latest", table_name="eviction_risks")
    op.drop_table("eviction_risks")
