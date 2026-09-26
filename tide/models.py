"""SQLAlchemy models. Decisions, runs and bills arrive in later phases."""

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Index, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Price(Base):
    """One collected hourly price. Every collection run appends rows; nothing is overwritten,
    so the table is also the price history that simulation mode replays later."""

    __tablename__ = "prices"

    id: Mapped[int] = mapped_column(primary_key=True)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    cloud: Mapped[str] = mapped_column(String(10))
    region: Mapped[str] = mapped_column(String(40))
    zone: Mapped[str | None] = mapped_column(String(40))  # AWS spot only
    instance_type: Mapped[str] = mapped_column(String(40))
    pricing: Mapped[str] = mapped_column(String(10))
    usd_per_hour: Mapped[float]
    vcpus: Mapped[int]
    memory_gb: Mapped[float]
    usd_per_vcpu_hour: Mapped[float]
    usd_per_gb_hour: Mapped[float]
    # GPU instance types only (NULL for CPU types)
    gpu_model: Mapped[str | None] = mapped_column(String(20))
    gpu_count: Mapped[int | None]
    gpu_memory_gb: Mapped[float | None]
    usd_per_gpu_hour: Mapped[float | None]

    __table_args__ = (
        CheckConstraint("cloud IN ('aws', 'azure')", name="ck_prices_cloud"),
        CheckConstraint("pricing IN ('spot', 'on_demand')", name="ck_prices_pricing"),
        Index("ix_prices_latest", "cloud", "region", "instance_type", "pricing", "collected_at"),
    )
