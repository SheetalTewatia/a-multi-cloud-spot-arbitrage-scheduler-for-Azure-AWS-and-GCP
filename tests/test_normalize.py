"""Price normalization and the instance catalogue."""

import pytest
from pydantic import ValidationError

from tide.catalog import Catalog
from tide.collectors.common import SPOT, PriceQuote, per_gb_hour, per_vcpu_hour


def test_per_vcpu_hour():
    # m5.large on-demand in ap-south-1: $0.101/hr for 2 vCPUs
    assert per_vcpu_hour(0.101, 2) == pytest.approx(0.0505)


def test_per_gb_hour():
    # same VM has 8 GB RAM
    assert per_gb_hour(0.101, 8) == pytest.approx(0.012625)


def test_quote_exposes_both_normalizations():
    quote = PriceQuote("azure", "eastus", None, "Standard_D4s_v5", SPOT, 0.04, 4, 16)
    assert quote.usd_per_vcpu_hour == pytest.approx(0.01)
    assert quote.usd_per_gb_hour == pytest.approx(0.0025)


def test_same_price_per_vcpu_for_bigger_vm_of_same_family():
    # D4s_v5 is exactly double D2s_v5, so the normalized price should match
    small = PriceQuote("azure", "eastus", None, "Standard_D2s_v5", SPOT, 0.0203, 2, 8)
    big = PriceQuote("azure", "eastus", None, "Standard_D4s_v5", SPOT, 0.0406, 4, 16)
    assert small.usd_per_vcpu_hour == pytest.approx(big.usd_per_vcpu_hour)


def test_catalog_loads(catalog):
    assert catalog.aws.instance_types["m5.large"].vcpus == 2
    assert catalog.azure.instance_types["Standard_D4s_v5"].memory_gb == 16
    assert "centralindia" in catalog.azure.regions


def test_catalog_rejects_zero_vcpus():
    # zero vCPUs would cause a divide-by-zero during normalization
    bad = {
        "aws": {"regions": ["us-east-1"], "instance_types": {"x": {"vcpus": 0, "memory_gb": 1}}},
        "azure": {"regions": [], "instance_types": {}},
    }
    with pytest.raises(ValidationError):
        Catalog.model_validate(bad)
