"""Checkpoint — tracks baton progress through a route."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class CheckpointStatus(Enum):
    """Status of a checkpoint step."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    SKIPPED = "skipped"
    FAILED = "failed"


@dataclass
class StepCheckpoint:
    """Checkpoint for a single step in a route.

    Attributes:
        step_index: Position of the step in the route.
        agent: Agent responsible for this step.
        status: Current status.
        started_at: Timestamp when the step started (None if not started).
        completed_at: Timestamp when the step completed (None if not done).
        result: Optional result payload from the step.
        error: Optional error message if the step failed.
    """

    step_index: int
    agent: str
    status: CheckpointStatus = CheckpointStatus.PENDING
    started_at: float | None = None
    completed_at: float | None = None
    result: Any = None
    error: str | None = None

    def start(self) -> None:
        """Mark the step as in progress."""
        self.status = CheckpointStatus.IN_PROGRESS
        self.started_at = time.time()

    def complete(self, result: Any = None) -> None:
        """Mark the step as completed."""
        self.status = CheckpointStatus.COMPLETED
        self.completed_at = time.time()
        self.result = result

    def skip(self) -> None:
        """Mark the step as skipped."""
        self.status = CheckpointStatus.SKIPPED
        self.completed_at = time.time()

    def fail(self, error: str) -> None:
        """Mark the step as failed."""
        self.status = CheckpointStatus.FAILED
        self.completed_at = time.time()
        self.error = error

    def duration(self) -> float | None:
        """Seconds the step took (or has taken so far)."""
        if self.started_at is None:
            return None
        end = self.completed_at or time.time()
        return end - self.started_at


@dataclass
class Checkpoint:
    """Tracks a baton's progress through a route.

    A Checkpoint is created for a specific (baton, route) pair and maintains
    a list of :class:`StepCheckpoint` objects — one per step in the route.

    Example::

        from purplepincher_baton import BatonRoute, RouteStep, Checkpoint

        route = BatonRoute(name="pipeline", steps=[
            RouteStep(agent="loader"),
            RouteStep(agent="renderer"),
            RouteStep(agent="uploader"),
        ])

        ck = Checkpoint(route=route, baton_id="abc123")
        ck.start_step(0, agent="loader")
        ck.complete_step(0, result={"files": 42})
        ck.start_step(1, agent="renderer")
        assert ck.progress() == 1  # one step done
    """

    route: Any  # BatonRoute — avoid circular import
    baton_id: str
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    steps: list[StepCheckpoint] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)

    def __post_init__(self) -> None:
        if not self.steps:
            self.steps = [
                StepCheckpoint(step_index=i, agent=agent)
                for i, step in enumerate(self.route.steps)
                for agent in [step.agent]
            ]

    def start_step(self, step_index: int, agent: str | None = None) -> None:
        """Mark a step as in progress."""
        self._validate_index(step_index)
        self.steps[step_index].start()

    def complete_step(self, step_index: int, result: Any = None) -> None:
        """Mark a step as completed."""
        self._validate_index(step_index)
        self.steps[step_index].complete(result)

    def skip_step(self, step_index: int) -> None:
        """Mark a step as skipped."""
        self._validate_index(step_index)
        self.steps[step_index].skip()

    def fail_step(self, step_index: int, error: str) -> None:
        """Mark a step as failed."""
        self._validate_index(step_index)
        self.steps[step_index].fail(error)

    @property
    def current_step(self) -> StepCheckpoint | None:
        """Return the first non-terminal step, or None if all done."""
        for step in self.steps:
            if step.status in (CheckpointStatus.PENDING, CheckpointStatus.IN_PROGRESS):
                return step
        return None

    @property
    def current_index(self) -> int | None:
        """Index of the current step, or None."""
        step = self.current_step
        return step.step_index if step else None

    def progress(self) -> int:
        """Number of completed steps."""
        return sum(
            1 for s in self.steps if s.status in (CheckpointStatus.COMPLETED, CheckpointStatus.SKIPPED)
        )

    def progress_fraction(self) -> float:
        """Fraction of steps completed (0.0 to 1.0)."""
        if not self.steps:
            return 1.0
        return self.progress() / len(self.steps)

    def is_complete(self) -> bool:
        """True if all steps are in a terminal state."""
        return all(
            s.status in (CheckpointStatus.COMPLETED, CheckpointStatus.SKIPPED, CheckpointStatus.FAILED)
            for s in self.steps
        )

    def is_failed(self) -> bool:
        """True if any step has failed."""
        return any(s.status == CheckpointStatus.FAILED for s in self.steps)

    def summary(self) -> dict[str, Any]:
        """Return a summary dict of the checkpoint state."""
        return {
            "id": self.id,
            "baton_id": self.baton_id,
            "route": self.route.name,
            "progress": f"{self.progress()}/{len(self.steps)}",
            "fraction": round(self.progress_fraction(), 2),
            "is_complete": self.is_complete(),
            "is_failed": self.is_failed(),
            "steps": [
                {
                    "index": s.step_index,
                    "agent": s.agent,
                    "status": s.status.value,
                    "duration": round(s.duration(), 3) if s.duration() else None,
                    "error": s.error,
                }
                for s in self.steps
            ],
        }

    def _validate_index(self, index: int) -> None:
        if index < 0 or index >= len(self.steps):
            raise IndexError(f"Step index {index} out of range (0..{len(self.steps) - 1})")
