"""Save price quotes to Postgres and read the latest snapshot back."""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import distinct_on
from sqlalchemy.orm import Session

from tide.collectors.common import PriceQuote
from tide.collectors.eviction import EvictionRisk
from tide.models import EvictionRisk as EvictionRiskRow
from tide.models import Price


def save_quotes(session: Session, quotes: list[PriceQuote], collected_at: datetime) -> int:
    """Append one row per quote, all stamped with the same collection time."""
    session.add_all(
        Price(
            collected_at=collected_at,
            cloud=q.cloud,
            region=q.region,
            zone=q.zone,
            instance_type=q.instance_type,
            pricing=q.pricing,
            usd_per_hour=q.usd_per_hour,
            vcpus=q.vcpus,
            memory_gb=q.memory_gb,
            usd_per_vcpu_hour=q.usd_per_vcpu_hour,
            usd_per_gb_hour=q.usd_per_gb_hour,
            gpu_model=q.gpu_model,
            gpu_count=q.gpu_count,
            gpu_memory_gb=q.gpu_memory_gb,
            usd_per_gpu_hour=q.usd_per_gpu_hour,
        )
        for q in quotes
    )
    return len(quotes)


def latest_prices(
    session: Session,
    cloud: str | None = None,
    region: str | None = None,
    pricing: str | None = None,
    gpu: bool | None = None,
) -> list[Price]:
    """The most recent price for each (cloud, region, zone, instance type, pricing).

    gpu=True returns only GPU types, cheapest per GPU-hour first; gpu=False only CPU types,
    and None returns both. Otherwise results are sorted cheapest per vCPU-hour first.

    Uses Postgres DISTINCT ON: sort each group newest-first and keep the first row.
    """
    key = (Price.cloud, Price.region, Price.zone, Price.instance_type, Price.pricing)
    query = select(Price).ext(distinct_on(*key)).order_by(*key, Price.collected_at.desc())
    if cloud:
        query = query.where(Price.cloud == cloud)
    if region:
        query = query.where(Price.region == region)
    if pricing:
        query = query.where(Price.pricing == pricing)
    if gpu is True:
        query = query.where(Price.gpu_model.is_not(None))
    elif gpu is False:
        query = query.where(Price.gpu_model.is_(None))

    rows = session.scalars(query).all()
    if gpu:
        return sorted(rows, key=lambda p: p.usd_per_gpu_hour)
    return sorted(rows, key=lambda p: p.usd_per_vcpu_hour)


def save_risks(session: Session, risks: list[EvictionRisk], collected_at: datetime) -> int:
    session.add_all(
        EvictionRiskRow(
            collected_at=collected_at,
            cloud=r.cloud,
            region=r.region,
            instance_type=r.instance_type,
            bucket=r.bucket,
            p_evict_hour=r.p_evict_hour,
            source=r.source,
        )
        for r in risks
    )
    return len(risks)


def latest_risks(session: Session) -> dict[tuple[str, str, str], EvictionRiskRow]:
    """Most recent eviction risk, keyed by (cloud, region, instance_type)."""
    key = (EvictionRiskRow.cloud, EvictionRiskRow.region, EvictionRiskRow.instance_type)
    query = (
        select(EvictionRiskRow)
        .ext(distinct_on(*key))
        .order_by(*key, EvictionRiskRow.collected_at.desc())
    )
    return {(r.cloud, r.region, r.instance_type): r for r in session.scalars(query)}
