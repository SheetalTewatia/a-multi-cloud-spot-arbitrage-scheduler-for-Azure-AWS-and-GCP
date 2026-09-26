"""Run every collector once and store the results."""

import logging
from datetime import UTC, datetime

from tide.catalog import Catalog
from tide.collectors import aws, azure, eviction
from tide.collectors.common import PriceQuote
from tide.collectors.eviction import EvictionRisk
from tide.collectors.store import save_quotes, save_risks
from tide.db import SessionLocal

log = logging.getLogger(__name__)


def collect_all(catalog: Catalog) -> tuple[list[PriceQuote], dict[str, str]]:
    """Collect from both clouds. A failure in one cloud is recorded, not raised,
    so one provider's outage doesn't stop us from storing the other's prices.

    Returns (quotes, errors) where errors maps cloud name -> error message.
    """
    quotes: list[PriceQuote] = []
    errors: dict[str, str] = {}
    for name, collector, cloud_catalog in [
        ("aws", aws.collect, catalog.aws),
        ("azure", azure.collect, catalog.azure),
    ]:
        try:
            cloud_quotes = collector(cloud_catalog)
            log.info("collected %d %s quotes", len(cloud_quotes), name)
            quotes += cloud_quotes
        except Exception as exc:
            log.exception("%s collector failed", name)
            errors[name] = str(exc)
    return quotes, errors


def collect_risks(catalog: Catalog, errors: dict[str, str]) -> list[EvictionRisk]:
    """Collect eviction risks; on failure record the error and return nothing."""
    try:
        risks = eviction.collect(catalog)
        log.info("collected %d eviction risks", len(risks))
        return risks
    except Exception as exc:
        log.exception("eviction collector failed")
        errors["eviction"] = str(exc)
        return []


def collect_and_store(catalog: Catalog) -> tuple[int, int, dict[str, str]]:
    """Collect prices and eviction risks, and save everything in one transaction.

    Returns (prices saved, risks saved, errors).
    """
    quotes, errors = collect_all(catalog)
    risks = collect_risks(catalog, errors)
    collected_at = datetime.now(UTC)
    with SessionLocal.begin() as session:
        saved_prices = save_quotes(session, quotes, collected_at)
        saved_risks = save_risks(session, risks, collected_at)
    return saved_prices, saved_risks, errors
