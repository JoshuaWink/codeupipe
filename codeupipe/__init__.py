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
from .converter import load_config, DEFAULT_CONFIG, PATTERN_DEFAULTS
from .converter.pipelines import build_export_pipeline, build_import_pipeline
from .registry import Registry, cup_component, default_registry

from importlib.metadata import version as _pkg_version, PackageNotFoundError
try:
    __version__ = _pkg_version("codeupipe")
except PackageNotFoundError:
    __version__ = "0.1.0"  # fallback for editable / non-installed usage
__all__ = [
    # Core
    "Payload", "MutablePayload",
    "Filter", "StreamFilter", "Pipeline", "Valve", "Tap",
    "State", "Hook",
    # Utils
    "ErrorHandlingMixin", "RetryFilter",
    # Converter
    "load_config", "DEFAULT_CONFIG", "PATTERN_DEFAULTS",
    "build_export_pipeline", "build_import_pipeline",
    # Registry
    "Registry", "cup_component", "default_registry",
]