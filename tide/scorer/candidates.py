"""Build scorer candidates from the latest stored prices and eviction risks."""

from sqlalchemy.orm import Session

from tide.catalog import Catalog
from tide.collectors.common import SPOT
from tide.collectors.eviction import UNKNOWN_BUCKET, p_evict_per_hour
from tide.collectors.store import latest_prices, latest_risks
from tide.scorer.model import Candidate


def load_candidates(session: Session, catalog: Catalog) -> list[Candidate]:
    risks = latest_risks(session)
    candidates = []
    for p in latest_prices(session):
        spec = catalog.spec(p.cloud, p.instance_type)
        if spec is None:
            continue  # type was removed from the catalogue after it was priced

        if p.pricing == SPOT:
            risk = risks.get((p.cloud, p.region, p.instance_type))
            # No risk data yet: assume the worst bucket rather than zero risk.
            bucket = risk.bucket if risk else UNKNOWN_BUCKET
            p_evict = risk.p_evict_hour if risk else p_evict_per_hour(UNKNOWN_BUCKET)
        else:
            bucket, p_evict = None, 0.0  # on-demand is never evicted

        candidates.append(
            Candidate(
                cloud=p.cloud,
                region=p.region,
                zone=p.zone,
                instance_type=p.instance_type,
                pricing=p.pricing,
                usd_per_hour=p.usd_per_hour,
                vcpus=p.vcpus,
                memory_gb=p.memory_gb,
                p_evict_hour=p_evict,
                gpu_model=p.gpu_model,
                gpu_count=p.gpu_count,
                gpu_memory_gb=p.gpu_memory_gb,
                reference_only=spec.reference_only,
                eviction_bucket=bucket,
            )
        )
    return candidates
