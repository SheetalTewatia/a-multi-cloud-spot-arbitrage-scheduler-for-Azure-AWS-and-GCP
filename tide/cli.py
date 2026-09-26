"""The `tide` command-line tool. More commands (destroy-all) arrive in later phases."""

import logging
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table
from sqlalchemy import select

from tide import __version__, db
from tide.catalog import load_catalog
from tide.collectors.common import ON_DEMAND, SPOT
from tide.collectors.run import collect_and_store
from tide.collectors.store import latest_prices
from tide.models import Run
from tide.scheduler import report as reports
from tide.scheduler.executor import FakeExecutor
from tide.scheduler.loop import MIGRATE_THRESHOLD, run_workload
from tide.scheduler.record import new_run_id, save_run
from tide.scheduler.replay import ReplayFeed, first_usable, load_snapshots
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


def print_rows(title: str, rows: list[tuple[str, str]]) -> None:
    table = Table(title=title, show_header=False)
    table.add_column(style="bold")
    table.add_column()
    for label, value in rows:
        table.add_row(label, value)
    console.print(table)


def print_decisions(run: Run) -> None:
    table = Table(title=f"Decisions in {run.id}")
    for column in ["At (h)", "Event", "Where", "USD/hr", "Reason"]:
        table.add_column(column)
    for d in run.decisions:
        where = " ".join(filter(None, [d.cloud, d.region, d.zone, d.instance_type, d.pricing]))
        price = f"{d.usd_per_hour:.4f}" if d.usd_per_hour is not None else ""
        table.add_row(f"{d.at_hours:.2f}", d.kind, where, price, d.reason)
    console.print(table)


@app.command()
def simulate(
    workload_file: Annotated[Path, typer.Argument(exists=True, dir_okay=False)],
    trials: Annotated[int, typer.Option(min=1, help="Independent runs with seeds seed..")] = 1,
    seed: Annotated[int, typer.Option(help="Random seed for simulated evictions.")] = 0,
    eviction_multiplier: Annotated[
        float, typer.Option(min=0, help="Scale every p_evict, for stress tests.")
    ] = 1.0,
    migrate_threshold: Annotated[float, typer.Option(min=0, max=1)] = MIGRATE_THRESHOLD,
    start: Annotated[
        datetime | None, typer.Option(help="Replay from this time (default: oldest usable prices).")
    ] = None,
    markdown: Annotated[Path | None, typer.Option(help="Also write the report here.")] = None,
) -> None:
    """Run the scheduler on replayed price history with a fake executor. Costs nothing."""
    workload = load_workload(workload_file)
    catalog = load_catalog()
    with db.SessionLocal() as session:
        snapshots = load_snapshots(session, catalog)
    try:
        if start is None:  # oldest history the workload can actually run on
            start = first_usable(snapshots, lambda cs: bool(make_plan(workload, cs).eligible))
        feed = ReplayFeed(snapshots, start.astimezone(UTC))
    except ValueError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    params = {
        "seed": seed,
        "eviction_multiplier": eviction_multiplier,
        "migrate_threshold": migrate_threshold,
        "replay_start": feed.start.isoformat(),
        "workload_file": workload_file.as_posix(),
    }
    with db.SessionLocal() as session:
        runs = []
        for trial in range(trials):
            executor = FakeExecutor(seed=seed + trial, eviction_multiplier=eviction_multiplier)
            result = run_workload(workload, feed, executor, migrate_threshold=migrate_threshold)
            run_params = params | {"seed": seed + trial}
            run = save_run(
                session, new_run_id("simulation"), "simulation", result, run_params, feed.start
            )
            runs.append(run)
        session.commit()

        longest = max(r.hours_elapsed for r in runs)
        used = feed.snapshots_used(longest)
        notes = [
            "SIMULATED: stored prices replayed with a fake executor and random evictions. "
            "No cloud resources were used.",
            f"Replayed {used} price snapshot(s) from {feed.start:%Y-%m-%d %H:%M} UTC. "
            f"Stored history ends {feed.times[-1]:%Y-%m-%d %H:%M} UTC; after that, prices "
            "are held constant.",
            f"Eviction multiplier {eviction_multiplier:g}, migration threshold "
            f"{migrate_threshold:.0%}, seeds {seed}..{seed + trials - 1}.",
        ]
        for note in notes:
            console.print(f"[dim]{note}[/]")
        if trials == 1:
            print_rows("Savings report", reports.run_rows(runs[0]))
            print_decisions(runs[0])
        else:
            print_rows(f"Summary of {trials} trials", reports.trial_summary_rows(runs))
        if markdown:
            title = f"Simulated savings report: {workload.name}"
            markdown.parent.mkdir(parents=True, exist_ok=True)
            markdown.write_text(reports.markdown(runs, title, notes), encoding="utf-8")
            console.print(f"Wrote {markdown}")


@app.command()
def report(
    run_id: str,
    markdown: Annotated[Path | None, typer.Option(help="Also write the report here.")] = None,
) -> None:
    """Show the savings report and decisions for one run."""
    with db.SessionLocal() as session:
        run = session.get(Run, run_id)
        if run is None:
            typer.echo(f"No run {run_id}. See `tide runs`.", err=True)
            raise typer.Exit(code=1)
        print_rows("Savings report", reports.run_rows(run))
        print_decisions(run)
        if markdown:
            text = reports.markdown([run], f"Savings report: {run.workload_name}", [])
            markdown.write_text(text, encoding="utf-8")


@app.command()
def runs(limit: Annotated[int, typer.Option(min=1)] = 20) -> None:
    """List recent runs, newest first."""
    with db.SessionLocal() as session:
        rows = session.scalars(select(Run).order_by(Run.created_at.desc()).limit(limit)).all()
        table = Table(title="Runs")
        for column in ["Run", "Mode", "Workload", "Status", "Cost", "Saved", "Evict", "Migr"]:
            table.add_column(column)
        for r in rows:
            table.add_row(
                r.id,
                r.mode,
                r.workload_name,
                r.status,
                f"${r.tide_cost:.4f}",
                reports.pct(reports.savings(r)),
                str(r.evictions),
                str(r.migrations),
            )
        console.print(table)


if __name__ == "__main__":
    app()
