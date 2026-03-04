"""
Pipeline: The Orchestrator

The Pipeline orchestrates filter execution with hooks, taps, and state tracking.
Filters run in sequence; Valves provide conditional flow control;
Taps provide observation points; Hooks provide lifecycle integration.
"""

from typing import Any, Dict, List, Optional, Set, Tuple, TypeVar, Generic, Union
from .payload import Payload
from .filter import Filter
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

    async def run(self, initial_payload: Payload[TInput]) -> Payload[TOutput]:
        """Execute the pipeline — flow payload through all filters and taps."""
        self._state = State()
        payload = initial_payload

        # Hook: pipeline start
        for hook in self._hooks:
            await hook.before(None, payload)

        try:
            for name, step in self._steps:
                step_type = self._step_types[name]

                if step_type == "tap":
                    await step.observe(payload)  # type: ignore
                    self._state.mark_executed(name)
                    continue

                # It's a filter (or valve — valves conform to Filter protocol)
                for hook in self._hooks:
                    await hook.before(step, payload)

                prev_payload = payload
                payload = await step.call(payload)  # type: ignore

                # Track valve skips: if payload is unchanged, the valve skipped
                if hasattr(step, '_predicate') and payload is prev_payload:
                    self._state.mark_skipped(name)
                else:
                    self._state.mark_executed(name)

                for hook in self._hooks:
                    await hook.after(step, payload)

        except Exception as e:
            for hook in self._hooks:
                await hook.on_error(None, e, payload)
            raise

        # Hook: pipeline end
        for hook in self._hooks:
            await hook.after(None, payload)

        return payload  # type: ignore
