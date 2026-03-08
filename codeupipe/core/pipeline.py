"""
Pipeline: The Orchestrator

The Pipeline orchestrates filter execution with hooks, taps, and state tracking.
Filters run in sequence; Valves provide conditional flow control;
Taps provide observation points; Hooks provide lifecycle integration.
"""

import asyncio
import inspect
import json
import sys
import time
from pathlib import Path
from typing import Any, AsyncIterator, Dict, List, Optional, Set, Tuple, TypeVar, Generic, Union
from .payload import Payload
from .filter import Filter
from .stream_filter import StreamFilter
from .tap import Tap
from .hook import Hook
from .state import State
from .event import PipelineEvent, EventEmitter
from .govern import (
    PayloadSchema, SchemaViolation, ContractViolation, PipelineTimeoutError,
    AuditTrail, AuditHook, DeadLetterHandler,
)

__all__ = ["Pipeline", "CircuitOpenError"]


class CircuitOpenError(Exception):
    """Raised when a circuit breaker is open and rejecting calls."""


TInput = TypeVar('TInput')
TOutput = TypeVar('TOutput')


class Pipeline(Generic[TInput, TOutput]):
    """
    Orchestrator — runs filters in sequence with hooks, taps, and state tracking.

    Build a pipeline by adding filters (.add_filter), taps (.add_tap),
    and hooks (.use_hook). Run it with .run(payload).
    After execution, inspect .state for execution metadata.
    """

    def __init__(self):
        self._steps: List[Tuple[str, Union[Filter, Tap], str]] = []  # (name, step, type)
        self._hooks: List[Hook] = []
        self._state: State = State()
        self._emitter: EventEmitter = EventEmitter()
        self._observe_timing: bool = False
        self._observe_lineage: bool = False
        self._disabled_taps: frozenset = frozenset()  # runtime tap toggle
        # Govern — contracts
        self._require_input_keys: Optional[Set[str]] = None
        self._guarantee_output_keys: Optional[Set[str]] = None
        self._input_schema: Optional[PayloadSchema] = None
        self._output_schema: Optional[PayloadSchema] = None

    @property
    def state(self) -> State:
        """Access pipeline execution state after run()."""
        return self._state

    def add_filter(self, filter: Filter[TInput, TOutput], name: Optional[str] = None) -> None:
        """Add a filter to the pipeline."""
        filter_name = name or filter.__class__.__name__
        self._steps.append((filter_name, filter, "filter"))

    def add_tap(self, tap: Tap, name: Optional[str] = None) -> None:
        """Add a tap (observation point) to the pipeline."""
        tap_name = name or tap.__class__.__name__
        self._steps.append((tap_name, tap, "tap"))

    def use_hook(self, hook: Hook) -> None:
        """Attach a lifecycle hook."""
        self._hooks.append(hook)

    def add_parallel(
        self, filters: List[Filter], name: str, *, names: Optional[List[str]] = None
    ) -> None:
        """Add a parallel fan-out/fan-in group of filters."""
        self._steps.append((name, (filters, names), "parallel"))

    def add_pipeline(self, pipeline: 'Pipeline', name: str) -> None:
        """Nest a Pipeline as a single step inside this Pipeline."""
        self._steps.append((name, pipeline, "pipeline"))

    def observe(self, *, timing: bool = True, lineage: bool = False) -> None:
        """Enable observation features (timing, lineage tracking)."""
        self._observe_timing = timing
        self._observe_lineage = lineage

    # ------------------------------------------------------------------
    # Govern — contracts and schemas
    # ------------------------------------------------------------------

    def require_input(self, *keys: str) -> None:
        """Declare required input keys — validated at the start of run()."""
        self._require_input_keys = set(keys)

    def guarantee_output(self, *keys: str) -> None:
        """Declare guaranteed output keys — validated at the end of run()."""
        self._guarantee_output_keys = set(keys)

    def require_input_schema(self, schema: PayloadSchema) -> None:
        """Attach a schema to validate input payloads at the start of run()."""
        self._input_schema = schema

    def guarantee_output_schema(self, schema: PayloadSchema) -> None:
        """Attach a schema to validate output payloads at the end of run()."""
        self._output_schema = schema

    def enable_audit(self, trail: Optional['AuditTrail'] = None) -> 'AuditTrail':
        """Attach an AuditHook and return the AuditTrail for later inspection."""
        if trail is None:
            trail = AuditTrail()
        self.use_hook(AuditHook(trail))
        return trail

    def on(self, event_kind: str, callback) -> None:
        """Subscribe to pipeline events. Use '*' for all events."""
        self._emitter.on(event_kind, callback)

    def off(self, event_kind: str, callback) -> None:
        """Unsubscribe from pipeline events."""
        self._emitter.off(event_kind, callback)

    async def call(self, payload: Payload[TInput]) -> Payload[TOutput]:
        """Filter protocol — allows a Pipeline to be used as a step in another Pipeline."""
        return await self.run(payload)

    @staticmethod
    async def _invoke(fn, *args):
        """Call fn(*args), awaiting the result only if it is a coroutine."""
        result = fn(*args)
        if inspect.isawaitable(result):
            result = await result
        return result

    async def run(self, initial_payload: Payload[TInput]) -> Payload[TOutput]:
        """Execute the pipeline — flow payload through all filters and taps."""
        # Check for StreamFilters — .run() is 1→1, StreamFilters are 0..N
        for name, step, step_type in self._steps:
            if step_type == "filter" and self._is_stream_filter(step):
                raise ValueError(
                    f"Pipeline contains StreamFilter '{name}'. "
                    f"Use pipeline.stream(source) with an async generator instead. "
                    f"Example: async for result in pipeline.stream(async_generator_of_payloads): ..."
                )

        self._state = State()
        payload = initial_payload
        _step_name: Optional[str] = None
        _step_t0: Optional[float] = None

        # Govern — validate input contracts
        if self._require_input_keys:
            data = payload.to_dict()
            missing = self._require_input_keys - set(data.keys())
            if missing:
                raise ContractViolation(
                    f"Input contract violated — missing keys: {', '.join(sorted(missing))}"
                )
        if self._input_schema:
            self._input_schema.validate(payload)

        # Emit pipeline.start
        await self._emitter.emit(PipelineEvent(
            kind="pipeline.start", trace_id=getattr(payload, 'trace_id', None),
        ))

        # Hook: pipeline start
        for hook in self._hooks:
            await self._invoke(hook.before, None, payload)

        try:
            for name, step, step_type in self._steps:
                _step_name = name
                _step_t0 = None

                if step_type == "tap":
                    if name in self._disabled_taps:
                        self._state.mark_skipped(name)
                        continue
                    await self._invoke(step.observe, payload)  # type: ignore
                    self._state.mark_executed(name)
                    continue

                _step_t0 = time.monotonic()
                await self._emitter.emit(PipelineEvent(
                    kind="step.start", step_name=name, trace_id=getattr(payload, 'trace_id', None),
                ))

                if step_type == "parallel":
                    filters_list, _names = step
                    results = await asyncio.gather(*[
                        self._invoke(f.call, payload) for f in filters_list
                    ])
                    for result in results:
                        payload = payload.merge(result)
                    self._state.mark_executed(name)

                elif step_type == "pipeline":
                    for hook in self._hooks:
                        await self._invoke(hook.before, step, payload)
                    payload = await step.run(payload)
                    self._state.mark_executed(name)
                    for hook in self._hooks:
                        await self._invoke(hook.after, step, payload)

                else:
                    # filter or valve
                    for hook in self._hooks:
                        await self._invoke(hook.before, step, payload)

                    payload = await self._invoke(step.call, payload)  # type: ignore

                    if hasattr(step, '_last_skipped') and step._last_skipped:
                        self._state.mark_skipped(name)
                    else:
                        self._state.mark_executed(name)

                    for hook in self._hooks:
                        await self._invoke(hook.after, step, payload)

                # Post-step instrumentation
                duration = time.monotonic() - _step_t0
                if self._observe_timing:
                    self._state.record_timing(name, duration)
                if self._observe_lineage:
                    payload = payload._stamp(name)
                await self._emitter.emit(PipelineEvent(
                    kind="step.end", step_name=name, duration=duration,
                    trace_id=getattr(payload, 'trace_id', None),
                ))

        except Exception as e:
            if _step_t0 is not None and _step_name is not None:
                duration = time.monotonic() - _step_t0
                if self._observe_timing:
                    self._state.record_timing(_step_name, duration)
                await self._emitter.emit(PipelineEvent(
                    kind="step.error", step_name=_step_name, duration=duration,
                    error=e, trace_id=getattr(payload, 'trace_id', None),
                ))
            for hook in self._hooks:
                await self._invoke(hook.on_error, None, e, payload)
            raise

        # Hook: pipeline end
        for hook in self._hooks:
            await self._invoke(hook.after, None, payload)

        # Emit pipeline.end
        await self._emitter.emit(PipelineEvent(
            kind="pipeline.end", trace_id=getattr(payload, 'trace_id', None),
        ))

        # Govern — validate output contracts
        if self._guarantee_output_keys:
            data = payload.to_dict()
            missing = self._guarantee_output_keys - set(data.keys())
            if missing:
                raise ContractViolation(
                    f"Output contract violated — missing keys: {', '.join(sorted(missing))}"
                )
        if self._output_schema:
            self._output_schema.validate(payload)

        return payload  # type: ignore

    def run_sync(self, initial_payload: Payload[TInput]) -> Payload[TOutput]:
        """Synchronous convenience wrapper — no manual asyncio.run() needed."""
        return asyncio.run(self.run(initial_payload))

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def describe(self) -> Dict[str, Any]:
        """Return a machine-readable tree of the pipeline structure.

        Useful for tooling, debugging, and visualizing pipeline topology.
        """
        steps = []
        for name, step, step_type in self._steps:
            if step_type == "parallel":
                filters_list, names_list = step
                par_names = names_list or [None] * len(filters_list)
                step_desc: Dict[str, Any] = {
                    "name": name,
                    "type": "parallel",
                    "filters": [
                        {"name": n or f.__class__.__name__, "type": "filter"}
                        for f, n in zip(filters_list, par_names)
                    ],
                }
            elif step_type == "pipeline":
                step_desc = {
                    "name": name,
                    "type": "pipeline",
                    "children": step.describe()["steps"],
                }
            else:
                step_desc = {
                    "name": name,
                    "type": step_type,
                    "class": step.__class__.__name__,
                }
            steps.append(step_desc)

        return {
            "steps": steps,
            "hooks": [h.__class__.__name__ for h in self._hooks],
            "step_count": len(steps),
        }

    # ------------------------------------------------------------------
    # Streaming
    # ------------------------------------------------------------------

    @staticmethod
    def _is_stream_filter(step) -> bool:
        """Check if a step implements the StreamFilter protocol (has .stream())."""
        return hasattr(step, 'stream') and callable(getattr(step, 'stream'))

    async def stream(
        self,
        source: AsyncIterator[Payload[TInput]],
    ) -> AsyncIterator[Payload[TOutput]]:
        """
        Stream payloads through the pipeline, one chunk at a time.

        source: An async iterable of Payload chunks.
        Yields: Transformed Payload chunks as they flow out.

        - Regular Filters are auto-adapted: 1 chunk in → 1 chunk out.
        - StreamFilters can yield 0, 1, or N chunks per input.
        - Valves gate per-chunk (predicate evaluated on each chunk).
        - Taps observe each chunk.
        - Hooks fire once per filter at stream-start and stream-end.
        - State tracks chunks_processed per step.
        """
        self._state = State()

        # Hook: pipeline start (payload=None-ish, use empty payload as sentinel)
        sentinel = Payload()
        for hook in self._hooks:
            await self._invoke(hook.before, None, sentinel)

        try:
            # Build the processing chain as nested async generators
            async def _source_gen():
                async for chunk in source:
                    yield chunk

            current = _source_gen()

            for name, step, step_type in self._steps:
                current = self._wrap_step(current, name, step, step_type)

            # Drain the chain, yielding results to the caller
            async for result in current:
                yield result

        except Exception as e:
            for hook in self._hooks:
                await self._invoke(hook.on_error, None, e, sentinel)
            raise

        # Hook: pipeline end
        for hook in self._hooks:
            await self._invoke(hook.after, None, sentinel)

    async def _wrap_step(
        self,
        upstream: AsyncIterator[Payload],
        name: str,
        step,
        step_type: str,
    ) -> AsyncIterator[Payload]:
        """Wrap a single step around an upstream async iterator."""

        # --- Tap: observe each chunk, pass through unchanged ---
        if step_type == "tap":
            if name in self._disabled_taps:
                self._state.mark_skipped(name)
                async for chunk in upstream:
                    yield chunk
                return
            if name not in self._state.executed:
                self._state.mark_executed(name)
            async for chunk in upstream:
                await self._invoke(step.observe, chunk)  # type: ignore
                self._state.increment_chunks(name)
                yield chunk
            return

        # --- Filter or Valve ---
        # Fire hook.before once at the start of this step's stream
        for hook in self._hooks:
            await self._invoke(hook.before, step, Payload())

        is_valve = hasattr(step, '_predicate')
        is_stream = self._is_stream_filter(step)

        if name not in self._state.executed and name not in self._state.skipped:
            self._state.mark_executed(name)

        async for chunk in upstream:
            # Valve gating — per-chunk predicate
            if is_valve:
                if not step._predicate(chunk):
                    self._state.increment_chunks(name)  # counted but skipped
                    yield chunk
                    continue

            if is_stream:
                # StreamFilter: yield 0..N chunks per input
                stream_result = step.stream(chunk)
                if inspect.isasyncgen(stream_result):
                    async for out in stream_result:
                        self._state.increment_chunks(name)
                        yield out
                else:
                    for out in stream_result:
                        self._state.increment_chunks(name)
                        yield out
            else:
                # Regular Filter: 1 chunk in → 1 chunk out
                result = await self._invoke(step.call, chunk)  # type: ignore
                self._state.increment_chunks(name)
                yield result

        # Fire hook.after once at the end of this step's stream
        for hook in self._hooks:
            await self._invoke(hook.after, step, Payload())

    # ------------------------------------------------------------------
    # Resilience wrappers
    # ------------------------------------------------------------------

    def with_retry(self, max_retries: int = 3) -> '_RetryPipeline':
        """Return a wrapper that retries the entire pipeline on failure."""
        return _RetryPipeline(self, max_retries)

    def with_circuit_breaker(self, failure_threshold: int = 5) -> '_CircuitBreakerPipeline':
        """Return a wrapper that opens a circuit breaker after consecutive failures."""
        return _CircuitBreakerPipeline(self, failure_threshold)

    def with_timeout(self, seconds: float) -> '_TimeoutPipeline':
        """Return a wrapper that cancels if run() exceeds the given duration."""
        return _TimeoutPipeline(self, seconds)

    def with_rate_limit(self, calls_per_second: float) -> '_RateLimitedPipeline':
        """Return a wrapper that throttles run() to at most calls_per_second invocations."""
        return _RateLimitedPipeline(self, calls_per_second)

    def with_dead_letter(self, handler: 'DeadLetterHandler') -> '_DeadLetterPipeline':
        """Return a wrapper that routes failed payloads to a handler instead of raising."""
        return _DeadLetterPipeline(self, handler)

    # ------------------------------------------------------------------
    # Config-driven assembly
    # ------------------------------------------------------------------

    _VALID_STEP_TYPES = {"filter", "tap", "hook", "stream-filter", "valve", "parallel", "pipeline"}

    @classmethod
    def from_config(cls, path: str, *, registry: Any) -> "Pipeline":
        """Build a Pipeline from a TOML or JSON config file.

        Config format (TOML shown, JSON identical structure):
            [pipeline]
            name = "my-pipeline"
            [[pipeline.steps]]
            name = "AddTenFilter"
            type = "filter"
            [pipeline.steps.config]
            amount = 42

        Supports Ring 3 features:
            - type = "parallel" with "filters" array for fan-out/fan-in
            - type = "pipeline" with nested "steps" for pipeline-as-step
            - pipeline.retry = {max_retries = 3} for pipeline-level retry
            - pipeline.circuit_breaker = {failure_threshold = 5} for circuit breaker

        Args:
            path: Path to a .toml or .json config file.
            registry: A Registry instance for name → component resolution.

        Returns:
            A fully-assembled Pipeline (or resilience wrapper) ready to .run().
        """
        config_path = Path(path)
        if not config_path.exists():
            raise FileNotFoundError(f"Config file not found: {path}")

        suffix = config_path.suffix.lower()
        text = config_path.read_text()

        if suffix == ".toml":
            data = cls._parse_toml(text)
        elif suffix == ".json":
            data = json.loads(text)
        else:
            raise ValueError(f"Unsupported config format '{suffix}'. Use .toml or .json")

        if "pipeline" not in data:
            raise ValueError("Config must contain a 'pipeline' key")

        pipeline_cfg = data["pipeline"]
        if "steps" not in pipeline_cfg:
            raise ValueError("Config 'pipeline' must contain 'steps'")

        pipe = cls._build_from_steps(pipeline_cfg["steps"], registry=registry)

        # Apply observe config
        if "observe" in pipeline_cfg:
            obs = pipeline_cfg["observe"]
            pipe.observe(
                timing=obs.get("timing", False),
                lineage=obs.get("lineage", False),
            )

        # Apply govern config — contracts
        if "require_input" in pipeline_cfg:
            pipe.require_input(*pipeline_cfg["require_input"])
        if "guarantee_output" in pipeline_cfg:
            pipe.guarantee_output(*pipeline_cfg["guarantee_output"])

        # Wrap with govern wrappers first (innermost layer)
        result: Any = pipe

        if "dead_letter" in pipeline_cfg:
            dl_name = pipeline_cfg["dead_letter"]
            dl_handler = registry.get(dl_name)
            result = _DeadLetterPipeline(result, dl_handler)

        if "timeout" in pipeline_cfg:
            result = _TimeoutPipeline(result, float(pipeline_cfg["timeout"]))

        if "rate_limit" in pipeline_cfg:
            rl = pipeline_cfg["rate_limit"]
            cps = rl if isinstance(rl, (int, float)) else rl.get("calls_per_second", 10)
            result = _RateLimitedPipeline(result, float(cps))

        # Wrap with resilience if configured (outermost layer)
        if "circuit_breaker" in pipeline_cfg and "retry" in pipeline_cfg:
            threshold = pipeline_cfg["circuit_breaker"].get("failure_threshold", 5)
            max_retries = pipeline_cfg["retry"].get("max_retries", 3)
            cb = _CircuitBreakerPipeline(result, threshold)
            return _RetryPipeline(cb, max_retries)  # type: ignore[return-value]

        if "circuit_breaker" in pipeline_cfg:
            threshold = pipeline_cfg["circuit_breaker"].get("failure_threshold", 5)
            return _CircuitBreakerPipeline(result, threshold)  # type: ignore[return-value]

        if "retry" in pipeline_cfg:
            max_retries = pipeline_cfg["retry"].get("max_retries", 3)
            return _RetryPipeline(result, max_retries)  # type: ignore[return-value]

        return result

    @classmethod
    def _build_from_steps(cls, steps_cfg: List[Dict], *, registry: Any) -> "Pipeline":
        """Build a Pipeline from a list of step config dicts (recursive)."""
        pipe = cls()
        for step_cfg in steps_cfg:
            step_name = step_cfg["name"]
            step_type = step_cfg.get("type", "filter")
            step_kwargs = step_cfg.get("config", {})

            if step_type not in cls._VALID_STEP_TYPES:
                raise ValueError(
                    f"Unknown step type '{step_type}'. "
                    f"Valid types: {', '.join(sorted(cls._VALID_STEP_TYPES))}"
                )

            if step_type == "parallel":
                if "filters" not in step_cfg:
                    raise ValueError(
                        f"Parallel step '{step_name}' requires a 'filters' key "
                        f"with an array of filter references"
                    )
                filters = []
                for f_cfg in step_cfg["filters"]:
                    f_kwargs = f_cfg.get("config", {})
                    filters.append(registry.get(f_cfg["name"], **f_kwargs))
                pipe.add_parallel(filters, name=step_name)
                continue

            if step_type == "pipeline":
                if "steps" not in step_cfg:
                    raise ValueError(
                        f"Pipeline step '{step_name}' requires a 'steps' key "
                        f"with an array of nested step definitions"
                    )
                inner = cls._build_from_steps(step_cfg["steps"], registry=registry)
                pipe.add_pipeline(inner, name=step_name)
                continue

            instance = registry.get(step_name, **step_kwargs)

            if step_type == "tap":
                pipe.add_tap(instance, name=step_name)
            elif step_type == "hook":
                pipe.use_hook(instance)
            else:
                pipe.add_filter(instance, name=step_name)

        return pipe

    @staticmethod
    def _parse_toml(text: str) -> dict:
        """Parse TOML text, using stdlib tomllib (3.11+) or fallback."""
        if sys.version_info >= (3, 11):
            import tomllib
            return tomllib.loads(text)
        try:
            import tomli
            return tomli.loads(text)
        except ImportError:
            raise ImportError(
                "TOML config requires Python 3.11+ or the 'tomli' package. "
                "Install with: pip install tomli"
            )


