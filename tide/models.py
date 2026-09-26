"""SQLAlchemy models. Bills arrive in a later phase."""

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


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


class EvictionRisk(Base):
    """Eviction risk per (cloud, region, instance type), appended on every collection."""

    __tablename__ = "eviction_risks"

    id: Mapped[int] = mapped_column(primary_key=True)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    cloud: Mapped[str] = mapped_column(String(10))
    region: Mapped[str] = mapped_column(String(40))
    instance_type: Mapped[str] = mapped_column(String(40))
    bucket: Mapped[str] = mapped_column(String(10))  # monthly interruption bucket, e.g. "5-10%"
    p_evict_hour: Mapped[float]
    source: Mapped[str] = mapped_column(String(30))

    __table_args__ = (
        Index("ix_eviction_risks_latest", "cloud", "region", "instance_type", "collected_at"),
    )


class Run(Base):
    """One workload run (simulated for now; real runs from Phase 5) and its savings totals."""

    __tablename__ = "runs"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)  # also the tide-run-id tag
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    mode: Mapped[str] = mapped_column(String(20))  # "simulation"
    workload_name: Mapped[str] = mapped_column(String(100))
    workload: Mapped[dict] = mapped_column(JSONB)  # the workload file as given
    params: Mapped[dict] = mapped_column(JSONB)  # seed, eviction multiplier, replay window...
    status: Mapped[str] = mapped_column(String(20))  # "finished" or "failed"
    met_deadline: Mapped[bool]
    hours_elapsed: Mapped[float]
    tide_cost: Mapped[float]
    on_demand_same: Mapped[float]
    on_demand_cheapest: Mapped[float | None]
    migrations: Mapped[int]
    evictions: Mapped[int]
    instance_hours: Mapped[float]
    gpu_hours: Mapped[float]

    decisions: Mapped[list[Decision]] = relationship(
        back_populates="run", order_by="Decision.id", cascade="all, delete-orphan"
    )

    __table_args__ = (CheckConstraint("mode IN ('simulation', 'live')", name="ck_runs_mode"),)


class Decision(Base):
    """One event in a run: place, migrate, evicted, finish or failed.

    For place and migrate, `candidates` holds every option that was scored at that moment,
    with its effective cost or the reason it was rejected. This is the audit trail.
    """

    __tablename__ = "decisions"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), index=True)
    at_hours: Mapped[float]  # hours since the run started
    at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))  # replayed clock time
    kind: Mapped[str] = mapped_column(String(20))
    reason: Mapped[str] = mapped_column(String(200))
    cloud: Mapped[str | None] = mapped_column(String(10))
    region: Mapped[str | None] = mapped_column(String(40))
    zone: Mapped[str | None] = mapped_column(String(40))
    instance_type: Mapped[str | None] = mapped_column(String(40))
    pricing: Mapped[str | None] = mapped_column(String(10))
    usd_per_hour: Mapped[float | None]
    candidates: Mapped[list | None] = mapped_column(JSONB)

    run: Mapped[Run] = relationship(back_populates="decisions")
