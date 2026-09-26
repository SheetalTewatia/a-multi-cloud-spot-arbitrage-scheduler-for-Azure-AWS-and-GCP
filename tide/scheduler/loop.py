"""The placement and migration loop.

Every tick (10 minutes, the same as the price collector) the loop:
  1. places the workload if it isn't running (first start, or after an eviction),
  2. otherwise migrates if a feasible option is more than 20% cheaper for the remaining
     work (the threshold stops it flapping between near-equal prices),
  3. runs for one tick, paying the current price, and checks for an eviction notice.

Every eviction or migration costs `restart_overhead_hours` of paid time with no progress
(checkpoint, relaunch, restore). Each decision keeps the full scored plan, which is the
audit trail.

Time is in hours since the run started. `prices_at(t)` returns the candidates at time t:
replayed history in simulation, live prices in a real run.
"""

from collections.abc import Callable
from dataclasses import dataclass

from tide.collectors.common import ON_DEMAND
from tide.scheduler.executor import Executor
from tide.scorer.model import Candidate, Plan, plan, score
from tide.scorer.workload import Workload

TICK_HOURS = 10 / 60
MIGRATE_THRESHOLD = 0.20


def option_key(c: Candidate) -> tuple:
    return (c.cloud, c.region, c.zone, c.instance_type, c.pricing)


@dataclass
class Event:
    at_hours: float
    kind: str  # "place", "migrate", "evicted", "finish", "failed"
    option: Candidate | None
    reason: str
    plan: Plan | None = None  # every scored candidate at that moment (place / migrate)


@dataclass
class RunResult:
    workload: Workload
    events: list[Event]
    finished: bool
    hours_elapsed: float
    tide_cost: float  # what Tide paid: spot, or on-demand when it had to fall back
    on_demand_same: float  # the same instance types, regions and hours at on-demand prices
    on_demand_cheapest: float | None  # cheapest on-demand option for the whole job, no Tide
    migrations: int
    evictions: int
    instance_hours: float  # paid hours, including restart overhead
    gpu_hours: float

    @property
    def met_deadline(self) -> bool:
        return self.finished and self.hours_elapsed <= self.workload.deadline_hours + 1e-9

    @property
    def savings(self) -> float | None:
        """Saving vs. on-demand for the same instance-hours (the headline number)."""
        return 1 - self.tide_cost / self.on_demand_same if self.on_demand_same else None


def remaining_workload(
    workload: Workload, done_hours: float, now_hours: float, overhead_hours: float = 0.0
) -> Workload:
    """What's left of the job: less work to do, and less time until the deadline.
    Restart overhead still to be paid (after an eviction) also eats into that time."""
    return workload.model_copy(
        update={
            "runtime_hours": workload.runtime_hours - done_hours,
            "deadline_hours": workload.deadline_hours - now_hours - overhead_hours,
        }
    )


def run_workload(
    workload: Workload,
    prices_at: Callable[[float], list[Candidate]],
    executor: Executor,
    tick_hours: float = TICK_HOURS,
    migrate_threshold: float = MIGRATE_THRESHOLD,
) -> RunResult:
    t = done = overhead_left = 0.0
    tide_cost = on_demand_same = instance_hours = gpu_hours = 0.0
    migrations = evictions = 0
    events: list[Event] = []
    current: Candidate | None = None
    instance: str | None = None
    finished = False
    on_demand_price: dict[tuple, float] = {}  # last known on-demand $/hr per (cloud, region, type)

    # Baseline without Tide: the cheapest on-demand option that can run the whole job.
    start_candidates = prices_at(0)
    baseline = plan(workload, [c for c in start_candidates if c.pricing == ON_DEMAND]).choice
    on_demand_cheapest = baseline.effective_cost if baseline else None

    while True:
        if t > workload.deadline_hours * 3:
            events.append(Event(t, "failed", current, "gave up: ran past 3x the deadline"))
            break

        candidates = prices_at(t)
        for c in candidates:
            if c.pricing == ON_DEMAND:
                on_demand_price[(c.cloud, c.region, c.instance_type)] = c.usd_per_hour
        remaining = remaining_workload(workload, done, t, overhead_left)
        best = plan(remaining, candidates)

        if current is None:
            after_eviction = bool(events) and events[-1].kind == "evicted"
            reason = "replacement after eviction" if after_eviction else "initial placement"
            choice = best.choice
            if choice is None:
                # The deadline can't be met any more (e.g. after a late eviction): finish
                # late on the cheapest on-demand option rather than abandoning the job.
                choice = next((o for o in best.eligible if o.candidate.pricing == ON_DEMAND), None)
                reason += "; deadline can no longer be met, finishing on on-demand"
            if choice is None:
                events.append(Event(t, "failed", None, "no option can run the workload", best))
                break
            current = choice.candidate
            instance = executor.launch(current)
            events.append(Event(t, "place", current, reason, best))
        else:
            # Refresh the running option's price, then look for a clearly cheaper option.
            current = next((c for c in candidates if option_key(c) == option_key(current)), current)
            if best.choice and option_key(best.choice.candidate) != option_key(current):
                current_cost = score(remaining, current).effective_cost
                if best.choice.effective_cost < current_cost * (1 - migrate_threshold):
                    saving = 1 - best.choice.effective_cost / current_cost
                    reason = f"{saving:.0%} cheaper than {current.instance_type} for remaining work"
                    executor.terminate(instance)
                    current = best.choice.candidate
                    instance = executor.launch(current)
                    overhead_left += workload.restart_overhead_hours  # checkpoint + restart
                    migrations += 1
                    events.append(Event(t, "migrate", current, reason, best))

        # Run for one tick: restart overhead first (paid, no progress), then real work.
        overhead = min(overhead_left, tick_hours)
        overhead_left -= overhead
        work = min(tick_hours - overhead, workload.runtime_hours - done)
        used = overhead + work
        type_key = (current.cloud, current.region, current.instance_type)

        tide_cost += current.usd_per_hour * used
        # If the on-demand price is unknown, count the price we paid (understates savings).
        on_demand_same += on_demand_price.get(type_key, current.usd_per_hour) * used
        instance_hours += used
        gpu_hours += (current.gpu_count or 0) * used
        done += work
        t = round(t + used, 9)  # stop float drift (6 x 1/6h must be exactly 1h)

        if done >= workload.runtime_hours - 1e-9:
            executor.terminate(instance)
            events.append(Event(t, "finish", current, f"finished after {t:.2f}h"))
            finished = True
            break

        if executor.eviction_notice(instance, used):
            executor.terminate(instance)
            evictions += 1
            events.append(Event(t, "evicted", current, "eviction notice"))
            current, instance = None, None
            overhead_left = workload.restart_overhead_hours

    return RunResult(
        workload=workload,
        events=events,
        finished=finished,
        hours_elapsed=t,
        tide_cost=tide_cost,
        on_demand_same=on_demand_same,
        on_demand_cheapest=on_demand_cheapest,
        migrations=migrations,
        evictions=evictions,
        instance_hours=instance_hours,
        gpu_hours=gpu_hours,
    )
