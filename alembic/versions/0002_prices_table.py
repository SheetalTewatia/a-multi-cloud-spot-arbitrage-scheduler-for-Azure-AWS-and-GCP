"""prices table: every collected spot and on-demand price (append-only history)

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-25

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | Sequence[str] | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "prices",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("cloud", sa.String(length=10), nullable=False),
        sa.Column("region", sa.String(length=40), nullable=False),
        sa.Column("zone", sa.String(length=40), nullable=True),
        sa.Column("instance_type", sa.String(length=40), nullable=False),
        sa.Column("pricing", sa.String(length=10), nullable=False),
        sa.Column("usd_per_hour", sa.Double(), nullable=False),
        sa.Column("vcpus", sa.Integer(), nullable=False),
        sa.Column("memory_gb", sa.Double(), nullable=False),
        sa.Column("usd_per_vcpu_hour", sa.Double(), nullable=False),
        sa.Column("usd_per_gb_hour", sa.Double(), nullable=False),
        sa.CheckConstraint("cloud IN ('aws', 'azure')", name="ck_prices_cloud"),
        sa.CheckConstraint("pricing IN ('spot', 'on_demand')", name="ck_prices_pricing"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_prices_latest",
        "prices",
        ["cloud", "region", "instance_type", "pricing", "collected_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_prices_latest", table_name="prices")
    op.drop_table("prices")
