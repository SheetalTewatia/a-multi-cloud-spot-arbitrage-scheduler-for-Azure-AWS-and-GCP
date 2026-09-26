"""Eviction risk: bucket conversion, AWS Spot Advisor parsing, Azure static table,
and joining risks onto price candidates."""

from datetime import UTC, datetime

import pytest
from conftest import load_fixture
from pydantic import ValidationError

from tide.catalog import Catalog
from tide.collectors.common import ON_DEMAND, SPOT, PriceQuote
from tide.collectors.eviction import (
    UNKNOWN_BUCKET,
    EvictionRisk,
    azure_static,
    p_evict_per_hour,
    parse_aws_advisor,
)
from tide.collectors.store import save_quotes, save_risks
from tide.scorer.candidates import load_candidates


def test_bucket_to_hourly_probability():
    # 5-10% per month -> middle 7.5% -> spread over 730 hours
    assert p_evict_per_hour("5-10%") == pytest.approx(0.075 / 730)
    assert p_evict_per_hour(">20%") > p_evict_per_hour("<5%")


def test_parse_aws_advisor(catalog):
    risks = parse_aws_advisor(load_fixture("aws_spot_advisor_subset.json"), catalog)
    by_key = {(r.region, r.instance_type): r for r in risks}

    # every catalogue type in every AWS region gets a risk
    assert len(risks) == len(catalog.aws.regions) * len(catalog.aws.instance_types)
    # recorded: m5.large in ap-south-1 is in range index 4 (">20%")
    assert by_key[("ap-south-1", "m5.large")].bucket == ">20%"
    assert by_key[("ap-south-1", "m5.large")].source == "aws-spot-advisor"
    # recorded: t3.large in ap-south-1 is index 1 ("5-10%")
    assert by_key[("ap-south-1", "t3.large")].bucket == "5-10%"


def test_aws_advisor_missing_type_gets_worst_bucket(catalog):
    data = load_fixture("aws_spot_advisor_subset.json")
    del data["spot_advisor"]["us-east-1"]["Linux"]["g6.xlarge"]
    risks = parse_aws_advisor(data, catalog)
    missing = next(r for r in risks if (r.region, r.instance_type) == ("us-east-1", "g6.xlarge"))
    assert (missing.bucket, missing.source) == (UNKNOWN_BUCKET, "default")


def test_aws_gpu_types_are_riskier_in_recorded_data(catalog):
    risks = parse_aws_advisor(load_fixture("aws_spot_advisor_subset.json"), catalog)
    by_key = {(r.region, r.instance_type): r.p_evict_hour for r in risks}
    assert by_key[("ap-south-1", "g5.xlarge")] > by_key[("ap-south-1", "t3.large")]


def test_azure_static_table_marks_values_as_assumed(catalog):
    risks = azure_static(catalog)
    assert len(risks) == len(catalog.azure.regions) * len(catalog.azure.instance_types)
    assert {r.source for r in risks} == {"azure-static-assumed"}
    t4 = next(r for r in risks if r.instance_type == "Standard_NC4as_T4_v3")
    d2 = next(r for r in risks if r.instance_type == "Standard_D2s_v5")
    assert t4.p_evict_hour > d2.p_evict_hour  # GPU assumed riskier


def test_catalog_rejects_unknown_eviction_bucket():
    bad = {
        "aws": {"regions": [], "instance_types": {}},
        "azure": {"regions": [], "instance_types": {}, "static_eviction_rates": {"x": "7%"}},
    }
    with pytest.raises(ValidationError):
        Catalog.model_validate(bad)


def test_candidates_join_risk_and_treat_on_demand_as_safe(db_session, catalog):
    now = datetime(2026, 1, 1, tzinfo=UTC)
    spec = catalog.aws.instance_types["m5.large"]
    common = dict(cloud="aws", region="us-east-1", instance_type="m5.large")
    spot = PriceQuote.from_spec(spec, **common, zone="us-east-1a", pricing=SPOT, usd_per_hour=0.04)
    od = PriceQuote.from_spec(spec, **common, zone=None, pricing=ON_DEMAND, usd_per_hour=0.096)
    save_quotes(db_session, [spot, od], now)
    save_risks(db_session, [EvictionRisk(**common, bucket="10-15%", source="test")], now)

    by_pricing = {c.pricing: c for c in load_candidates(db_session, catalog)}
    assert by_pricing[SPOT].p_evict_hour == pytest.approx(p_evict_per_hour("10-15%"))
    assert by_pricing[SPOT].eviction_bucket == "10-15%"
    assert by_pricing[ON_DEMAND].p_evict_hour == 0


def test_candidates_without_risk_data_assume_worst(db_session, catalog):
    now = datetime(2026, 1, 1, tzinfo=UTC)
    spec = catalog.aws.instance_types["t3.large"]
    quote = PriceQuote.from_spec(
        spec, cloud="aws", region="us-east-1", zone="us-east-1a", instance_type="t3.large",
        pricing=SPOT, usd_per_hour=0.03,
    )  # fmt: skip
    save_quotes(db_session, [quote], now)
    [candidate] = load_candidates(db_session, catalog)
    assert candidate.p_evict_hour == pytest.approx(p_evict_per_hour(UNKNOWN_BUCKET))
