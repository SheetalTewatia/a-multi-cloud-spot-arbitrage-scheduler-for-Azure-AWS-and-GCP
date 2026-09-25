"""The `tide` command-line tool. More commands (plan, destroy-all) arrive in later phases."""

import logging
import time
from datetime import UTC, datetime
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from tide import __version__, db
from tide.catalog import load_catalog
from tide.collectors.common import ON_DEMAND, SPOT
from tide.collectors.run import collect_and_store
from tide.collectors.store import latest_prices

app = typer.Typer(help="Tide: multi-cloud spot arbitrage scheduler.", no_args_is_help=True)
console = Console()


@app.command()
def version() -> None:
    """Print the Tide version."""
    typer.echo(__version__)


@app.command("db-check")
def db_check() -> None:
    """Check that Tide can reach Postgres."""
    if db.check_connection():
        typer.echo("database: ok")
    else:
        typer.echo("database: unreachable (is `docker compose up -d db` running?)", err=True)
        raise typer.Exit(code=1)


@app.command()
def collect(
    watch: Annotated[bool, typer.Option(help="Keep collecting on an interval.")] = False,
    interval_minutes: Annotated[int, typer.Option(min=1)] = 10,
) -> None:
    """Fetch current spot and on-demand prices from AWS and Azure and store them."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logging.getLogger("httpx2").setLevel(logging.WARNING)  # one log line per request is noise
    catalog = load_catalog()
    while True:
        saved, errors = collect_and_store(catalog)
        typer.echo(f"saved {saved} prices" + (f", failed: {', '.join(errors)}" if errors else ""))
        if not watch:
            if errors:
                raise typer.Exit(code=1)
            return
        time.sleep(interval_minutes * 60)


@app.command()
def prices(
    cloud: Annotated[str | None, typer.Option(help="aws or azure")] = None,
    region: Annotated[str | None, typer.Option()] = None,
    spot_only: Annotated[bool, typer.Option(help="Hide on-demand rows.")] = False,
    limit: Annotated[int, typer.Option(min=1)] = 50,
) -> None:
    """Show the latest stored prices, cheapest per vCPU-hour first."""
    with db.SessionLocal() as session:
        rows = latest_prices(session, cloud=cloud, region=region)
    if not rows:
        typer.echo("No prices stored yet. Run `tide collect` first.")
        raise typer.Exit(code=1)

    # On-demand price for each (cloud, region, type), to show how much cheaper spot is.
    on_demand = {
        (r.cloud, r.region, r.instance_type): r.usd_per_hour for r in rows if r.pricing == ON_DEMAND
    }
    if spot_only:
        rows = [r for r in rows if r.pricing == SPOT]

    table = Table(title="Latest prices (USD)")
    for column in ["Cloud", "Region", "Zone", "Type", "Pricing"]:
        table.add_column(column)
    for column in ["per hour", "per vCPU-hr", "per GB-hr", "vs on-demand", "age"]:
        table.add_column(column, justify="right")

    now = datetime.now(UTC)
    for r in rows[:limit]:
        od = on_demand.get((r.cloud, r.region, r.instance_type))
        saving = f"-{1 - r.usd_per_hour / od:.0%}" if r.pricing == SPOT and od else ""
        age_minutes = int((now - r.collected_at).total_seconds() // 60)
        table.add_row(
            r.cloud,
            r.region,
            r.zone or "-",
            r.instance_type,
            r.pricing,
            f"{r.usd_per_hour:.4f}",
            f"{r.usd_per_vcpu_hour:.5f}",
            f"{r.usd_per_gb_hour:.5f}",
            saving,
            f"{age_minutes}m",
        )
    console.print(table)


if __name__ == "__main__":
    app()
