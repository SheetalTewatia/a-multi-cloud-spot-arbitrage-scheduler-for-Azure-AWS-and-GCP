"""The scheduler loop (placement, eviction, migration, fallback), the fake executor,
price replay and run recording. Prices and evictions are scripted so results are exact."""

from datetime import UTC, datetime, timedelta

import pytest

from tide.collectors.common import ON_DEMAND, SPOT
from tide.models import Price
from tide.scheduler import report
from tide.scheduler.executor import FakeExecutor
from tide.scheduler.loop import run_workload
from tide.scheduler.record import save_run
from tide.scheduler.replay import ReplayFeed, build_snapshots, first_usable
from tide.scorer.model import Candidate
from tide.scorer.workload import Requirements, Workload


def job(runtime=2.0, deadline=4.0, overhead=0.5) -> Workload:
    return Workload(
        name="job",
        kind="cpu",
        runtime_hours=runtime,
        deadline_hours=deadline,
        restart_overhead_hours=overhead,
        requirements=Requirements(vcpus=2, memory_gb=8),
    )


def option(name, price, pricing=SPOT, p_evict=0.0, cloud="aws"):
    return Candidate(cloud, "us-east-1", None, name, pricing, price, 2, 8, p_evict)


class ScriptedExecutor:
    """Evicts on the given eviction checks (1 = the first check), otherwise never."""

    def __init__(self, evict_on_checks=()):
        self.evict_on = set(evict_on_checks)
        self.checks = 0
        self.launches: list[str] = []
        self.terminated: list[str] = []

    def launch(self, c):
        self.launches.append(c.instance_type)
        return f"i-{len(self.launches)}"

    def terminate(self, instance_id):
        self.terminated.append(instance_id)

    def eviction_notice(self, instance_id, hours):
        self.checks += 1
        return self.checks in self.evict_on


SPOT_A = option("a", 0.03)
ON_DEMAND_A = option("a", 0.10, ON_DEMAND)


def constant(*candidates):
    return lambda t: list(candidates)


# --- the loop -----------------------------------------------------------------------------


def test_uninterrupted_run_costs_price_times_runtime():
    result = run_workload(job(), constant(SPOT_A, ON_DEMAND_A), ScriptedExecutor())
    assert result.finished and result.met_deadline
    assert result.hours_elapsed == pytest.approx(2.0)
    assert result.tide_cost == pytest.approx(0.06)
    assert result.on_demand_same == pytest.approx(0.20)
    assert result.on_demand_cheapest == pytest.approx(0.20)
    assert result.savings == pytest.approx(0.7)
    assert [e.kind for e in result.events] == ["place", "finish"]


def test_eviction_adds_paid_restart_overhead_and_replaces():
    executor = ScriptedExecutor(evict_on_checks=[1])  # evicted after the first 10 minutes
    result = run_workload(job(overhead=0.5), constant(SPOT_A, ON_DEMAND_A), executor)

    assert result.evictions == 1
    assert [e.kind for e in result.events] == ["place", "evicted", "place", "finish"]
    assert result.events[2].reason == "replacement after eviction"
    # 2h of work + 0.5h overhead, all paid
    assert result.hours_elapsed == pytest.approx(2.5)
    assert result.instance_hours == pytest.approx(2.5)
    assert result.tide_cost == pytest.approx(0.03 * 2.5)
    assert result.on_demand_same == pytest.approx(0.10 * 2.5)


def test_migrates_when_a_much_cheaper_option_appears():
    cheap_b = option("b", 0.01, cloud="azure")

    def feed(t):  # b appears after one hour at a third of a's price
        return [SPOT_A, ON_DEMAND_A] + ([cheap_b] if t >= 1 else [])

    executor = ScriptedExecutor()
    result = run_workload(job(runtime=4, deadline=8, overhead=0.25), feed, executor)

    assert result.migrations == 1
    assert executor.launches == ["a", "b"]
    migrate = next(e for e in result.events if e.kind == "migrate")
    assert migrate.at_hours == pytest.approx(1.0)
    assert migrate.plan is not None  # the full scored plan is kept for the audit trail
    # 1h on a, then 0.25h restart overhead + 3h work on b
    assert result.tide_cost == pytest.approx(0.03 * 1 + 0.01 * 3.25)


def test_no_migration_below_threshold():
    slightly_cheaper = option("b", 0.027, cloud="azure")  # 10% cheaper: not worth moving

    def feed(t):
        return [SPOT_A, ON_DEMAND_A] + ([slightly_cheaper] if t >= 1 else [])

    result = run_workload(job(runtime=4, deadline=8), feed, ScriptedExecutor())
    assert result.migrations == 0


def test_price_changes_are_paid_while_running():
    def feed(t):
        return [option("a", 0.03 if t < 1 else 0.06), ON_DEMAND_A]

    result = run_workload(job(), feed, ScriptedExecutor())
    assert result.tide_cost == pytest.approx(0.03 * 1 + 0.06 * 1)


def test_finishes_late_on_on_demand_when_deadline_is_lost():
    # overhead of 3h after an eviction makes the 4h deadline impossible
    executor = ScriptedExecutor(evict_on_checks=[1])
    result = run_workload(job(overhead=3), constant(SPOT_A, ON_DEMAND_A), executor)
    replacement = result.events[2]
    assert replacement.option.pricing == ON_DEMAND
    assert "deadline can no longer be met" in replacement.reason
    assert result.finished and not result.met_deadline


