"""RelayStation — manages baton handoffs between named agents."""

from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from .baton import Baton, BatonState


@dataclass
class RelayEvent:
    """Record of a single relay action."""

    baton_id: str
    action: str  # "pass", "ack", "drop", "complete", "timeout", "register", "fork"
    agent: str
    timestamp: float
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentInfo:
    """Tracked information about a registered agent."""

    name: str
    registered_at: float = field(default_factory=time.time)
    batons_held: int = 0
    batons_completed: int = 0
    batons_dropped: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


class RelayStation:
    """Central hub that tracks batons and agents, coordinating handoffs.

    The RelayStation is not a message broker — it's a **ledger**.  Agents
    call methods to record handoffs; the station enforces invariants,
    maintains history, and provides queries.

    Example::

        station = RelayStation()
        station.register_agent("worker-1")
        station.register_agent("worker-2")

        baton = station.create_baton(
            payload={"task": "render frame 42"},
            sender="coordinator",
            receiver="worker-1",
        )

        station.pass_baton(baton.id, from_agent="worker-1", to_agent="worker-2")
        station.acknowledge_baton(baton.id, agent="worker-2")
        station.complete_baton(baton.id, agent="worker-2")
    """

    def __init__(self) -> None:
        self._batons: dict[str, Baton] = {}
        self._agents: dict[str, AgentInfo] = {}
        self._log: list[RelayEvent] = []
        self._agent_inbox: dict[str, list[str]] = defaultdict(list)

    # ── Agent management ──────────────────────────────────────────

    def register_agent(self, name: str, **metadata: Any) -> None:
        """Register an agent with the relay station.

        Raises:
            ValueError: If the agent is already registered.
        """
        if name in self._agents:
            raise ValueError(f"Agent {name!r} is already registered")
        self._agents[name] = AgentInfo(name=name, metadata=metadata)
        self._log_event("", "register", name)

    def agent_info(self, name: str) -> AgentInfo:
        """Return info about a registered agent.

        Raises:
            KeyError: If the agent is not registered.
        """
        if name not in self._agents:
            raise KeyError(f"Agent {name!r} is not registered")
        return self._agents[name]

    @property
    def agents(self) -> list[str]:
        """Names of all registered agents."""
        return list(self._agents.keys())

    # ── Baton lifecycle ───────────────────────────────────────────

    def create_baton(
        self,
        payload: Any,
        sender: str,
        receiver: str | None = None,
        timeout_seconds: float | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Baton:
        """Create a new baton and register it with the station."""
        receiver = receiver or sender
        baton = Baton(
            payload=payload,
            sender=sender,
            receiver=receiver,
            timeout_seconds=timeout_seconds,
            metadata=metadata or {},
        )
        self._batons[baton.id] = baton
        self._agent_inbox[receiver].append(baton.id)
        if receiver in self._agents:
            self._agents[receiver].batons_held += 1
        self._log_event(baton.id, "create", sender, {"receiver": receiver})
        return baton

    def get_baton(self, baton_id: str) -> Baton:
        """Retrieve a baton by id.

        Raises:
            KeyError: If the baton_id is unknown.
        """
        if baton_id not in self._batons:
            raise KeyError(f"Baton {baton_id!r} not found")
        return self._batons[baton_id]

    def pass_baton(self, baton_id: str, from_agent: str, to_agent: str) -> None:
        """Record a handoff from one agent to another.

        Raises:
            KeyError: If the baton or agents are unknown.
            ValueError: If the baton is not in a passable state.
        """
        baton = self.get_baton(baton_id)
        self._require_agent(from_agent)
        self._require_agent(to_agent)
        baton.pass_to(receiver=to_agent, sender=from_agent)
        self._agent_inbox[to_agent].append(baton_id)
        self._log_event(baton_id, "pass", from_agent, {"to": to_agent})

    def acknowledge_baton(self, baton_id: str, agent: str) -> None:
        """Record that an agent has acknowledged a baton."""
        baton = self.get_baton(baton_id)
        baton.acknowledge(agent)
        self._log_event(baton_id, "ack", agent)

    def hold_baton(self, baton_id: str, agent: str) -> None:
        """Record that an agent is actively holding the baton."""
        baton = self.get_baton(baton_id)
        baton.hold(agent)
        self._log_event(baton_id, "hold", agent)

    def complete_baton(self, baton_id: str, agent: str) -> None:
        """Mark a baton as completed."""
        baton = self.get_baton(baton_id)
        baton.complete(agent)
        if agent in self._agents:
            self._agents[agent].batons_completed += 1
        self._log_event(baton_id, "complete", agent)

    def drop_baton(self, baton_id: str, agent: str, reason: str | None = None) -> None:
        """Mark a baton as dropped."""
        baton = self.get_baton(baton_id)
        baton.drop(agent, reason)
        if agent in self._agents:
            self._agents[agent].batons_dropped += 1
        self._log_event(baton_id, "drop", agent, {"reason": reason})

    def fork_baton(self, baton_id: str, new_receiver: str) -> Baton:
        """Fork an existing baton to a new receiver.

        Returns the child baton.
        """
        baton = self.get_baton(baton_id)
        child = baton.fork(new_receiver)
        self._batons[child.id] = child
        self._agent_inbox[new_receiver].append(child.id)
        if new_receiver in self._agents:
            self._agents[new_receiver].batons_held += 1
        self._log_event(baton_id, "fork", baton.receiver or baton.sender, {"child": child.id})
        return child

    # ── Queries ───────────────────────────────────────────────────

    @property
    def batons(self) -> list[Baton]:
        """All batons tracked by this station."""
        return list(self._batons.values())

    def inbox(self, agent: str) -> list[Baton]:
        """Return batons in an agent's inbox (non-terminal)."""
        return [
            self._batons[bid]
            for bid in self._agent_inbox.get(agent, [])
            if bid in self._batons and not self._batons[bid].is_terminal()
        ]

    def active_batons(self) -> list[Baton]:
        """Return all non-terminal batons."""
        return [b for b in self._batons.values() if not b.is_terminal()]

    def history(self, baton_id: str | None = None) -> list[RelayEvent]:
        """Return relay events, optionally filtered by baton_id."""
        if baton_id is None:
            return list(self._log)
        return [e for e in self._log if e.baton_id == baton_id]

    def check_timeouts(self) -> list[Baton]:
        """Check all active batons for timeouts.

        Returns:
            List of batons that just timed out.
        """
        timed_out: list[Baton] = []
        for baton in self._batons.values():
            if baton.check_timeout():
                timed_out.append(baton)
                self._log_event(baton.id, "timeout", baton.receiver or baton.sender)
        return timed_out

    # ── Internals ─────────────────────────────────────────────────

    def _require_agent(self, name: str) -> None:
        if name not in self._agents:
            raise KeyError(f"Agent {name!r} is not registered")

    def _log_event(
        self, baton_id: str, action: str, agent: str, details: dict[str, Any] | None = None
    ) -> None:
        self._log.append(
            RelayEvent(
                baton_id=baton_id,
                action=action,
                agent=agent,
                timestamp=time.time(),
                details=details or {},
            )
        )
