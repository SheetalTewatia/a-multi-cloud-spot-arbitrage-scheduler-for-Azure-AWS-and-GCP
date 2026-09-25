"""Run every collector once and store the results."""

import logging
from datetime import UTC, datetime

from tide.catalog import Catalog
from tide.collectors import aws, azure
from tide.collectors.common import PriceQuote
from tide.collectors.store import save_quotes
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


def collect_and_store(catalog: Catalog) -> tuple[int, dict[str, str]]:
    """Collect from both clouds and save everything in one transaction."""
    quotes, errors = collect_all(catalog)
    collected_at = datetime.now(UTC)
    with SessionLocal.begin() as session:
        saved = save_quotes(session, quotes, collected_at)
    return saved, errors
