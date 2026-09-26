"""Price normalization and the instance catalogue."""

import pytest
from pydantic import ValidationError

from tide.catalog import Catalog
from tide.collectors.common import SPOT, PriceQuote, per_gb_hour, per_gpu_hour, per_vcpu_hour


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


def test_per_gpu_hour():
    # p4d.24xlarge: 8 A100s for $15.05/hr spot -> $1.88 per GPU-hour
    assert per_gpu_hour(15.0469, 8) == pytest.approx(1.8809, abs=1e-4)


def test_quote_from_spec_copies_gpu_details(catalog):
    spec = catalog.aws.instance_types["g4dn.xlarge"]
    quote = PriceQuote.from_spec(
        spec,
        cloud="aws",
        region="ap-south-1",
        zone="ap-south-1c",
        instance_type="g4dn.xlarge",
        pricing=SPOT,
        usd_per_hour=0.2075,
    )
    assert (quote.gpu_model, quote.gpu_count, quote.gpu_memory_gb) == ("T4", 1, 16)
    assert quote.usd_per_gpu_hour == pytest.approx(0.2075)
    assert quote.usd_per_vcpu_hour == pytest.approx(0.2075 / 4)


def test_cpu_quote_has_no_gpu_price():
    quote = PriceQuote("aws", "us-east-1", None, "m5.large", SPOT, 0.04, 2, 8)
    assert quote.gpu_model is None
    assert quote.usd_per_gpu_hour is None


def test_catalog_gpu_entries(catalog):
    t4 = catalog.azure.instance_types["Standard_NC4as_T4_v3"]
    assert t4.gpu.model == "T4" and t4.gpu.memory_gb == 16
    assert catalog.spec("aws", "m5.large").gpu is None
    # A100 types are for price comparison only (cost guardrail)
    assert catalog.spec("aws", "p4d.24xlarge").reference_only
    assert catalog.spec("azure", "Standard_NC24ads_A100_v4").reference_only
    assert not t4.reference_only


def test_catalog_has_two_gpu_regions_per_cloud(catalog):
    for cloud in (catalog.aws, catalog.azure):
        assert any(spec.gpu for spec in cloud.instance_types.values())
        assert len(cloud.regions) >= 2
