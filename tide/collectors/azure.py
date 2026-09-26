"""Azure price collector, using the public Retail Prices API (no credentials needed).

The API returns every meter for a VM size: Linux and Windows, pay-as-you-go, Spot and
Low Priority, and sometimes Cloud Services. We keep only Linux VM meters. (Product names
vary: "Virtual Machines Dsv5 Series" but "NCads A100 v4 Series Linux", so we filter out
what we don't want instead of matching what we do.)
  - meterName ending in "Spot"  -> spot price
  - plain meterName             -> on-demand (pay-as-you-go) price

Note: unlike AWS, these Spot prices are list prices that Azure updates periodically,
not a live per-zone market price.
"""

import httpx2

from tide.catalog import CloudCatalog
from tide.collectors.common import ON_DEMAND, SPOT, PriceQuote

RETAIL_PRICES_URL = "https://prices.azure.com/api/retail/prices"
API_VERSION = "2023-01-01-preview"


def parse_items(items: list[dict], region: str, catalog: CloudCatalog) -> list[PriceQuote]:
    """Turn Retail Prices API items into spot and on-demand quotes for Linux VMs."""
    # (instance_type, pricing) -> newest matching item
    latest: dict[tuple[str, str], dict] = {}
    for item in items:
        instance_type = item["armSkuName"]
        product = item["productName"]
        meter = item["meterName"]

        if instance_type not in catalog.instance_types:
            continue
        if "Windows" in product or "Cloud Services" in product:
            continue
        if "Low Priority" in meter or item["unitOfMeasure"] != "1 Hour":
            continue

        pricing = SPOT if meter.endswith("Spot") else ON_DEMAND
        key = (instance_type, pricing)
        if key not in latest or item["effectiveStartDate"] > latest[key]["effectiveStartDate"]:
            latest[key] = item

    quotes = []
    for (instance_type, pricing), item in sorted(latest.items()):
        quotes.append(
            PriceQuote.from_spec(
                catalog.instance_types[instance_type],
                cloud="azure",
                region=region,
                zone=None,
                instance_type=instance_type,
                pricing=pricing,
                usd_per_hour=float(item["retailPrice"]),
            )
        )
    return quotes


def build_filter(region: str, instance_types: list[str]) -> str:
    skus = " or ".join(f"armSkuName eq '{sku}'" for sku in instance_types)
    return (
        "serviceName eq 'Virtual Machines' and priceType eq 'Consumption' "
        f"and armRegionName eq '{region}' and ({skus})"
    )


def fetch_items(client: httpx2.Client, region: str, instance_types: list[str]) -> list[dict]:
    """Fetch all matching items, following NextPageLink pagination."""
    items: list[dict] = []
    url: str | None = RETAIL_PRICES_URL
    params: dict | None = {
        "api-version": API_VERSION,
        "currencyCode": "USD",
        "$filter": build_filter(region, instance_types),
    }
    while url:
        response = client.get(url, params=params)
        response.raise_for_status()
        body = response.json()
        items += body["Items"]
        url = body.get("NextPageLink")
        params = None  # NextPageLink already contains the query string
    return items


def collect(catalog: CloudCatalog) -> list[PriceQuote]:
    """Collect spot and on-demand quotes for every region and instance type in the catalogue."""
    instance_types = list(catalog.instance_types)
    quotes: list[PriceQuote] = []
    with httpx2.Client(timeout=30) as client:
        for region in catalog.regions:
            quotes += parse_items(fetch_items(client, region, instance_types), region, catalog)
    return quotes
