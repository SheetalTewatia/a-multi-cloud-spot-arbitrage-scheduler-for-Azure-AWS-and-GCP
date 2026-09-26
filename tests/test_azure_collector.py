"""Azure collector parsing, tested against a recorded real Retail Prices API response."""

import httpx2
import pytest
from conftest import load_fixture

from tide.collectors.azure import build_filter, fetch_items, parse_items
from tide.collectors.common import ON_DEMAND, SPOT


def recorded_items():
    return load_fixture("azure_retail_prices_centralindia.json")["Items"]


def test_parse_items_keeps_only_linux_spot_and_on_demand(catalog):
    # The recording has 14 meters: Windows, Low Priority and Cloud Services must be dropped.
    quotes = parse_items(recorded_items(), "centralindia", catalog.azure)

    prices = {(q.instance_type, q.pricing): q.usd_per_hour for q in quotes}
    assert prices == {
        ("Standard_D2s_v5", SPOT): pytest.approx(0.018665),
        ("Standard_D2s_v5", ON_DEMAND): pytest.approx(0.101),
        ("Standard_D2as_v5", SPOT): pytest.approx(0.010275),
        ("Standard_D2as_v5", ON_DEMAND): pytest.approx(0.0556),
    }


def test_parse_items_normalizes_with_catalog_specs(catalog):
    quotes = parse_items(recorded_items(), "centralindia", catalog.azure)
    spot = next(q for q in quotes if q.instance_type == "Standard_D2s_v5" and q.pricing == SPOT)
    assert spot.cloud == "azure"
    assert spot.zone is None
    assert spot.usd_per_vcpu_hour == pytest.approx(0.018665 / 2)
    assert spot.usd_per_gb_hour == pytest.approx(0.018665 / 8)


def test_parse_items_uses_newest_effective_price(catalog):
    items = recorded_items()
    spot = next(
        i for i in items if i["meterName"] == "D2s v5 Spot" and "Windows" not in i["productName"]
    )
    old = dict(spot, retailPrice=5.0, effectiveStartDate="2019-01-01T00:00:00Z")

    quotes = parse_items([old, *items], "centralindia", catalog.azure)

    price = next(q for q in quotes if q.instance_type == "Standard_D2s_v5" and q.pricing == SPOT)
    assert price.usd_per_hour == pytest.approx(0.018665)


def test_parse_items_ignores_types_not_in_catalog(catalog):
    item = dict(recorded_items()[0], armSkuName="Standard_E64s_v5")
    assert parse_items([item], "centralindia", catalog.azure) == []


def test_build_filter():
    f = build_filter("eastus", ["Standard_D2s_v5", "Standard_D4s_v5"])
    assert "armRegionName eq 'eastus'" in f
    assert "(armSkuName eq 'Standard_D2s_v5' or armSkuName eq 'Standard_D4s_v5')" in f


def test_fetch_items_follows_next_page_link():
    pages = {
        "first": {"Items": [{"n": 1}], "NextPageLink": "https://prices.azure.com/page2"},
        "second": {"Items": [{"n": 2}], "NextPageLink": None},
    }

    def handler(request):
        page = "second" if request.url.path == "/page2" else "first"
        return httpx2.Response(200, json=pages[page])

    client = httpx2.Client(transport=httpx2.MockTransport(handler))
    assert fetch_items(client, "eastus", ["Standard_D2s_v5"]) == [{"n": 1}, {"n": 2}]


def test_parse_items_gpu_including_a100_product_naming(catalog):
    # A100 meters are named "NCads A100 v4 Series Linux", not "Virtual Machines ...".
    items = load_fixture("azure_retail_prices_gpu_eastus.json")["Items"]
    quotes = parse_items(items, "eastus", catalog.azure)

    prices = {(q.instance_type, q.pricing): q.usd_per_hour for q in quotes}
    assert prices == {
        ("Standard_NC4as_T4_v3", SPOT): pytest.approx(0.149174),
        ("Standard_NC4as_T4_v3", ON_DEMAND): pytest.approx(0.526),
        ("Standard_NC24ads_A100_v4", SPOT): pytest.approx(0.67877),
        ("Standard_NC24ads_A100_v4", ON_DEMAND): pytest.approx(3.673),
    }
    a100 = next(q for q in quotes if q.instance_type == "Standard_NC24ads_A100_v4")
    assert (a100.gpu_model, a100.gpu_count, a100.gpu_memory_gb) == ("A100", 1, 80)
