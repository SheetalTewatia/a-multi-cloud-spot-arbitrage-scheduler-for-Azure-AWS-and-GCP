"""The shape every collector returns, plus price normalization."""

from dataclasses import dataclass

from tide.catalog import InstanceSpec

SPOT = "spot"
ON_DEMAND = "on_demand"


@dataclass(frozen=True)
class PriceQuote:
    """One hourly price for one instance type in one place.

    zone is the AWS availability zone for spot prices (AWS spot prices differ per AZ).
    It is None for AWS on-demand and for all Azure prices, which are per region.
    GPU fields are None for CPU-only instance types.
    """

    cloud: str  # "aws" or "azure"
    region: str
    zone: str | None
    instance_type: str
    pricing: str  # SPOT or ON_DEMAND
    usd_per_hour: float
    vcpus: int
    memory_gb: float
    gpu_model: str | None = None
    gpu_count: int | None = None
    gpu_memory_gb: float | None = None

    @classmethod
    def from_spec(
        cls,
        spec: InstanceSpec,
        *,
        cloud: str,
        region: str,
        zone: str | None,
        instance_type: str,
        pricing: str,
        usd_per_hour: float,
    ) -> PriceQuote:
        """Build a quote, copying the hardware details from the catalogue entry."""
        return cls(
            cloud=cloud,
            region=region,
            zone=zone,
            instance_type=instance_type,
            pricing=pricing,
            usd_per_hour=usd_per_hour,
            vcpus=spec.vcpus,
            memory_gb=spec.memory_gb,
            gpu_model=spec.gpu.model if spec.gpu else None,
            gpu_count=spec.gpu.count if spec.gpu else None,
            gpu_memory_gb=spec.gpu.memory_gb if spec.gpu else None,
        )

    @property
    def usd_per_vcpu_hour(self) -> float:
        return per_vcpu_hour(self.usd_per_hour, self.vcpus)

    @property
    def usd_per_gb_hour(self) -> float:
        return per_gb_hour(self.usd_per_hour, self.memory_gb)

    @property
    def usd_per_gpu_hour(self) -> float | None:
        return per_gpu_hour(self.usd_per_hour, self.gpu_count) if self.gpu_count else None


# The normalizations are alternative views of the same instance price, not a split:
# a 2 vCPU / 8 GB VM at $0.10/hr is $0.05 per vCPU-hour OR $0.0125 per GB-hour.
def per_vcpu_hour(usd_per_hour: float, vcpus: int) -> float:
    return usd_per_hour / vcpus


def per_gb_hour(usd_per_hour: float, memory_gb: float) -> float:
    return usd_per_hour / memory_gb


def per_gpu_hour(usd_per_hour: float, gpu_count: int) -> float:
    """Whole instance price divided by its GPUs (the CPUs and RAM come bundled)."""
    return usd_per_hour / gpu_count
