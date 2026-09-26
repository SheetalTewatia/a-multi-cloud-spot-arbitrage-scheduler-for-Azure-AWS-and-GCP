"""runs and decisions: savings totals per run, and the audit trail of every decision

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-26

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005"
down_revision: str | Sequence[str] | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "runs",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("mode", sa.String(length=20), nullable=False),
        sa.Column("workload_name", sa.String(length=100), nullable=False),
        sa.Column("workload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("params", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("met_deadline", sa.Boolean(), nullable=False),
        sa.Column("hours_elapsed", sa.Double(), nullable=False),
        sa.Column("tide_cost", sa.Double(), nullable=False),
        sa.Column("on_demand_same", sa.Double(), nullable=False),
        sa.Column("on_demand_cheapest", sa.Double(), nullable=True),
        sa.Column("migrations", sa.Integer(), nullable=False),
        sa.Column("evictions", sa.Integer(), nullable=False),
        sa.Column("instance_hours", sa.Double(), nullable=False),
        sa.Column("gpu_hours", sa.Double(), nullable=False),
        sa.CheckConstraint("mode IN ('simulation', 'live')", name="ck_runs_mode"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "decisions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.String(length=40), nullable=False),
        sa.Column("at_hours", sa.Double(), nullable=False),
        sa.Column("at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("reason", sa.String(length=200), nullable=False),
        sa.Column("cloud", sa.String(length=10), nullable=True),
        sa.Column("region", sa.String(length=40), nullable=True),
        sa.Column("zone", sa.String(length=40), nullable=True),
        sa.Column("instance_type", sa.String(length=40), nullable=True),
        sa.Column("pricing", sa.String(length=10), nullable=True),
        sa.Column("usd_per_hour", sa.Double(), nullable=True),
        sa.Column("candidates", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_decisions_run_id"), "decisions", ["run_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_decisions_run_id"), table_name="decisions")
    op.drop_table("decisions")
    op.drop_table("runs")
