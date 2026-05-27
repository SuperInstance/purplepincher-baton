"""PurplePincher Baton — relay and baton-passing for distributed task handoffs."""

from .baton import Baton, BatonState
from .relay import RelayStation
from .route import BatonRoute, RouteStep, StepType
from .checkpoint import Checkpoint, CheckpointStatus
from .timeout import TimeoutHandler, TimeoutPolicy

__all__ = [
    "Baton",
    "BatonState",
    "RelayStation",
    "BatonRoute",
    "RouteStep",
    "StepType",
    "Checkpoint",
    "CheckpointStatus",
    "TimeoutHandler",
    "TimeoutPolicy",
]
__version__ = "0.1.0"
