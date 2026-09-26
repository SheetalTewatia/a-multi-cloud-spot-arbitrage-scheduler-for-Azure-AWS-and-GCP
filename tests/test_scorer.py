"""The effective-cost model: formula, deadline feasibility, choice, fallback and
requirement matching for CPU and GPU workloads."""

from pathlib import Path

import pytest

from tide.collectors.common import ON_DEMAND, SPOT
from tide.scorer.model import Candidate, plan, rejection_reason, score
from tide.scorer.workload import Requirements, Workload, load_workload

WORKLOADS = Path(__file__).parent.parent / "workloads"


def cpu_job(**overrides) -> Workload:
    fields = dict(
        name="job",
        kind="cpu",
        runtime_hours=10,
        deadline_hours=12,
        restart_overhead_hours=0.5,
        requirements=Requirements(vcpus=2, memory_gb=8),
    )
    return Workload(**(fields | overrides))


def gpu_job(**requirements) -> Workload:
    return Workload(
        name="gpu",
        kind="gpu",
        runtime_hours=3,
        deadline_hours=8,
        restart_overhead_hours=0.25,
        requirements=Requirements(**requirements),
    )


def cpu(price, pricing=SPOT, p_evict=0.01, name="m5.large", cloud="aws", vcpus=2, memory=8):
    return Candidate(cloud, "us-east-1", None, name, pricing, price, vcpus, memory, p_evict)


def gpu(model, memory, price=0.5, count=1, name=None, reference_only=False):
    return Candidate(
        "aws", "us-east-1", None, name or f"{model}-box", SPOT, price, 4, 16, 0.01,
        gpu_model=model, gpu_count=count, gpu_memory_gb=memory, reference_only=reference_only,
    )  # fmt: skip


# --- the formula --------------------------------------------------------------------------


def test_effective_cost_formula():
    # p_evict 0.01/hr over 10h -> 0.1 expected restarts, each losing 0.5h
    option = score(cpu_job(), cpu(0.10, p_evict=0.01))
    assert option.expected_restarts == pytest.approx(0.1)
    # 0.10 * 10  +  0.1 * 0.5 * 0.10
    assert option.effective_cost == pytest.approx(1.0 + 0.005)
    assert option.expected_finish_hours == pytest.approx(10 + 0.05)
    assert option.feasible


def test_on_demand_has_no_restart_cost():
    option = score(cpu_job(), cpu(0.10, pricing=ON_DEMAND, p_evict=0.0))
    assert option.expected_restarts == 0
    assert option.effective_cost == pytest.approx(1.0)


def test_risk_can_outweigh_a_lower_price():
    # Cheaper but very likely to be evicted, with a long restart each time.
    risky = cpu(0.10, p_evict=0.5, name="risky")
    safe = cpu(0.11, p_evict=0.0, name="safe")
    job = cpu_job(restart_overhead_hours=2, deadline_hours=100)
    result = plan(job, [risky, safe])
    # risky: 1.0 + 5 restarts * 2h * 0.10 = 2.0   safe: 1.1
    assert result.choice.candidate.instance_type == "safe"


# --- deadline, choice and fallback --------------------------------------------------------


def test_misses_deadline_when_restart_overhead_pushes_past_it():
    job = cpu_job(runtime_hours=10, deadline_hours=10.01, restart_overhead_hours=1)
    option = score(job, cpu(0.10, p_evict=0.01))  # finishes at 10.1h
    assert not option.feasible


def test_choose_cheapest_feasible_spot():
    options = [cpu(0.05, name="a"), cpu(0.03, name="b"), cpu(0.20, ON_DEMAND, 0.0, name="c")]
    result = plan(cpu_job(), options)
    assert result.choice.candidate.instance_type == "b"
    assert [o.candidate.instance_type for o in result.options] == ["b", "a", "c"]


def test_falls_back_to_on_demand_when_no_spot_meets_deadline():
    job = cpu_job(runtime_hours=6, deadline_hours=6)  # zero slack: any eviction is too late
    result = plan(job, [cpu(0.03), cpu(0.10, ON_DEMAND, 0.0, name="od")])
    assert result.choice.candidate.pricing == ON_DEMAND
    assert result.choice.candidate.instance_type == "od"


