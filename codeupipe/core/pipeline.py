"""
Pipeline: The Orchestrator

The Pipeline orchestrates filter execution with hooks, taps, and state tracking.
Filters run in sequence; Valves provide conditional flow control;
Taps provide observation points; Hooks provide lifecycle integration.
"""

import inspect
from typing import Any, AsyncIterator, Dict, List, Optional, Set, Tuple, TypeVar, Generic, Union
from .payload import Payload
from .filter import Filter
from .stream_filter import StreamFilter
from .tap import Tap
from .hook import Hook
from .state import State

__all__ = ["Pipeline"]

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
        self._steps: List[Tuple[str, Union[Filter, Tap]]] = []
        self._step_types: Dict[str, str] = {}  # name -> "filter" | "tap"
        self._hooks: List[Hook] = []
        self._state: State = State()

    @property
    def state(self) -> State:
        """Access pipeline execution state after run()."""
        return self._state

    def add_filter(self, filter: Filter[TInput, TOutput], name: Optional[str] = None) -> None:
        """Add a filter to the pipeline."""
        filter_name = name or filter.__class__.__name__
        self._steps.append((filter_name, filter))
        self._step_types[filter_name] = "filter"

    def add_tap(self, tap: Tap, name: Optional[str] = None) -> None:
        """Add a tap (observation point) to the pipeline."""
        tap_name = name or tap.__class__.__name__
        self._steps.append((tap_name, tap))
        self._step_types[tap_name] = "tap"

    def use_hook(self, hook: Hook) -> None:
        """Attach a lifecycle hook."""
        self._hooks.append(hook)

    @staticmethod
    async def _invoke(fn, *args):
        """Call fn(*args), awaiting the result only if it is a coroutine."""
        result = fn(*args)
        if inspect.isawaitable(result):
            result = await result
        return result

    async def run(self, initial_payload: Payload[TInput]) -> Payload[TOutput]:
        """Execute the pipeline — flow payload through all filters and taps."""
        self._state = State()
        payload = initial_payload

        # Hook: pipeline start
        for hook in self._hooks:
            await self._invoke(hook.before, None, payload)

        try:
            for name, step in self._steps:
                step_type = self._step_types[name]

                if step_type == "tap":
                    await self._invoke(step.observe, payload)  # type: ignore
                    self._state.mark_executed(name)
                    continue

                # It's a filter (or valve — valves conform to Filter protocol)
                for hook in self._hooks:
                    await self._invoke(hook.before, step, payload)

                prev_payload = payload
                payload = await self._invoke(step.call, payload)  # type: ignore

                # Track valve skips: if payload is unchanged, the valve skipped
                if hasattr(step, '_predicate') and payload is prev_payload:
                    self._state.mark_skipped(name)
                else:
                    self._state.mark_executed(name)

                for hook in self._hooks:
                    await self._invoke(hook.after, step, payload)

        except Exception as e:
            for hook in self._hooks:
                await self._invoke(hook.on_error, None, e, payload)
            raise

        # Hook: pipeline end
        for hook in self._hooks:
            await self._invoke(hook.after, None, payload)

        return payload  # type: ignore

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

            for name, step in self._steps:
                step_type = self._step_types[name]
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
