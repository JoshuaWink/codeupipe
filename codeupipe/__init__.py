"""
codeupipe: Pipeline framework for Python

Composable Payload-Filter-Pipeline pattern with Valves, Taps, and Hooks.

Core concepts:
- Payload: Data flowing through the pipeline
- Filter: Processing unit that transforms payloads
- Pipeline: Orchestrator that runs filters in sequence
- Valve: Conditional flow control — gates a filter with a predicate
- Tap: Non-modifying observation point
- State: Pipeline execution metadata
- Hook: Lifecycle hooks for pipeline execution
"""

from .core import Payload, MutablePayload, Filter, Pipeline, Valve, Tap, State, Hook
from .utils import ErrorHandlingMixin, RetryFilter

__version__ = "0.1.0"
__all__ = [
    # Core
    "Payload", "MutablePayload",
    "Filter", "Pipeline", "Valve", "Tap",
    "State", "Hook",
    # Utils
    "ErrorHandlingMixin", "RetryFilter",
]