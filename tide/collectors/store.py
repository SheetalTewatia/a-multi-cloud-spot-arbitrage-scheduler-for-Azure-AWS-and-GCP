"""Save price quotes to Postgres and read the latest snapshot back."""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import distinct_on
from sqlalchemy.orm import Session

from tide.collectors.common import PriceQuote
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
        )
        for q in quotes
    )
    return len(quotes)


def latest_prices(
    session: Session,
    cloud: str | None = None,
    region: str | None = None,
    pricing: str | None = None,
) -> list[Price]:
    """The most recent price for each (cloud, region, zone, instance type, pricing),
    cheapest per vCPU-hour first.

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

    rows = session.scalars(query).all()
    return sorted(rows, key=lambda p: p.usd_per_vcpu_hour)
