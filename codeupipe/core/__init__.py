"""
Core Module: Base Protocols and Classes

The foundation — protocols, abstract base classes, and fundamental types.
"""

from .payload import Payload, MutablePayload
from .filter import Filter
from .pipeline import Pipeline
from .valve import Valve
from .tap import Tap
from .state import State
from .hook import Hook

__all__ = [
    "Payload", "MutablePayload",
    "Filter", "Pipeline", "Valve", "Tap",
    "State", "Hook",
]