# ──────────────────────────────────────────────────────────────
# Resilience wrappers (returned by Pipeline.with_retry / with_circuit_breaker)
# ──────────────────────────────────────────────────────────────

class _RetryPipeline:
    """Wraps a Pipeline with retry logic — re-runs on failure up to max_retries times."""

    def __init__(self, pipeline: Pipeline, max_retries: int):
        self._pipeline = pipeline
        self._max_retries = max_retries

    async def run(self, payload: Payload) -> Payload:
        last_error: Optional[Exception] = None
        for _attempt in range(1 + self._max_retries):
            try:
                return await self._pipeline.run(payload)
            except Exception as e:
                last_error = e
                # Emit retry event if the inner pipeline has an emitter
                if hasattr(self._pipeline, '_emitter'):
                    await self._pipeline._emitter.emit(PipelineEvent(
                        kind="pipeline.retry",
                        metadata={"attempt": _attempt + 1, "max_retries": self._max_retries},
                        error=e,
                        trace_id=getattr(payload, 'trace_id', None),
                    ))
        raise last_error  # type: ignore[misc]

    def run_sync(self, payload: Payload) -> Payload:
        return asyncio.run(self.run(payload))


class _CircuitBreakerPipeline:
    """Wraps a Pipeline with a circuit breaker — opens after consecutive failures."""

    def __init__(self, pipeline: Pipeline, failure_threshold: int):
        self._pipeline = pipeline
        self._failure_threshold = failure_threshold
        self._consecutive_failures = 0

    async def run(self, payload: Payload) -> Payload:
        if self._consecutive_failures >= self._failure_threshold:
            # Emit circuit.open event if the inner pipeline has an emitter
            if hasattr(self._pipeline, '_emitter'):
                await self._pipeline._emitter.emit(PipelineEvent(
                    kind="circuit.open",
                    trace_id=getattr(payload, 'trace_id', None),
                ))
            raise CircuitOpenError(
                f"Circuit breaker open after {self._failure_threshold} consecutive failures"
            )
        try:
            result = await self._pipeline.run(payload)
            self._consecutive_failures = 0
            return result
        except Exception:
            self._consecutive_failures += 1
            raise

    def run_sync(self, payload: Payload) -> Payload:
        return asyncio.run(self.run(payload))