def test_fails_cleanly_when_nothing_can_run_it():
    too_small = Candidate("aws", "us-east-1", None, "tiny", SPOT, 0.01, 1, 1, 0.0)
    result = run_workload(job(), constant(too_small), ScriptedExecutor())
    assert not result.finished
    assert result.events[-1].kind == "failed"
    assert result.tide_cost == 0


# --- fake executor ------------------------------------------------------------------------


def test_fake_executor_never_evicts_on_demand_or_zero_risk():
    executor = FakeExecutor(seed=1, eviction_multiplier=1000)
    on_demand = executor.launch(option("a", 0.1, ON_DEMAND))
    safe = executor.launch(option("b", 0.1, SPOT, p_evict=0.0))
    assert not any(executor.eviction_notice(on_demand, 1) for _ in range(100))
    assert not any(executor.eviction_notice(safe, 1) for _ in range(100))


def test_fake_executor_eviction_rate_follows_p_evict():
    executor = FakeExecutor(seed=7)
    instance = executor.launch(option("a", 0.1, SPOT, p_evict=0.2))
    hits = sum(executor.eviction_notice(instance, 1) for _ in range(5000))
    assert hits / 5000 == pytest.approx(0.2, abs=0.02)


def test_fake_executor_is_reproducible_with_a_seed():
    def draws(seed):
        executor = FakeExecutor(seed=seed)
        instance = executor.launch(option("a", 0.1, SPOT, p_evict=0.3))
        return [executor.eviction_notice(instance, 1) for _ in range(50)]

    assert draws(3) == draws(3)


# --- replay -------------------------------------------------------------------------------

T0 = datetime(2026, 1, 1, tzinfo=UTC)


def price_row(at, cloud, name, usd, pricing=SPOT):
    return Price(
        collected_at=at, cloud=cloud, region="r", zone=None, instance_type=name,
        pricing=pricing, usd_per_hour=usd, vcpus=2, memory_gb=8, usd_per_vcpu_hour=usd / 2,
        usd_per_gb_hour=usd / 8, gpu_model=None, gpu_count=None, gpu_memory_gb=None,
        usd_per_gpu_hour=None,
    )  # fmt: skip


def test_snapshots_carry_forward_missing_prices(catalog):
    later = T0 + timedelta(hours=1)
    prices = [
        price_row(T0, "aws", "m5.large", 0.04),
        price_row(T0, "azure", "Standard_D2s_v5", 0.02),
        price_row(later, "azure", "Standard_D2s_v5", 0.03),  # AWS failed at this collection
    ]
    snapshots = build_snapshots(prices, [], catalog)
    assert len(snapshots) == 2
    second = {c.instance_type: c.usd_per_hour for c in snapshots[1].candidates}
    assert second == {"m5.large": 0.04, "Standard_D2s_v5": 0.03}


def test_replay_feed_uses_latest_snapshot_at_or_before_time(catalog):
    prices = [
        price_row(T0, "aws", "m5.large", 0.04),
        price_row(T0 + timedelta(hours=1), "aws", "m5.large", 0.05),
    ]
    feed = ReplayFeed(build_snapshots(prices, [], catalog))
    assert feed(0.5)[0].usd_per_hour == 0.04
    assert feed(1.0)[0].usd_per_hour == 0.05
    assert feed(99)[0].usd_per_hour == 0.05  # held constant past the end of history
    assert feed.snapshots_used(0.5) == 1
    assert feed.snapshots_used(2) == 2


def test_replay_start_before_history_is_rejected(catalog):
    snapshots = build_snapshots([price_row(T0, "aws", "m5.large", 0.04)], [], catalog)
    with pytest.raises(ValueError):
        ReplayFeed(snapshots, T0 - timedelta(hours=1))


def test_first_usable_skips_snapshots_without_eligible_options(catalog):
    later = T0 + timedelta(hours=1)
    prices = [price_row(T0, "aws", "m5.large", 0.04), price_row(later, "aws", "g4dn.xlarge", 0.2)]
    snapshots = build_snapshots(prices, [], catalog)
    has_gpu = lambda cs: any(c.instance_type == "g4dn.xlarge" for c in cs)  # noqa: E731
    assert first_usable(snapshots, has_gpu) == later


# --- recording and reports ----------------------------------------------------------------


def test_saved_run_keeps_totals_and_audit_trail(db_session):
    result = run_workload(job(), constant(SPOT_A, ON_DEMAND_A), ScriptedExecutor([1]))
    run = save_run(db_session, "sim-test-1", "simulation", result, {"seed": 0}, T0)
    db_session.flush()

    assert run.evictions == 1 and run.status == "finished"
    assert [d.kind for d in run.decisions] == ["place", "evicted", "place", "finish"]
    first = run.decisions[0]
    assert first.at == T0
    assert {c["instance_type"] for c in first.candidates} == {"a"}  # every scored option
    assert report.savings(run) == pytest.approx(0.7)

    text = report.markdown([run], "Test report", ["SIMULATED"])
    assert "Saved vs on-demand | 70.0%" in text
    assert "replacement after eviction" in text
