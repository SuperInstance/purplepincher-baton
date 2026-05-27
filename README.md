# PurplePincher Baton

> The shell outlives every crab that inhabits it.  
> Knowledge filed into the walls becomes instinct for the next.

A Python library for **baton-passing** — coordinating distributed task handoffs between agents. Each unit of work is a `Baton` that gets passed from sender to receiver through a `RelayStation`, tracked by `Checkpoint`, routed through `BatonRoute`, and guarded by `TimeoutHandler`.

## Install

```bash
pip install purplepincher-baton
```

## Quick Start

### Basic Baton Handoff

```python
from purplepincher_baton import Baton

# Create a baton
baton = Baton(payload={"task": "render frame 42"}, sender="coordinator", receiver="worker-1")

# Pass it along
baton.pass_to("worker-2")
baton.acknowledge("worker-2")

# Complete it
baton.complete("worker-2")
```

### Relay Station (Multi-Agent Coordination)

```python
from purplepincher_baton import RelayStation

station = RelayStation()
station.register_agent("coordinator")
station.register_agent("worker-1")
station.register_agent("worker-2")

# Create and hand off a baton
baton = station.create_baton(
    payload={"task": "render"},
    sender="coordinator",
    receiver="worker-1",
    timeout_seconds=30.0,
)

station.pass_baton(baton.id, from_agent="worker-1", to_agent="worker-2")
station.acknowledge_baton(baton.id, agent="worker-2")
station.complete_baton(baton.id, agent="worker-2")

# Check agent stats
info = station.agent_info("worker-2")
print(f"Completed: {info.batons_completed}")  # → 1
```

### Routes (Sequential / Parallel / Conditional)

```python
from purplepincher_baton import BatonRoute, RouteStep, StepType

route = BatonRoute(name="render-pipeline", steps=[
    RouteStep(agent="loader", label="Load assets"),
    RouteStep(agent="renderer", label="Render frame"),
    RouteStep(agent="reviewer", label="QA check",
              step_type=StepType.CONDITIONAL,
              condition=lambda p: p.get("quality") == "high"),
    RouteStep(agent="uploader", label="Upload result"),
])

# Resolve route for a given payload
groups = route.resolve(payload={"quality": "high"})
# → [["loader"], ["renderer"], ["reviewer"], ["uploader"]]

groups = route.resolve(payload={"quality": "low"})
# → [["loader"], ["renderer"], ["uploader"]]  (reviewer skipped)
```

### Checkpoints (Progress Tracking)

```python
from purplepincher_baton import Checkpoint

ck = Checkpoint(route=route, baton_id="abc123")
ck.start_step(0)
ck.complete_step(0, result={"files": 42})
ck.start_step(1)
print(ck.progress())           # → 1
print(ck.progress_fraction())  # → 0.25
print(ck.summary())
```

### Timeout Handling with Escalation

```python
from purplepincher_baton import TimeoutHandler, TimeoutPolicy

handler = TimeoutHandler(default_timeout=30.0, max_retries=3)

# Check all active batons
expired = handler.check(station.active_batons())

for baton in expired:
    handler.escalate(baton, policy=TimeoutPolicy.ESCALATE, escalate_to="supervisor")
```

## API Reference

| Module | Class | Description |
|--------|-------|-------------|
| `baton` | `Baton` | Unit of work with payload, state, timeout, history, fork |
| `baton` | `BatonState` | Enum: CREATED, HELD, PASSED, ACKNOWLEDGED, COMPLETED, DROPPED, TIMED_OUT |
| `relay` | `RelayStation` | Central ledger tracking agents, batons, and handoffs |
| `route` | `BatonRoute` | Ordered path of steps (sequential, parallel, conditional) |
| `route` | `RouteStep` | Single step in a route |
| `checkpoint` | `Checkpoint` | Progress tracker for a baton through a route |
| `timeout` | `TimeoutHandler` | Monitors batons for timeout, applies escalation policies |
| `timeout` | `TimeoutPolicy` | Enum: MARK_TIMED_OUT, RETRY, ESCALATE, DROP |

## Dependencies

None beyond Python 3.10+. Only `pytest` for development.

## License

MIT
