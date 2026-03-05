"""
codeupipe: Pipeline framework for Python

Composable Payload-Filter-Pipeline pattern with Valves, Taps, Hooks, and Streaming.
Filters and Taps can be sync or async. Zero external dependencies.

Core concepts:
- Payload: Immutable data container flowing through the pipeline
- MutablePayload: Mutable sibling for performance-critical bulk edits
- Filter: Processing unit that transforms payloads (sync or async)
- StreamFilter: Streaming unit — yields 0, 1, or N output chunks per input
- Pipeline: Orchestrator — .run() for batch, .stream() for streaming
- Valve: Conditional flow control — gates a filter with a predicate
- Tap: Non-modifying observation point (sync or async)
- State: Pipeline execution metadata — tracks executed, skipped, errors, chunk counts
- Hook: Lifecycle hooks — before / after / on_error (sync or async)
"""

from .core import Payload, MutablePayload, Filter, StreamFilter, Pipeline, Valve, Tap, State, Hook
from .utils import ErrorHandlingMixin, RetryFilter

__version__ = "0.1.0"
__all__ = [
    # Core
    "Payload", "MutablePayload",
    "Filter", "StreamFilter", "Pipeline", "Valve", "Tap",
    "State", "Hook",
    # Utils
    "ErrorHandlingMixin", "RetryFilter",
]