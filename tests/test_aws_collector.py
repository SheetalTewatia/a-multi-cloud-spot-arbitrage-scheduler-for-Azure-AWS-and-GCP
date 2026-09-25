"""AWS collector parsing, tested against recorded real API responses."""

import json
from datetime import datetime

import pytest
from conftest import load_fixture

from tide.collectors.aws import parse_on_demand_product, parse_spot_history
from tide.collectors.common import SPOT


def spot_history():
    """Recorded DescribeSpotPriceHistory rows; boto3 returns Timestamp as a datetime."""
    rows = load_fixture("aws_spot_history_ap_south_1.json")
    for row in rows:
        row["Timestamp"] = datetime.fromisoformat(row["Timestamp"])
    return rows


def test_parse_spot_history(catalog):
    quotes = parse_spot_history(spot_history(), "ap-south-1", catalog.aws)

    # 3 zones x 2 instance types in the recording
    assert len(quotes) == 6
    assert all(q.cloud == "aws" and q.pricing == SPOT and q.zone for q in quotes)

    m5_1a = next(q for q in quotes if q.zone == "ap-south-1a" and q.instance_type == "m5.large")
    assert m5_1a.usd_per_hour == pytest.approx(0.0306)
    assert m5_1a.vcpus == 2  # from catalog.yaml, not the API
    assert m5_1a.usd_per_vcpu_hour == pytest.approx(0.0153)


def test_parse_spot_history_keeps_newest_price_per_zone(catalog):
    rows = spot_history()
    newest = next(r for r in rows if r["AvailabilityZone"] == "ap-south-1a")
    older = dict(newest, SpotPrice="9.999", Timestamp=datetime.fromisoformat("2020-01-01T00:00Z"))

    quotes = parse_spot_history([older, *rows], "ap-south-1", catalog.aws)

    match = [
        q for q in quotes if q.zone == "ap-south-1a" and q.instance_type == newest["InstanceType"]
    ]
    assert len(match) == 1
    assert match[0].usd_per_hour == pytest.approx(float(newest["SpotPrice"]))


def test_parse_on_demand_product():
    product = json.dumps(load_fixture("aws_pricing_m5_large_ap_south_1.json"))
    assert parse_on_demand_product(product) == pytest.approx(0.101)


def test_parse_on_demand_product_without_hourly_price_fails():
    product = load_fixture("aws_pricing_m5_large_ap_south_1.json")
    for term in product["terms"]["OnDemand"].values():
        for dimension in term["priceDimensions"].values():
            dimension["unit"] = "Quantity"
    with pytest.raises(ValueError):
        parse_on_demand_product(json.dumps(product))
