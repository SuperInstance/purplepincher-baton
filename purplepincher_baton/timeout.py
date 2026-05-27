"""TimeoutHandler — monitors batons and escalates on missed handoffs."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable


class TimeoutPolicy(Enum):
    """What to do when a baton times out."""

    MARK_TIMED_OUT = "mark_timed_out"
    RETRY = "retry"
    ESCALATE = "escalate"
    DROP = "drop"


@dataclass
class EscalationRecord:
    """Record of an escalation action taken for a timed-out baton."""

    baton_id: str
    policy: TimeoutPolicy
    timestamp: float
    attempt: int
    details: str = ""


@dataclass
class TimeoutHandler:
    """Monitors batons for timeout and applies escalation policies.

    The handler can be used standalone or with a :class:`RelayStation`.

    Example::

        from purplepincher_baton import TimeoutHandler, TimeoutPolicy, Baton

        handler = TimeoutHandler(default_timeout=30.0)

        baton = Baton(payload={"task": "render"}, sender="a", receiver="b",
                       timeout_seconds=5.0)

        # ... time passes ...

        expired = handler.check([baton])
        for b in expired:
            handler.escalate(b, policy=TimeoutPolicy.ESCALATE,
                            escalate_to="supervisor")
    """

    default_timeout: float = 60.0
    max_retries: int = 3
    retry_delay: float = 5.0
    escalation_log: list[EscalationRecord] = field(default_factory=list)
    _retry_counts: dict[str, int] = field(default_factory=dict)
    _on_timeout: list[Callable[[Any, TimeoutPolicy], None]] = field(default_factory=list)

    def on_timeout(self, callback: Callable[[Any, TimeoutPolicy], None]) -> None:
        """Register a callback invoked when a baton times out.

        The callback receives ``(baton, policy)``.
        """
        self._on_timeout.append(callback)

    def check(self, batons: list[Any]) -> list[Any]:
        """Check a list of batons for timeouts.

        Returns the list of batons that have timed out during this check.
        """
        expired: list[Any] = []
        for baton in batons:
            if baton.is_terminal():
                continue
            # Apply default timeout if baton has none set
            if baton.timeout_seconds is None:
                baton.timeout_seconds = self.default_timeout
            if baton.check_timeout():
                expired.append(baton)
        return expired

    def escalate(
        self,
        baton: Any,
        policy: TimeoutPolicy = TimeoutPolicy.MARK_TIMED_OUT,
        escalate_to: str | None = None,
        details: str = "",
    ) -> EscalationRecord:
        """Apply an escalation policy to a timed-out baton.

        Args:
            baton: The timed-out baton.
            policy: The policy to apply.
            escalate_to: For ESCALATE policy, the agent to hand off to.
            details: Optional details about the escalation.

        Returns:
            An EscalationRecord documenting the action.
        """
        baton_id = baton.id
        attempt = self._retry_counts.get(baton_id, 0) + 1
        self._retry_counts[baton_id] = attempt

        if policy == TimeoutPolicy.RETRY and attempt <= self.max_retries:
            # Reset baton for retry
            baton.state = type(baton).state.__class__(baton.state.value)  # keep current
            baton.state = baton.state.__class__("held")
            baton.updated_at = time.time()
            baton.timeout_seconds = (baton.timeout_seconds or self.default_timeout)
            details = details or f"Retry attempt {attempt}/{self.max_retries}"

        elif policy == TimeoutPolicy.ESCALATE and escalate_to:
            baton.pass_to(escalade_to if False else escalate_to)
            details = details or f"Escalated to {escalate_to}"

        elif policy == TimeoutPolicy.DROP:
            baton.drop(reason="timeout_handler: dropped after timeout")
            details = details or "Dropped by timeout handler"

        record = EscalationRecord(
            baton_id=baton_id,
            policy=policy,
            timestamp=time.time(),
            attempt=attempt,
            details=details,
        )
        self.escalation_log.append(record)

        for callback in self._on_timeout:
            callback(baton, policy)

        return record

    @property
    def retry_count(self) -> dict[str, int]:
        """Return a copy of per-baton retry counts."""
        return dict(self._retry_counts)

    def clear(self) -> None:
        """Reset handler state."""
        self.escalation_log.clear()
        self._retry_counts.clear()
