"""Workload definitions, loaded from a workload YAML file (see workloads/)."""

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, NonNegativeFloat, PositiveFloat, PositiveInt


class Requirements(BaseModel):
    """Minimum hardware. Any instance type that meets all of these is a candidate."""

    vcpus: PositiveInt = 1
    memory_gb: NonNegativeFloat = 0
    # GPU jobs: ask for a GPU model, a minimum GPU memory, or both (neither = any GPU).
    gpu_model: str | None = None
    min_gpu_memory_gb: PositiveFloat | None = None
    gpu_count: PositiveInt = 1


class Workload(BaseModel):
    name: str
    kind: Literal["cpu", "gpu"]
    runtime_hours: PositiveFloat  # how long the job runs without interruptions
    deadline_hours: PositiveFloat  # must finish within this many hours of starting
    # Time lost per eviction: relaunch, restore the checkpoint, redo work since it.
    # For GPU jobs include model and checkpoint reload time (often several minutes).
    restart_overhead_hours: NonNegativeFloat
    requirements: Requirements = Requirements()


def load_workload(path: Path) -> Workload:
    with open(path) as f:
        return Workload.model_validate(yaml.safe_load(f))
