"""Baton — the fundamental unit of work passed between agents."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class BatonState(Enum):
    """Lifecycle states for a baton."""

    CREATED = "created"
    HELD = "held"
    PASSED = "passed"
    ACKNOWLEDGED = "acknowledged"
    COMPLETED = "completed"
    DROPPED = "dropped"
    TIMED_OUT = "timed_out"


@dataclass
class Baton:
    """A baton represents a unit of work passed from one agent to another.

    Attributes:
        id: Unique identifier for this baton.
        payload: Arbitrary data carried by the baton.
        sender: Identifier of the agent that created or last held the baton.
        receiver: Identifier of the agent currently holding or next to receive the baton.
        state: Current lifecycle state.
        created_at: Unix timestamp when the baton was created.
        updated_at: Unix timestamp of last state change.
        timeout_seconds: Optional timeout; if set, the baton expires after this many seconds.
        metadata: Additional key-value metadata attached to the baton.
        parent_id: If this baton was forked from another, the parent's id.
        history: Ordered list of (agent, timestamp, state) tuples tracking handoffs.
    """

    payload: Any
    sender: str
    receiver: str | None = None
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    state: BatonState = BatonState.CREATED
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    timeout_seconds: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    parent_id: str | None = None
    history: list[tuple[str, float, BatonState]] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.receiver is None:
            self.receiver = self.sender
        self._record(self.sender, self.state)

    def _record(self, agent: str, state: BatonState) -> None:
        now = time.time()
        self.updated_at = now
        self.history.append((agent, now, state))

    def pass_to(self, receiver: str, sender: str | None = None) -> None:
        """Pass the baton to a new receiver.

        Raises:
            ValueError: If the baton is not in a passable state.
        """
        if self.state in (BatonState.COMPLETED, BatonState.DROPPED, BatonState.TIMED_OUT):
            raise ValueError(f"Cannot pass baton in state {self.state.value}")
        sender = sender or self.receiver or self.sender
        self.sender = sender
        self.receiver = receiver
        self.state = BatonState.PASSED
        self._record(sender, BatonState.PASSED)

    def acknowledge(self, agent: str | None = None) -> None:
        """Acknowledge receipt of the baton.

        Raises:
            ValueError: If the baton has not been passed.
        """
        if self.state != BatonState.PASSED:
            raise ValueError(f"Can only acknowledge a passed baton, got {self.state.value}")
        agent = agent or self.receiver
        self.state = BatonState.ACKNOWLEDGED
        self._record(agent, BatonState.ACKNOWLEDGED)

    def hold(self, agent: str | None = None) -> None:
        """Mark the baton as held by an agent."""
        agent = agent or self.receiver
        self.state = BatonState.HELD
        self._record(agent, BatonState.HELD)

    def complete(self, agent: str | None = None) -> None:
        """Mark the baton as successfully completed."""
        agent = agent or self.receiver
        self.state = BatonState.COMPLETED
        self._record(agent, BatonState.COMPLETED)

    def drop(self, agent: str | None = None, reason: str | None = None) -> None:
        """Drop the baton, indicating failure or abandonment.

        Args:
            agent: The agent dropping the baton.
            reason: Optional reason stored in metadata.
        """
        agent = agent or self.receiver
        self.state = BatonState.DROPPED
        if reason:
            self.metadata["drop_reason"] = reason
        self._record(agent, BatonState.DROPPED)

    def check_timeout(self) -> bool:
        """Check whether the baton has exceeded its timeout.

        Returns:
            True if the baton has timed out (and updates state), False otherwise.
        """
        if self.timeout_seconds is None:
            return False
        if self.state in (BatonState.COMPLETED, BatonState.DROPPED, BatonState.TIMED_OUT):
            return False
        elapsed = time.time() - self.updated_at
        if elapsed > self.timeout_seconds:
            self.state = BatonState.TIMED_OUT
            self._record(self.receiver or self.sender, BatonState.TIMED_OUT)
            return True
        return False

    def is_terminal(self) -> bool:
        """Return True if the baton is in a terminal state."""
        return self.state in (BatonState.COMPLETED, BatonState.DROPPED, BatonState.TIMED_OUT)

    def age(self) -> float:
        """Seconds since the baton was created."""
        return time.time() - self.created_at

    def idle(self) -> float:
        """Seconds since the last state change."""
        return time.time() - self.updated_at

    def fork(self, new_receiver: str) -> Baton:
        """Create a child baton with the same payload, targeting a new receiver.

        The child references the parent via ``parent_id``.
        """
        child = Baton(
            payload=self.payload,
            sender=self.receiver or self.sender,
            receiver=new_receiver,
            timeout_seconds=self.timeout_seconds,
            metadata=dict(self.metadata),
            parent_id=self.id,
        )
        return child
