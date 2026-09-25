"""Load and validate catalog.yaml (the instance types and regions Tide considers)."""

from pathlib import Path

import yaml
from pydantic import BaseModel, PositiveFloat, PositiveInt

from tide.config import settings


class InstanceSpec(BaseModel):
    vcpus: PositiveInt
    memory_gb: PositiveFloat


class CloudCatalog(BaseModel):
    regions: list[str]
    instance_types: dict[str, InstanceSpec]


class Catalog(BaseModel):
    aws: CloudCatalog
    azure: CloudCatalog


def load_catalog(path: Path | None = None) -> Catalog:
    """Load the catalogue from `path`, or from CATALOG_PATH (default ./catalog.yaml)."""
    with open(path or settings.catalog_path) as f:
        return Catalog.model_validate(yaml.safe_load(f))
