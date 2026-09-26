"""Executors launch and terminate workloads. The scheduler loop only talks to this
interface, so the same loop drives the fake executor (simulation) and, from Phase 5,
the real AWS and Azure executors.
"""

import random
from typing import Protocol

from tide.collectors.common import SPOT
from tide.scorer.model import Candidate


class Executor(Protocol):
    def launch(self, option: Candidate) -> str:
        """Start the workload on this option and return an instance id."""

    def terminate(self, instance_id: str) -> None: ...

    def eviction_notice(self, instance_id: str, hours: float) -> bool:
        """Did an eviction notice arrive for this instance during the last `hours`?"""


class FakeExecutor:
    """Launches nothing and costs nothing. Evictions are drawn at random from each spot
    option's p_evict, so a simulated run sees roughly as many evictions as the model expects.

    eviction_multiplier scales p_evict for stress tests (e.g. 50 = fifty times riskier).
    """

    def __init__(self, seed: int = 0, eviction_multiplier: float = 1.0):
        self.rng = random.Random(seed)
        self.eviction_multiplier = eviction_multiplier
        self.running: dict[str, Candidate] = {}
        self.launched = 0

    def launch(self, option: Candidate) -> str:
        self.launched += 1
        instance_id = f"fake-{self.launched}"
        self.running[instance_id] = option
        return instance_id

    def terminate(self, instance_id: str) -> None:
        self.running.pop(instance_id, None)

    def eviction_notice(self, instance_id: str, hours: float) -> bool:
        option = self.running[instance_id]
        if option.pricing != SPOT:
            return False
        p_hour = min(option.p_evict_hour * self.eviction_multiplier, 1.0)
        # chance of at least one eviction in `hours`, treating each hour independently
        p_interval = 1 - (1 - p_hour) ** hours
        return self.rng.random() < p_interval
