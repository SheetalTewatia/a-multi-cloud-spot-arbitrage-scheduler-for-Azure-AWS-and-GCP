"""The shape every collector returns, plus price normalization."""

from dataclasses import dataclass

SPOT = "spot"
ON_DEMAND = "on_demand"


@dataclass(frozen=True)
class PriceQuote:
    """One hourly price for one instance type in one place.

    zone is the AWS availability zone for spot prices (AWS spot prices differ per AZ).
    It is None for AWS on-demand and for all Azure prices, which are per region.
    """

    cloud: str  # "aws" or "azure"
    region: str
    zone: str | None
    instance_type: str
    pricing: str  # SPOT or ON_DEMAND
    usd_per_hour: float
    vcpus: int
    memory_gb: float

    @property
    def usd_per_vcpu_hour(self) -> float:
        return per_vcpu_hour(self.usd_per_hour, self.vcpus)

    @property
    def usd_per_gb_hour(self) -> float:
        return per_gb_hour(self.usd_per_hour, self.memory_gb)


# The two normalizations are alternative views of the same instance price, not a split:
# a 2 vCPU / 8 GB VM at $0.10/hr is $0.05 per vCPU-hour OR $0.0125 per GB-hour.
def per_vcpu_hour(usd_per_hour: float, vcpus: int) -> float:
    return usd_per_hour / vcpus


def per_gb_hour(usd_per_hour: float, memory_gb: float) -> float:
    return usd_per_hour / memory_gb
