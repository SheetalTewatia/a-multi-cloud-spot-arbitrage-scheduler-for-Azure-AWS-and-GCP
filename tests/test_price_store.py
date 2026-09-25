"""Storing prices and reading the latest snapshot (needs Postgres)."""

from datetime import UTC, datetime, timedelta

import pytest

from tide.catalog import Catalog
from tide.collectors import run
from tide.collectors.common import ON_DEMAND, SPOT, PriceQuote
from tide.collectors.store import latest_prices, save_quotes

T0 = datetime(2026, 1, 1, tzinfo=UTC)


def quote(price: float, pricing: str = SPOT, zone: str | None = "us-east-1a") -> PriceQuote:
    return PriceQuote("aws", "us-east-1", zone, "m5.large", pricing, price, 2, 8)


def test_save_quotes_stores_normalized_prices(db_session):
    save_quotes(db_session, [quote(0.04)], T0)
    [row] = latest_prices(db_session)
    assert row.usd_per_vcpu_hour == pytest.approx(0.02)
    assert row.usd_per_gb_hour == pytest.approx(0.005)
    assert row.collected_at == T0


def test_latest_prices_returns_only_newest_per_key(db_session):
    save_quotes(db_session, [quote(0.04)], T0)
    save_quotes(db_session, [quote(0.03)], T0 + timedelta(minutes=10))
    rows = latest_prices(db_session)
    assert [r.usd_per_hour for r in rows] == [pytest.approx(0.03)]


def test_latest_prices_sorted_cheapest_first_and_filterable(db_session):
    save_quotes(
        db_session,
        [
            quote(0.096, ON_DEMAND, zone=None),
            quote(0.05, zone="us-east-1b"),
            quote(0.03, zone="us-east-1a"),
        ],
        T0,
    )
    assert [r.usd_per_hour for r in latest_prices(db_session)] == [0.03, 0.05, 0.096]
    assert len(latest_prices(db_session, pricing=SPOT)) == 2
    assert latest_prices(db_session, cloud="azure") == []


def test_collect_all_keeps_other_cloud_when_one_fails(monkeypatch):
    def broken(_catalog):
        raise RuntimeError("AWS credentials expired")

    monkeypatch.setattr(run.aws, "collect", broken)
    monkeypatch.setattr(run.azure, "collect", lambda _c: [quote(0.02)])

    empty = {"regions": [], "instance_types": {}}
    quotes, errors = run.collect_all(Catalog.model_validate({"aws": empty, "azure": empty}))

    assert len(quotes) == 1
    assert errors == {"aws": "AWS credentials expired"}
