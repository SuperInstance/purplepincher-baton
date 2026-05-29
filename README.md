# purplepincher-baton — Context-Offloading Baton

**Relay and baton-passing for distributed task handoffs. Pass context between agents like a relay race.**

## What This Gives You

- **Batons** — self-contained context packages that travel between agents
- **Relay stations** — intermediate stops where batons can be inspected, modified, or routed
- **Routes** — multi-hop paths with typed steps (compute, transfer, checkpoint, notify)
- **Checkpoints** — persist baton state at any point for recovery
- **Timeout handling** — configurable timeout policies per step or per route

## Quick Start

```bash
pip install purplepincher-baton
```

```python
from purplepincher_baton import Baton, RelayStation, BatonRoute, Checkpoint, TimeoutHandler

# Create a baton with context
baton = Baton(
    id="task-42",
    context={"files_changed": ["README.md"], "status": "in_progress"},
    payload={"readme_content": "..."},
)

# Define a route
route = BatonRoute(steps=[
    RouteStep(type="transfer", destination="agent-1"),
    RouteStep(type="compute", action="review_readme"),
    RouteStep(type="checkpoint"),
    RouteStep(type="transfer", destination="agent-2"),
    RouteStep(type="compute", action="push_changes"),
])

# Run the relay
station = RelayStation()
result = station.relay(baton, route)
print(result.status)  # COMPLETED

# With timeout handling
timeout = TimeoutHandler(policy=TimeoutPolicy(max_duration_seconds=300))
result = station.relay(baton, route, timeout=timeout)
```

## API Reference

### `Baton(id, context, payload)` · `BatonState` — PENDING, IN_TRANSIT, DELIVERED, FAILED
### `RelayStation` — `relay(baton, route) → RelayResult`
### `BatonRoute(steps)` · `RouteStep(type, destination, action)` · `StepType`
### `Checkpoint(baton_id, state, timestamp)` · `CheckpointStatus`
### `TimeoutHandler(policy)` · `TimeoutPolicy` — per-step or per-route timeouts

## How It Fits

The context-offloading system for the [SuperInstance fleet](https://github.com/SuperInstance). When agents need to hand off work, the baton carries all necessary context.

- **[cocapn-com](https://github.com/SuperInstance/cocapn-com)** — Message routing (batons ride on messages)
- **[captain](https://github.com/SuperInstance/captain)** — Task dispatching (creates batons)
- **[agent-grid](https://github.com/SuperInstance/agent-grid)** — Grid topology (routes batons)

## Testing

```bash
pytest tests/
```

## Installation

```bash
pip install purplepincher-baton
```

Python 3.10+. MIT license.
