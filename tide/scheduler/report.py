"""Savings reports for one run, or a summary over several simulated trials."""

from statistics import mean

from tide.models import Run


def savings(run: Run) -> float | None:
    """Tide's actual cost vs. on-demand for the same instance-hours (the headline number)."""
    return 1 - run.tide_cost / run.on_demand_same if run.on_demand_same else None


def savings_vs_cheapest(run: Run) -> float | None:
    """Tide's actual cost vs. running the whole job once on the cheapest on-demand option.
    Stricter than `savings`: restart overhead from evictions counts against Tide here."""
    return 1 - run.tide_cost / run.on_demand_cheapest if run.on_demand_cheapest else None


def pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.1%}"


def worst_best(values: list[float]) -> str:
    return f"{pct(min(values))} / {pct(max(values))}" if values else "n/a"


def run_rows(run: Run) -> list[tuple[str, str]]:
    """The savings report for one run as (label, value) rows."""
    workload = run.workload
    rows = [
        ("Run", f"{run.id} ({run.mode})"),
        ("Workload", f"{run.workload_name} ({workload['kind']})"),
        ("Status", run.status),
        (
            "Finished in",
            f"{run.hours_elapsed:.2f}h of {workload['runtime_hours']:g}h work, "
            f"deadline {workload['deadline_hours']:g}h "
            f"({'met' if run.met_deadline else 'MISSED'})",
        ),
        ("Paid instance-hours", f"{run.instance_hours:.2f}h (includes restart overhead)"),
        ("Tide's actual cost", f"${run.tide_cost:.4f}"),
        ("On-demand, same instance-hours", f"${run.on_demand_same:.4f}"),
        ("Saved vs on-demand", pct(savings(run))),
    ]
    if run.on_demand_cheapest is not None:
        rows += [
            ("Cheapest on-demand for the job", f"${run.on_demand_cheapest:.4f}"),
            ("Saved vs cheapest on-demand", pct(savings_vs_cheapest(run))),
        ]
    rows += [("Migrations", str(run.migrations)), ("Evictions", str(run.evictions))]
    if run.gpu_hours:
        rows.append(("Cost per GPU-hour", f"${run.tide_cost / run.gpu_hours:.4f}"))
    return rows


def trial_summary_rows(runs: list[Run]) -> list[tuple[str, str]]:
    """Summary over several simulated trials of the same workload."""
    saved = [s for s in (savings(r) for r in runs) if s is not None]
    strict = [s for s in (savings_vs_cheapest(r) for r in runs) if s is not None]
    rows = [
        ("Trials", str(len(runs))),
        ("Mean saved vs on-demand", pct(mean(saved)) if saved else "n/a"),
        ("Worst / best trial", worst_best(saved)),
        ("Mean saved vs cheapest on-demand", pct(mean(strict)) if strict else "n/a"),
        ("Worst / best trial (cheapest)", worst_best(strict)),
        ("Mean Tide cost", f"${mean(r.tide_cost for r in runs):.4f}"),
        ("Mean on-demand, same instance-hours", f"${mean(r.on_demand_same for r in runs):.4f}"),
        ("Total evictions", str(sum(r.evictions for r in runs))),
        ("Total migrations", str(sum(r.migrations for r in runs))),
        ("Failed runs", f"{sum(r.status != 'finished' for r in runs)} of {len(runs)}"),
        ("Deadlines missed", f"{sum(not r.met_deadline for r in runs)} of {len(runs)}"),
    ]
    return rows


def markdown(runs: list[Run], title: str, notes: list[str]) -> str:
    """A markdown report: summary, per-run results and the first run's decisions."""
    lines = [f"# {title}", ""]
    lines += [f"> {note}" for note in notes] + [""]

    summary = trial_summary_rows(runs) if len(runs) > 1 else run_rows(runs[0])
    lines += ["| | |", "| --- | --- |"] + [f"| {k} | {v} |" for k, v in summary] + [""]

    if len(runs) > 1:
        lines += [
            "## Trials",
            "",
            "| Run | Cost | On-demand | Saved | Saved (cheapest) | Evictions | Migrations "
            "| Hours | Deadline |",
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
        for r in runs:
            lines.append(
                f"| {r.id} | ${r.tide_cost:.4f} | ${r.on_demand_same:.4f} | {pct(savings(r))} "
                f"| {pct(savings_vs_cheapest(r))} "
                f"| {r.evictions} | {r.migrations} | {r.hours_elapsed:.2f} "
                f"| {'met' if r.met_deadline else 'missed'} |"
            )
        lines.append("")

    # Show the decisions of a trial where something happened, if there is one.
    first = next((r for r in runs if r.evictions or r.migrations), runs[0])
    lines += [
        f"## Decisions in {first.id}",
        "",
        "| At (h) | Event | Where | USD/hr | Reason |",
        "| --- | --- | --- | --- | --- |",
    ]
    for d in first.decisions:
        where = " ".join(filter(None, [d.cloud, d.region, d.zone, d.instance_type, d.pricing]))
        price = f"{d.usd_per_hour:.4f}" if d.usd_per_hour is not None else ""
        lines.append(f"| {d.at_hours:.2f} | {d.kind} | {where} | {price} | {d.reason} |")
    lines.append("")
    return "\n".join(lines)
