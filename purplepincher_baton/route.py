"""BatonRoute — defines sequential, parallel, and conditional paths for batons."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable


class StepType(Enum):
    """Type of route step."""

    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    CONDITIONAL = "conditional"


@dataclass
class RouteStep:
    """A single step in a route.

    Attributes:
        agent: The agent responsible for this step.
        step_type: Whether this step runs sequentially, in parallel, or conditionally.
        condition: For conditional steps, a callable that receives the baton payload
            and returns True if the step should execute.
        label: Optional human-readable label for this step.
        metadata: Arbitrary metadata for this step.
    """

    agent: str
    step_type: StepType = StepType.SEQUENTIAL
    condition: Callable[[Any], bool] | None = None
    label: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class BatonRoute:
    """Defines a path that a baton should follow through a series of agents.

    A route is an ordered list of :class:`RouteStep` objects.  Steps can be
    sequential (default), parallel (run together with adjacent parallel steps),
    or conditional (skipped if the condition evaluates to False).

    Example::

        route = BatonRoute(name="render-pipeline", steps=[
            RouteStep(agent="loader", label="Load assets"),
            RouteStep(agent="renderer", label="Render frame"),
            RouteStep(agent="reviewer", label="QA check",
                      step_type=StepType.CONDITIONAL,
                      condition=lambda p: p.get("quality") == "high"),
            RouteStep(agent="uploader", label="Upload result"),
        ])

        # Get ordered sequence of agents for a given payload
        agents = route.resolve(payload={"quality": "high"})
        # → ["loader", "renderer", "reviewer", "uploader"]
    """

    name: str
    steps: list[RouteStep] = field(default_factory=list)
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    metadata: dict[str, Any] = field(default_factory=dict)

    def add_step(
        self,
        agent: str,
        step_type: StepType = StepType.SEQUENTIAL,
        condition: Callable[[Any], bool] | None = None,
        label: str | None = None,
    ) -> "BatonRoute":
        """Append a step and return self for chaining."""
        self.steps.append(
            RouteStep(agent=agent, step_type=step_type, condition=condition, label=label)
        )
        return self

    def resolve(self, payload: Any = None) -> list[list[str]]:
        """Resolve the route into execution groups.

        Returns a list of groups.  Each group is a list of agent names that
        should run in parallel.  Sequential steps each get their own group.

        Conditional steps are included only when their condition evaluates to
        True against the provided payload.
        """
        groups: list[list[str]] = []
        current_parallel: list[str] = []

        for step in self.steps:
            # Evaluate condition
            if step.step_type == StepType.CONDITIONAL:
                if step.condition is not None and payload is not None:
                    if not step.condition(payload):
                        continue
                elif step.condition is not None and payload is None:
                    continue

            if step.step_type == StepType.PARALLEL:
                current_parallel.append(step.agent)
            else:
                if current_parallel:
                    groups.append(current_parallel)
                    current_parallel = []
                groups.append([step.agent])

        if current_parallel:
            groups.append(current_parallel)

        return groups

    def agents(self, payload: Any = None) -> list[str]:
        """Flat ordered list of agents for this route, given a payload."""
        return [agent for group in self.resolve(payload) for agent in group]

    def validate(self) -> list[str]:
        """Validate the route and return a list of issues (empty if valid)."""
        issues: list[str] = []
        seen: set[str] = set()
        for i, step in enumerate(self.steps):
            if step.step_type == StepType.CONDITIONAL and step.condition is None:
                issues.append(f"Step {i} ({step.agent}): conditional step has no condition")
            if not step.agent:
                issues.append(f"Step {i}: agent name is empty")
            if step.step_type == StepType.PARALLEL and step.condition is not None:
                issues.append(f"Step {i} ({step.agent}): parallel steps cannot have conditions")
            if step.agent in seen and step.step_type != StepType.PARALLEL:
                issues.append(
                    f"Step {i} ({step.agent}): duplicate agent in sequential/conditional step"
                )
            seen.add(step.agent)
        return issues

    def __len__(self) -> int:
        return len(self.steps)

    def __repr__(self) -> str:
        return f"BatonRoute(name={self.name!r}, steps={len(self.steps)})"
