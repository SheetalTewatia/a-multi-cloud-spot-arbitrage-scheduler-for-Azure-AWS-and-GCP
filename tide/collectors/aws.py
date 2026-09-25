"""AWS price collector.

Spot:      EC2 DescribeSpotPriceHistory (current price per availability zone).
On-demand: the AWS Price List API (pricing:GetProducts).

Both are read-only API calls with no charge. Credentials come from the normal boto3 chain
(AWS_PROFILE, env vars, or ~/.aws). See docs/permissions.md.
"""

import json
from datetime import UTC, datetime

import boto3

from tide.catalog import CloudCatalog
from tide.collectors.common import ON_DEMAND, SPOT, PriceQuote

LINUX = "Linux/UNIX"

# The Price List API is only served from a few regions; us-east-1 answers for every region.
PRICING_API_REGION = "us-east-1"


def parse_spot_history(history: list[dict], region: str, catalog: CloudCatalog) -> list[PriceQuote]:
    """Turn DescribeSpotPriceHistory rows into one quote per (zone, instance type).

    If a zone/type appears more than once, keep the most recent price.
    """
    latest: dict[tuple[str, str], dict] = {}
    for row in history:
        key = (row["AvailabilityZone"], row["InstanceType"])
        if key not in latest or row["Timestamp"] > latest[key]["Timestamp"]:
            latest[key] = row

    quotes = []
    for (zone, instance_type), row in sorted(latest.items()):
        spec = catalog.instance_types[instance_type]
        quotes.append(
            PriceQuote(
                cloud="aws",
                region=region,
                zone=zone,
                instance_type=instance_type,
                pricing=SPOT,
                usd_per_hour=float(row["SpotPrice"]),
                vcpus=spec.vcpus,
                memory_gb=spec.memory_gb,
            )
        )
    return quotes


def parse_on_demand_product(price_list_item: str) -> float:
    """Extract the hourly USD price from one Price List API product (a JSON string)."""
    product = json.loads(price_list_item)
    for term in product["terms"]["OnDemand"].values():
        for dimension in term["priceDimensions"].values():
            if dimension["unit"] == "Hrs":
                return float(dimension["pricePerUnit"]["USD"])
    raise ValueError("no hourly on-demand price in product")


def fetch_spot_history(ec2, instance_types: list[str]) -> list[dict]:
    """Current spot price for each (zone, instance type).

    StartTime=now asks for the price in effect right now, not the full history.
    """
    paginator = ec2.get_paginator("describe_spot_price_history")
    pages = paginator.paginate(
        InstanceTypes=instance_types,
        ProductDescriptions=[LINUX],
        StartTime=datetime.now(UTC),
    )
    return [row for page in pages for row in page["SpotPriceHistory"]]


def fetch_on_demand_product(pricing, region: str, instance_type: str) -> str:
    """Return the single Price List product for Linux, shared tenancy, no pre-installed software."""
    filters = {
        "instanceType": instance_type,
        "regionCode": region,
        "operatingSystem": "Linux",
        "tenancy": "Shared",
        "preInstalledSw": "NA",
        "capacitystatus": "Used",
        "licenseModel": "No License required",
    }
    response = pricing.get_products(
        ServiceCode="AmazonEC2",
        Filters=[{"Type": "TERM_MATCH", "Field": k, "Value": v} for k, v in filters.items()],
    )
    products = response["PriceList"]
    if len(products) != 1:
        raise ValueError(f"expected 1 product for {instance_type} in {region}, got {len(products)}")
    return products[0]


def collect(catalog: CloudCatalog) -> list[PriceQuote]:
    """Collect spot and on-demand quotes for every region and instance type in the catalogue."""
    instance_types = list(catalog.instance_types)
    pricing = boto3.client("pricing", region_name=PRICING_API_REGION)
    quotes: list[PriceQuote] = []

    for region in catalog.regions:
        ec2 = boto3.client("ec2", region_name=region)
        quotes += parse_spot_history(fetch_spot_history(ec2, instance_types), region, catalog)

        for instance_type, spec in catalog.instance_types.items():
            product = fetch_on_demand_product(pricing, region, instance_type)
            quotes.append(
                PriceQuote(
                    cloud="aws",
                    region=region,
                    zone=None,
                    instance_type=instance_type,
                    pricing=ON_DEMAND,
                    usd_per_hour=parse_on_demand_product(product),
                    vcpus=spec.vcpus,
                    memory_gb=spec.memory_gb,
                )
            )
    return quotes
