"""The `tide` command-line tool. More commands (simulate, destroy-all) arrive in later phases."""

import logging
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from tide import __version__, db
from tide.catalog import load_catalog
from tide.collectors.common import ON_DEMAND, SPOT
from tide.collectors.run import collect_and_store
from tide.collectors.store import latest_prices
from tide.scorer.candidates import load_candidates
from tide.scorer.model import plan as make_plan
from tide.scorer.workload import load_workload

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
    """Fetch current prices and eviction risks from AWS and Azure and store them."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logging.getLogger("httpx2").setLevel(logging.WARNING)  # one log line per request is noise
    catalog = load_catalog()
    while True:
        prices_saved, risks_saved, errors = collect_and_store(catalog)
        failed = f", failed: {', '.join(errors)}" if errors else ""
        typer.echo(f"saved {prices_saved} prices and {risks_saved} eviction risks{failed}")
        if not watch:
            if errors:
                raise typer.Exit(code=1)
            return
        time.sleep(interval_minutes * 60)


@app.command()
def prices(
    gpu: Annotated[bool, typer.Option(help="Show GPU types, priced per GPU-hour.")] = False,
    cloud: Annotated[str | None, typer.Option(help="aws or azure")] = None,
    region: Annotated[str | None, typer.Option()] = None,
    spot_only: Annotated[bool, typer.Option(help="Hide on-demand rows.")] = False,
    limit: Annotated[int, typer.Option(min=1)] = 50,
) -> None:
    """Show the latest stored prices: CPU types per vCPU-hour, or GPU types with --gpu."""
    with db.SessionLocal() as session:
        rows = latest_prices(session, cloud=cloud, region=region, gpu=gpu)
    if not rows:
        typer.echo("No prices stored yet. Run `tide collect` first.")
        raise typer.Exit(code=1)

    # On-demand price for each (cloud, region, type), to show how much cheaper spot is.
    on_demand = {
        (r.cloud, r.region, r.instance_type): r.usd_per_hour for r in rows if r.pricing == ON_DEMAND
    }
    if spot_only:
        rows = [r for r in rows if r.pricing == SPOT]
    catalog = load_catalog()

    table = Table(title=f"Latest {'GPU' if gpu else 'CPU'} prices (USD)")
    for column in ["Cloud", "Region", "Zone", "Type"] + (["GPU"] if gpu else []) + ["Pricing"]:
        table.add_column(column)
    per_unit = ["per GPU-hr"] if gpu else ["per vCPU-hr", "per GB-hr"]
    for column in ["per hour", *per_unit, "vs on-demand", "age"]:
        table.add_column(column, justify="right")

    now = datetime.now(UTC)
    for r in rows[:limit]:
        od = on_demand.get((r.cloud, r.region, r.instance_type))
        saving = f"{r.usd_per_hour / od - 1:+.0%}" if r.pricing == SPOT and od else ""
        age_minutes = int((now - r.collected_at).total_seconds() // 60)
        spec = catalog.spec(r.cloud, r.instance_type)
        name = r.instance_type + (" (ref)" if spec and spec.reference_only else "")
        if gpu:
            hardware = [f"{r.gpu_count}x {r.gpu_model} {r.gpu_memory_gb:g}GB"]
            unit_prices = [f"{r.usd_per_gpu_hour:.4f}"]
        else:
            hardware = []
            unit_prices = [f"{r.usd_per_vcpu_hour:.5f}", f"{r.usd_per_gb_hour:.5f}"]
        table.add_row(
            r.cloud,
            r.region,
            r.zone or "-",
            name,
            *hardware,
            r.pricing,
            f"{r.usd_per_hour:.4f}",
            *unit_prices,
            saving,
            f"{age_minutes}m",
        )
    console.print(table)
    if gpu:
        console.print("(ref) = reference only: priced for comparison, never launched.")


@app.command()
def plan(
    workload_file: Annotated[Path, typer.Argument(exists=True, dir_okay=False)],
    top: Annotated[int, typer.Option(min=1, help="How many eligible options to show.")] = 15,
    show_rejected: Annotated[
        bool, typer.Option("--show-rejected", help="Also list candidates that can't run it.")
    ] = False,
) -> None:
    """Rank every placement option for a workload and show the one Tide would choose."""
    workload = load_workload(workload_file)
    catalog = load_catalog()
    with db.SessionLocal() as session:
        candidates = load_candidates(session, catalog)
    if not candidates:
        typer.echo("No prices stored yet. Run `tide collect` first.")
        raise typer.Exit(code=1)

    result = make_plan(workload, candidates)
    gpu = workload.kind == "gpu"
    req = workload.requirements

    console.print(
        f"[bold]{workload.name}[/] ({workload.kind}): {workload.runtime_hours:g}h runtime, "
        f"deadline {workload.deadline_hours:g}h, "
        f"restart overhead {workload.restart_overhead_hours:g}h per eviction"
    )
    needs = []
    if gpu:
        needs.append(f"{req.gpu_count}x {req.gpu_model or 'any'} GPU")
        if req.min_gpu_memory_gb:
            needs.append(f">= {req.min_gpu_memory_gb:g} GB GPU memory")
    if req.vcpus > 1 or not gpu:
        needs.append(f">= {req.vcpus} vCPU")
    if req.memory_gb:
        needs.append(f">= {req.memory_gb:g} GB RAM")
    console.print(
        f"Needs {', '.join(needs)}. {len(candidates)} candidates: "
        f"{len(result.eligible)} eligible, {len(candidates) - len(result.eligible)} rejected."
    )

    table = Table(title="Ranked options (cheapest effective cost first)")
    table.add_column("#", justify="right")
    for column in ["Cloud", "Region", "Zone", "Type"] + (["GPU"] if gpu else []) + ["Pricing"]:
        table.add_column(column)
    for column in [
        "USD/hr",
        "USD/GPU-hr" if gpu else "USD/vCPU-hr",
        "evict/mo",
        "exp. restarts",
        "finish h",
        "eff. cost",
        "meets deadline",
    ]:
        table.add_column(column, justify="right")

    shown = result.eligible[:top]
    if result.choice and result.choice not in shown:
        shown.append(result.choice)  # e.g. an on-demand fallback ranked below the spot options
    if show_rejected:
        shown += [o for o in result.options if o.rejected]
    rank_of = {id(o): i for i, o in enumerate(result.eligible, start=1)}
    for option in shown:
        c = option.candidate
        chosen = option is result.choice
        if option.rejected:
            numbers = ["-"] * 5 + [option.rejected]
        else:
            numbers = [
                c.eviction_bucket or "-",
                f"{option.expected_restarts:.4f}",
                f"{option.expected_finish_hours:.3f}",
                f"{option.effective_cost:.4f}",
                "yes" if option.feasible else "NO",
            ]
        per_unit = c.usd_per_hour / c.gpu_count if gpu and c.gpu_count else c.usd_per_hour / c.vcpus
        table.add_row(
            "->" if chosen else str(rank_of.get(id(option), "")),
            c.cloud,
            c.region,
            c.zone or "-",
            c.instance_type,
            *([f"{c.gpu_count}x {c.gpu_model}" if c.gpu_model else "-"] if gpu else []),
            c.pricing,
            f"{c.usd_per_hour:.4f}",
            f"{per_unit:.4f}",
            *numbers,
            style="bold green" if chosen else ("dim" if option.rejected else None),
        )
    console.print(table)

    choice = result.choice
    if choice is None:
        console.print("[bold red]No option meets the requirements and deadline.[/]")
        raise typer.Exit(code=1)
    c = choice.candidate
    where = " ".join(filter(None, [c.cloud, c.region, c.zone, c.instance_type]))
    where += f" ({c.pricing})"
    console.print(f"[bold]Choice:[/] {where}, expected cost ${choice.effective_cost:.4f}")
    if c.pricing == ON_DEMAND:
        console.print("  No spot option can meet the deadline, so Tide falls back to on-demand.")
    elif result.savings_vs_on_demand is not None:
        console.print(
            f"  vs ${result.on_demand_baseline:.4f} on-demand for the same type and region: "
            f"{result.savings_vs_on_demand:.0%} cheaper"
        )


if __name__ == "__main__":
    app()
