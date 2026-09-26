"""Replay stored price history as a price feed for the scheduler loop.

Each `tide collect` is one snapshot. Snapshots are merged forward in time: a price that is
missing from one collection (say AWS failed that time) keeps its last known value.
During a replay, time t uses the latest snapshot at or before start + t; past the end of
the history, the last snapshot's prices are held constant.
"""

from bisect import bisect_right
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from tide.catalog import Catalog
from tide.models import EvictionRisk, Price
from tide.scorer.candidates import make_candidate
from tide.scorer.model import Candidate


@dataclass
class Snapshot:
    at: datetime
    candidates: list[Candidate]


def build_snapshots(
    prices: list[Price], risks: list[EvictionRisk], catalog: Catalog
) -> list[Snapshot]:
    """prices and risks must be sorted by collected_at."""
    snapshots: list[Snapshot] = []
    price_state: dict[tuple, Price] = {}
    risk_state: dict[tuple, EvictionRisk] = {}
    next_risk = 0

    by_time: dict[datetime, list[Price]] = {}
    for p in prices:
        by_time.setdefault(p.collected_at, []).append(p)

    for at, rows in by_time.items():
        for p in rows:
            price_state[(p.cloud, p.region, p.zone, p.instance_type, p.pricing)] = p
        while next_risk < len(risks) and risks[next_risk].collected_at <= at:
            r = risks[next_risk]
            risk_state[(r.cloud, r.region, r.instance_type)] = r
            next_risk += 1

        candidates = []
        for p in price_state.values():
            c = make_candidate(p, risk_state.get((p.cloud, p.region, p.instance_type)), catalog)
            if c:
                candidates.append(c)
        snapshots.append(Snapshot(at, candidates))
    return snapshots


def load_snapshots(session: Session, catalog: Catalog) -> list[Snapshot]:
    prices = list(session.scalars(select(Price).order_by(Price.collected_at, Price.id)))
    risks = list(session.scalars(select(EvictionRisk).order_by(EvictionRisk.collected_at)))
    return build_snapshots(prices, risks, catalog)


def first_usable(snapshots: list[Snapshot], usable: Callable[[list[Candidate]], bool]) -> datetime:
    """The earliest snapshot time where `usable(candidates)` is true, e.g. the first
    collection that priced a GPU type the workload can use."""
    for snapshot in snapshots:
        if usable(snapshot.candidates):
            return snapshot.at
    raise ValueError("no stored snapshot has an option that can run this workload")


class ReplayFeed:
    """Callable price feed: feed(t_hours) -> candidates in effect at start + t."""

    def __init__(self, snapshots: list[Snapshot], start: datetime | None = None):
        if not snapshots:
            raise ValueError("no price history stored; run `tide collect` first")
        self.snapshots = snapshots
        self.times = [s.at for s in snapshots]
        self.start = start or self.times[0]
        if self.start < self.times[0]:
            raise ValueError(f"start is before the first stored prices ({self.times[0]})")

    def at(self, t_hours: float) -> datetime:
        return self.start + timedelta(hours=t_hours)

    def __call__(self, t_hours: float) -> list[Candidate]:
        index = bisect_right(self.times, self.at(t_hours)) - 1
        return self.snapshots[index].candidates

    def snapshots_used(self, hours: float) -> int:
        """How many distinct snapshots a run of `hours` actually saw."""
        first = bisect_right(self.times, self.start) - 1
        last = bisect_right(self.times, self.at(hours)) - 1
        return last - first + 1
