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

from .core import (
    Payload, MutablePayload, Filter, StreamFilter, Pipeline, CircuitOpenError, Valve, Tap,
    State, Hook, PipelineEvent, EventEmitter,
    PayloadSchema, SchemaViolation, ContractViolation, PipelineTimeoutError,
    AuditEntry, AuditTrail, AuditHook,
    DeadLetterHandler, LogDeadLetterHandler,
)
from .utils import ErrorHandlingMixin, RetryFilter
from .converter import load_config, DEFAULT_CONFIG, PATTERN_DEFAULTS
from .converter.pipelines import build_export_pipeline, build_import_pipeline
from .registry import Registry, cup_component, default_registry
from .distribute import RemoteFilter, Checkpoint, CheckpointHook, IterableSource, FileSource, WorkerPool
from .deploy import (
    DeployTarget, DeployAdapter, DockerAdapter, find_adapters, load_manifest,
    ManifestError, resolve_recipe, list_recipes, RecipeError,
    init_project, list_templates, InitError,
)

from importlib.metadata import version as _pkg_version, PackageNotFoundError
try:
    __version__ = _pkg_version("codeupipe")
except PackageNotFoundError:
    __version__ = "0.6.0"  # fallback for editable / non-installed usage
__all__ = [
    # Core
    "Payload", "MutablePayload",
    "Filter", "StreamFilter", "Pipeline", "CircuitOpenError", "Valve", "Tap",
    "State", "Hook",
    # Observe
    "PipelineEvent", "EventEmitter",
    # Govern
    "PayloadSchema", "SchemaViolation", "ContractViolation", "PipelineTimeoutError",
    "AuditEntry", "AuditTrail", "AuditHook",
    "DeadLetterHandler", "LogDeadLetterHandler",
    # Utils
    "ErrorHandlingMixin", "RetryFilter",
    # Converter
    "load_config", "DEFAULT_CONFIG", "PATTERN_DEFAULTS",
    "build_export_pipeline", "build_import_pipeline",
    # Registry
    "Registry", "cup_component", "default_registry",
    # Distribute
    "RemoteFilter", "Checkpoint", "CheckpointHook",
    "IterableSource", "FileSource", "WorkerPool",
    # Deploy
    "DeployTarget", "DeployAdapter", "DockerAdapter",
    "find_adapters", "load_manifest", "ManifestError",
    "resolve_recipe", "list_recipes", "RecipeError",
    "init_project", "list_templates", "InitError",
]