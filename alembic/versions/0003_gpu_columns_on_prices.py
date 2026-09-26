"""gpu columns on prices: model, count, memory and USD per GPU-hour (NULL for CPU types)

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-26

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | Sequence[str] | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("prices", sa.Column("gpu_model", sa.String(length=20), nullable=True))
    op.add_column("prices", sa.Column("gpu_count", sa.Integer(), nullable=True))
    op.add_column("prices", sa.Column("gpu_memory_gb", sa.Double(), nullable=True))
    op.add_column("prices", sa.Column("usd_per_gpu_hour", sa.Double(), nullable=True))


def downgrade() -> None:
    op.drop_column("prices", "usd_per_gpu_hour")
    op.drop_column("prices", "gpu_memory_gb")
    op.drop_column("prices", "gpu_count")
    op.drop_column("prices", "gpu_model")
