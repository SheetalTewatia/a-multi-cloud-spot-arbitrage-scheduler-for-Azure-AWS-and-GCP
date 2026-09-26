"""The effective-cost model. Pure functions: no database, no network.

    expected_restarts = p_evict * runtime_hours
    effective_cost    = spot_price * runtime_hours
                      + expected_restarts * restart_overhead_hours * spot_price
    feasible          = expected finish time (including restart overhead) <= deadline
    choose            = feasible spot option with the lowest effective_cost
    fallback          = cheapest feasible on-demand option if no spot option is feasible

Prices are for the whole instance, because that's what you pay for. Among instances that
meet the requirements this ranks by price per vCPU-hour (CPU) or per GPU-hour (GPU).
On-demand options have p_evict = 0.
"""

from dataclasses import dataclass

from tide.collectors.common import ON_DEMAND, SPOT
from tide.scorer.workload import Workload


@dataclass(frozen=True)
class Candidate:
    """One place a workload could run, with its current price and eviction risk."""

    cloud: str
    region: str
    zone: str | None
    instance_type: str
    pricing: str  # SPOT or ON_DEMAND
    usd_per_hour: float
    vcpus: int
    memory_gb: float
    p_evict_hour: float  # 0 for on-demand
    gpu_model: str | None = None
    gpu_count: int | None = None
    gpu_memory_gb: float | None = None
    reference_only: bool = False
    eviction_bucket: str | None = None  # e.g. "5-10%", for display


@dataclass(frozen=True)
class ScoredOption:
    candidate: Candidate
    rejected: str | None  # why it can't run this workload at all; None = it can
    expected_restarts: float = 0.0
    expected_finish_hours: float = 0.0
    effective_cost: float = 0.0
    feasible: bool = False  # finishes before the deadline


@dataclass(frozen=True)
class Plan:
    workload: Workload
    options: list[ScoredOption]  # every candidate, the audit trail
    choice: ScoredOption | None
    on_demand_baseline: float | None  # cost of the chosen type on on-demand, same region

    @property
    def eligible(self) -> list[ScoredOption]:
        return [o for o in self.options if o.rejected is None]

    @property
    def savings_vs_on_demand(self) -> float | None:
        if self.choice is None or not self.on_demand_baseline:
            return None
        return 1 - self.choice.effective_cost / self.on_demand_baseline


def rejection_reason(workload: Workload, c: Candidate) -> str | None:
    """Why this candidate can't run the workload, or None if it can."""
    req = workload.requirements
    if c.reference_only:
        return "reference only (never launched)"
    if workload.kind == "cpu" and c.gpu_model is not None:
        return "GPU type (CPU job)"
    if workload.kind == "gpu":
        if c.gpu_model is None:
            return "no GPU"
        if req.gpu_model and c.gpu_model != req.gpu_model:
            return f"needs {req.gpu_model} GPU"
        if req.min_gpu_memory_gb and c.gpu_memory_gb < req.min_gpu_memory_gb:
            return f"needs >= {req.min_gpu_memory_gb:g} GB GPU memory"
        if c.gpu_count < req.gpu_count:
            return f"needs {req.gpu_count} GPUs"
    if c.vcpus < req.vcpus:
        return f"needs {req.vcpus} vCPUs"
    if c.memory_gb < req.memory_gb:
        return f"needs {req.memory_gb:g} GB RAM"
    return None


def score(workload: Workload, c: Candidate) -> ScoredOption:
    """Apply the effective-cost formula to one candidate."""
    reason = rejection_reason(workload, c)
    if reason:
        return ScoredOption(candidate=c, rejected=reason)

    expected_restarts = c.p_evict_hour * workload.runtime_hours
    lost_hours = expected_restarts * workload.restart_overhead_hours
    effective_cost = c.usd_per_hour * workload.runtime_hours + lost_hours * c.usd_per_hour
    expected_finish = workload.runtime_hours + lost_hours
    return ScoredOption(
        candidate=c,
        rejected=None,
        expected_restarts=expected_restarts,
        expected_finish_hours=expected_finish,
        effective_cost=effective_cost,
        feasible=expected_finish <= workload.deadline_hours,
    )


def plan(workload: Workload, candidates: list[Candidate]) -> Plan:
    """Score every candidate and pick one: cheapest feasible spot, else on-demand."""
    scored = [score(workload, c) for c in candidates]
    # Eligible options first, cheapest first; rejected ones after, for the audit trail.
    scored.sort(key=lambda o: (o.rejected is not None, o.effective_cost))

    def cheapest_feasible(pricing: str) -> ScoredOption | None:
        options = [o for o in scored if o.rejected is None and o.feasible]
        return next((o for o in options if o.candidate.pricing == pricing), None)

    choice = cheapest_feasible(SPOT) or cheapest_feasible(ON_DEMAND)

    baseline = None
    if choice:
        chosen = choice.candidate
        baseline = next(
            (
                o.candidate.usd_per_hour * workload.runtime_hours
                for o in scored
                if o.candidate.pricing == ON_DEMAND
                and (o.candidate.cloud, o.candidate.region, o.candidate.instance_type)
                == (chosen.cloud, chosen.region, chosen.instance_type)
            ),
            None,
        )
    return Plan(workload=workload, options=scored, choice=choice, on_demand_baseline=baseline)
