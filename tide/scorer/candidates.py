"""Build scorer candidates from stored prices and eviction risks."""

from sqlalchemy.orm import Session

from tide.catalog import Catalog
from tide.collectors.common import SPOT
from tide.collectors.eviction import UNKNOWN_BUCKET, p_evict_per_hour
from tide.collectors.store import latest_prices, latest_risks
from tide.models import EvictionRisk, Price
from tide.scorer.model import Candidate


def make_candidate(price: Price, risk: EvictionRisk | None, catalog: Catalog) -> Candidate | None:
    """Combine one price row with its eviction risk. None if the type left the catalogue."""
    spec = catalog.spec(price.cloud, price.instance_type)
    if spec is None:
        return None

    if price.pricing == SPOT:
        # No risk data yet: assume the worst bucket rather than zero risk.
        bucket = risk.bucket if risk else UNKNOWN_BUCKET
        p_evict = risk.p_evict_hour if risk else p_evict_per_hour(UNKNOWN_BUCKET)
    else:
        bucket, p_evict = None, 0.0  # on-demand is never evicted

    return Candidate(
        cloud=price.cloud,
        region=price.region,
        zone=price.zone,
        instance_type=price.instance_type,
        pricing=price.pricing,
        usd_per_hour=price.usd_per_hour,
        vcpus=price.vcpus,
        memory_gb=price.memory_gb,
        p_evict_hour=p_evict,
        gpu_model=price.gpu_model,
        gpu_count=price.gpu_count,
        gpu_memory_gb=price.gpu_memory_gb,
        reference_only=spec.reference_only,
        eviction_bucket=bucket,
    )


def load_candidates(session: Session, catalog: Catalog) -> list[Candidate]:
    """Candidates from the latest prices and risks (what `tide plan` uses)."""
    risks = latest_risks(session)
    candidates = []
    for price in latest_prices(session):
        risk = risks.get((price.cloud, price.region, price.instance_type))
        candidate = make_candidate(price, risk, catalog)
        if candidate:
            candidates.append(candidate)
    return candidates
