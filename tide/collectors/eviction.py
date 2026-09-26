"""Eviction-risk collector: an eviction probability per hour (p_evict) for each
(cloud, region, instance type).

AWS:   the public Spot Instance Advisor feed. For every type and region it gives a bucket
       for the "frequency of interruption" over the trailing month: <5%, 5-10%, ... >20%.
Azure: a static table in catalog.yaml. The real data (Azure Resource Graph SpotResources)
       needs credentials; until then the values are assumptions, and are labelled as such.

Converting a monthly bucket to a per-hour probability (an assumption, kept simple):
take the middle of the bucket and spread it evenly over the 730 hours in a month.
  "5-10%" -> 7.5% per month -> 0.075 / 730 = 0.0001 per hour
"""

from dataclasses import dataclass

import httpx2

from tide.catalog import Catalog

AWS_SPOT_ADVISOR_URL = "https://spot-bid-advisor.s3.amazonaws.com/spot-advisor-data.json"
HOURS_PER_MONTH = 730

# Middle of each monthly bucket. ">20%" has no upper bound, so we assume 25%.
BUCKET_MONTHLY_RATE = {
    "<5%": 0.025,
    "5-10%": 0.075,
    "10-15%": 0.125,
    "15-20%": 0.175,
    ">20%": 0.25,
}
# Used when a source has no data for a type: assume the worst bucket.
UNKNOWN_BUCKET = ">20%"


def p_evict_per_hour(bucket: str) -> float:
    return BUCKET_MONTHLY_RATE[bucket] / HOURS_PER_MONTH


@dataclass(frozen=True)
class EvictionRisk:
    cloud: str
    region: str
    instance_type: str
    bucket: str  # monthly interruption bucket, e.g. "5-10%"
    source: str  # where the bucket came from

    @property
    def p_evict_hour(self) -> float:
        return p_evict_per_hour(self.bucket)


def parse_aws_advisor(data: dict, catalog: Catalog) -> list[EvictionRisk]:
    """Look up each catalogue type/region in the Spot Advisor feed."""
    labels = {r["index"]: r["label"] for r in data["ranges"]}
    risks = []
    for region in catalog.aws.regions:
        linux = data["spot_advisor"].get(region, {}).get("Linux", {})
        for instance_type in catalog.aws.instance_types:
            entry = linux.get(instance_type)
            if entry is None:
                risks.append(EvictionRisk("aws", region, instance_type, UNKNOWN_BUCKET, "default"))
            else:
                bucket = labels[entry["r"]]
                risks.append(EvictionRisk("aws", region, instance_type, bucket, "aws-spot-advisor"))
    return risks


def azure_static(catalog: Catalog) -> list[EvictionRisk]:
    """Azure eviction buckets from the static table in catalog.yaml (assumed values)."""
    risks = []
    for region in catalog.azure.regions:
        for instance_type in catalog.azure.instance_types:
            bucket = catalog.azure.static_eviction_rates.get(instance_type)
            if bucket is None:
                risks.append(
                    EvictionRisk("azure", region, instance_type, UNKNOWN_BUCKET, "default")
                )
            else:
                risks.append(
                    EvictionRisk("azure", region, instance_type, bucket, "azure-static-assumed")
                )
    return risks


def collect(catalog: Catalog) -> list[EvictionRisk]:
    with httpx2.Client(timeout=60) as client:
        response = client.get(AWS_SPOT_ADVISOR_URL)
        response.raise_for_status()
    return parse_aws_advisor(response.json(), catalog) + azure_static(catalog)