def test_no_choice_when_nothing_can_meet_deadline():
    job = cpu_job(runtime_hours=10, deadline_hours=5)
    result = plan(job, [cpu(0.03), cpu(0.10, ON_DEMAND, 0.0)])
    assert result.choice is None
    assert result.savings_vs_on_demand is None


def test_savings_compare_with_on_demand_of_same_type_and_region():
    spot = cpu(0.03, p_evict=0.0)
    on_demand = cpu(0.10, ON_DEMAND, 0.0)
    other_type_on_demand = cpu(0.05, ON_DEMAND, 0.0, name="t3.large")
    result = plan(cpu_job(), [spot, on_demand, other_type_on_demand])
    assert result.on_demand_baseline == pytest.approx(1.0)
    assert result.savings_vs_on_demand == pytest.approx(0.7)


def test_every_candidate_is_kept_for_the_audit_trail():
    candidates = [cpu(0.03), gpu("T4", 16), cpu(0.05, vcpus=1, name="small")]
    result = plan(cpu_job(), candidates)
    assert len(result.options) == 3
    assert [o.rejected is None for o in result.options] == [True, False, False]


# --- CPU requirement matching -------------------------------------------------------------


def test_cpu_job_rejects_too_small_and_gpu_types():
    job = cpu_job()
    assert rejection_reason(job, cpu(0.01, vcpus=1)) == "needs 2 vCPUs"
    assert rejection_reason(job, cpu(0.01, memory=4)) == "needs 8 GB RAM"
    assert rejection_reason(job, gpu("T4", 16)) == "GPU type (CPU job)"
    assert rejection_reason(job, cpu(0.01, vcpus=4, memory=16)) is None


# --- GPU requirement matching -------------------------------------------------------------


def test_gpu_job_by_model():
    job = gpu_job(gpu_model="T4")
    assert rejection_reason(job, gpu("T4", 16)) is None
    assert rejection_reason(job, gpu("A10", 24)) == "needs T4 GPU"
    assert rejection_reason(job, cpu(0.01)) == "no GPU"


def test_gpu_job_by_minimum_memory():
    job = gpu_job(min_gpu_memory_gb=20)
    assert rejection_reason(job, gpu("T4", 16)) == "needs >= 20 GB GPU memory"
    assert rejection_reason(job, gpu("A10", 24)) is None
    assert rejection_reason(job, gpu("L4", 24)) is None


def test_gpu_job_by_model_and_memory_and_count():
    job = gpu_job(gpu_model="A10", min_gpu_memory_gb=24, gpu_count=2)
    assert rejection_reason(job, gpu("A10", 24, count=1)) == "needs 2 GPUs"
    assert rejection_reason(job, gpu("A10", 24, count=4)) is None


def test_any_gpu_when_no_model_or_memory_given():
    assert rejection_reason(gpu_job(), gpu("T4", 16)) is None


def test_reference_only_types_are_never_chosen():
    # The A100 is the cheapest per GPU-hour here, but it is reference-only.
    a100 = gpu("A100", 80, price=0.10, reference_only=True)
    t4 = gpu("T4", 16, price=0.20)
    result = plan(gpu_job(min_gpu_memory_gb=16), [a100, t4])
    assert result.choice.candidate.gpu_model == "T4"
    rejected = next(o for o in result.options if o.candidate.gpu_model == "A100")
    assert rejected.rejected == "reference only (never launched)"


def test_gpu_plan_picks_cheapest_matching_gpu():
    candidates = [gpu("T4", 16, price=0.21), gpu("A10", 24, price=0.41), gpu("T4", 16, 0.15)]
    result = plan(gpu_job(min_gpu_memory_gb=16), candidates)
    assert result.choice.candidate.usd_per_hour == pytest.approx(0.15)


# --- workload files -----------------------------------------------------------------------


@pytest.mark.parametrize("path", sorted(WORKLOADS.glob("*.yaml")), ids=lambda p: p.name)
def test_example_workloads_load(path):
    workload = load_workload(path)
    assert workload.deadline_hours >= workload.runtime_hours


def test_workload_rejects_unknown_kind():
    with pytest.raises(ValueError):
        Workload(name="x", kind="tpu", runtime_hours=1, deadline_hours=1, restart_overhead_hours=0)
