"""Save a run and its decisions (the audit trail) to Postgres."""

import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from tide.models import Decision, Run
from tide.scheduler.loop import RunResult
from tide.scorer.model import ScoredOption


def new_run_id(mode: str) -> str:
    """e.g. sim-20260926-141500-a3f95c01. Real runs use it as the tide-run-id cloud tag."""
    prefix = "sim" if mode == "simulation" else "run"
    return f"{prefix}-{datetime.now(UTC):%Y%m%d-%H%M%S}-{secrets.token_hex(4)}"


def option_to_dict(option: ScoredOption) -> dict:
    c = option.candidate
    return {
        "cloud": c.cloud,
        "region": c.region,
        "zone": c.zone,
        "instance_type": c.instance_type,
        "pricing": c.pricing,
        "usd_per_hour": c.usd_per_hour,
        "p_evict_hour": c.p_evict_hour,
        "eviction_bucket": c.eviction_bucket,
        "gpu_model": c.gpu_model,
        "rejected": option.rejected,
        "expected_restarts": option.expected_restarts,
        "expected_finish_hours": option.expected_finish_hours,
        "effective_cost": option.effective_cost,
        "feasible": option.feasible,
    }


def save_run(
    session: Session,
    run_id: str,
    mode: str,
    result: RunResult,
    params: dict,
    clock_start: datetime | None = None,
) -> Run:
    run = Run(
        id=run_id,
        created_at=datetime.now(UTC),
        mode=mode,
        workload_name=result.workload.name,
        workload=result.workload.model_dump(),
        params=params,
        status="finished" if result.finished else "failed",
        met_deadline=result.met_deadline,
        hours_elapsed=result.hours_elapsed,
        tide_cost=result.tide_cost,
        on_demand_same=result.on_demand_same,
        on_demand_cheapest=result.on_demand_cheapest,
        migrations=result.migrations,
        evictions=result.evictions,
        instance_hours=result.instance_hours,
        gpu_hours=result.gpu_hours,
    )
    for event in result.events:
        c = event.option
        run.decisions.append(
            Decision(
                at_hours=event.at_hours,
                at=clock_start + timedelta(hours=event.at_hours) if clock_start else None,
                kind=event.kind,
                reason=event.reason,
                cloud=c.cloud if c else None,
                region=c.region if c else None,
                zone=c.zone if c else None,
                instance_type=c.instance_type if c else None,
                pricing=c.pricing if c else None,
                usd_per_hour=c.usd_per_hour if c else None,
                candidates=[option_to_dict(o) for o in event.plan.options] if event.plan else None,
            )
        )
    session.add(run)
    return run