class _TimeoutPipeline:
    """Wraps a Pipeline with a timeout — raises PipelineTimeoutError on expiry."""

    def __init__(self, pipeline: Pipeline, seconds: float):
        self._pipeline = pipeline
        self._seconds = seconds

    async def run(self, payload: Payload) -> Payload:
        try:
            return await asyncio.wait_for(self._pipeline.run(payload), timeout=self._seconds)
        except asyncio.TimeoutError:
            # Emit timeout event
            if hasattr(self._pipeline, '_emitter'):
                await self._pipeline._emitter.emit(PipelineEvent(
                    kind="pipeline.timeout",
                    metadata={"timeout_seconds": self._seconds},
                    trace_id=getattr(payload, 'trace_id', None),
                ))
            raise PipelineTimeoutError(
                f"Pipeline timed out after {self._seconds}s"
            )

    def run_sync(self, payload: Payload) -> Payload:
        return asyncio.run(self.run(payload))


class _RateLimitedPipeline:
    """Wraps a Pipeline with token-bucket rate limiting."""

    def __init__(self, pipeline: Pipeline, calls_per_second: float):
        self._pipeline = pipeline
        self._min_interval = 1.0 / calls_per_second
        self._last_call: float = 0.0

    async def run(self, payload: Payload) -> Payload:
        now = time.monotonic()
        elapsed = now - self._last_call
        if elapsed < self._min_interval:
            await asyncio.sleep(self._min_interval - elapsed)
        self._last_call = time.monotonic()
        return await self._pipeline.run(payload)

    def run_sync(self, payload: Payload) -> Payload:
        return asyncio.run(self.run(payload))


class _DeadLetterPipeline:
    """Wraps a Pipeline — routes failed payloads to a handler instead of raising."""

    def __init__(self, pipeline: Pipeline, handler: DeadLetterHandler):
        self._pipeline = pipeline
        self._handler = handler

    async def run(self, payload: Payload) -> Payload:
        try:
            return await self._pipeline.run(payload)
        except Exception as e:
            # Emit dead_letter event
            if hasattr(self._pipeline, '_emitter'):
                await self._pipeline._emitter.emit(PipelineEvent(
                    kind="dead_letter",
                    error=e,
                    trace_id=getattr(payload, 'trace_id', None),
                ))
            await self._handler.handle(payload, e)
            return payload  # return original payload as-is

    def run_sync(self, payload: Payload) -> Payload:
        return asyncio.run(self.run(payload))
