"""Load and validate catalog.yaml (the instance types and regions Tide considers)."""

from pathlib import Path

import yaml
from pydantic import BaseModel, PositiveFloat, PositiveInt

from tide.config import settings


class GpuSpec(BaseModel):
    model: str  # T4, A10, L4, A100
    count: PositiveInt
    memory_gb: PositiveFloat  # per GPU


class InstanceSpec(BaseModel):
    vcpus: PositiveInt
    memory_gb: PositiveFloat
    gpu: GpuSpec | None = None
    # Priced for comparison only; the scheduler never places work on it (cost guardrail).
    reference_only: bool = False


class CloudCatalog(BaseModel):
    regions: list[str]
    instance_types: dict[str, InstanceSpec]


class Catalog(BaseModel):
    aws: CloudCatalog
    azure: CloudCatalog

    def spec(self, cloud: str, instance_type: str) -> InstanceSpec | None:
        return getattr(self, cloud).instance_types.get(instance_type)


def load_catalog(path: Path | None = None) -> Catalog:
    """Load the catalogue from `path`, or from CATALOG_PATH (default ./catalog.yaml)."""
    with open(path or settings.catalog_path) as f:
        return Catalog.model_validate(yaml.safe_load(f))
