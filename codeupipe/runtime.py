"""
codeupipe.runtime — Live pipeline control for production.

Provides zero-downtime capabilities:
- TapSwitch: Enable/disable taps at runtime without restarting.
- HotSwap: Atomically replace the active Pipeline from a new config.

Both are designed for long-running servers where uptime matters.
Zero external dependencies.
"""

import threading
from typing import Any, Dict, List, Optional, Set

__all__ = ["TapSwitch", "HotSwap"]


# ── TapSwitch — toggle taps at runtime ──────────────────────────────


class TapSwitch:
    """Control which taps are active on a Pipeline at runtime.

    Wrap a Pipeline to toggle observation taps on/off by name without
    restarting the server. Uses a thread-safe set of disabled tap names.

    Usage:
        switch = TapSwitch(pipeline)
        switch.disable("verbose_logger")    # stop observing
        switch.enable("verbose_logger")     # resume observing
        switch.disable_all()                # silence everything
        switch.enable_all()                 # restore everything
        switch.status()                     # → {"verbose_logger": True, ...}
    """

    def __init__(self, pipeline: Any):
        self._pipeline = pipeline
        self._lock = threading.Lock()
        self._disabled: Set[str] = set()

    def disable(self, tap_name: str) -> None:
        """Disable a tap by name — it will be skipped during pipeline.run()."""
        with self._lock:
            self._disabled.add(tap_name)
            self._apply()

    def enable(self, tap_name: str) -> None:
        """Re-enable a previously disabled tap."""
        with self._lock:
            self._disabled.discard(tap_name)
            self._apply()

    def disable_all(self) -> None:
        """Disable all taps on the pipeline."""
        with self._lock:
            for name, _step, step_type in self._pipeline._steps:
                if step_type == "tap":
                    self._disabled.add(name)
            self._apply()

    def enable_all(self) -> None:
        """Re-enable all taps."""
        with self._lock:
            self._disabled.clear()
            self._apply()

    def is_disabled(self, tap_name: str) -> bool:
        """Check if a specific tap is currently disabled."""
        with self._lock:
            return tap_name in self._disabled

    @property
    def disabled(self) -> Set[str]:
        """Return the set of currently disabled tap names."""
        with self._lock:
            return set(self._disabled)

    def status(self) -> Dict[str, bool]:
        """Return {tap_name: enabled} for all taps on the pipeline."""
        with self._lock:
            result: Dict[str, bool] = {}
            for name, _step, step_type in self._pipeline._steps:
                if step_type == "tap":
                    result[name] = name not in self._disabled
            return result

    def _apply(self) -> None:
        """Sync the pipeline's disabled-taps set from our state.

        The Pipeline checks _disabled_taps during run() to skip taps.
        This is an atomic reference swap — safe for concurrent requests.
        """
        # Atomic reference swap: build new frozenset, assign in one op
        self._pipeline._disabled_taps = frozenset(self._disabled)


# ── HotSwap — atomic pipeline replacement ───────────────────────────


class HotSwap:
    """Atomically replace the active Pipeline for zero-downtime updates.

    Holds a reference to the current Pipeline behind a lock.  On reload(),
    builds a new Pipeline from the config file and swaps it in.
    In-flight requests finish on the old pipeline; new requests hit the new.

    Usage:
        swap = HotSwap("pipeline.json", registry=my_registry)
        result = await swap.run(payload)       # uses current pipeline

        swap.reload()                           # hot-swap to new config
        result = await swap.run(payload)       # uses updated pipeline

        # Or reload from a different config:
        swap.reload("pipeline_v2.json")
    """

    def __init__(self, config_path: str, *, registry: Any):
        from codeupipe.core.pipeline import Pipeline

        self._config_path = config_path
        self._registry = registry
        self._lock = threading.Lock()
        self._pipeline = Pipeline.from_config(config_path, registry=registry)
        self._version: int = 1

    @property
    def pipeline(self) -> Any:
        """The currently active Pipeline instance."""
        return self._pipeline

    @property
    def version(self) -> int:
        """The reload version counter (starts at 1, increments on reload)."""
        return self._version

    @property
    def config_path(self) -> str:
        """The path of the currently loaded config."""
        return self._config_path

    async def run(self, payload: Any) -> Any:
        """Run the payload through the current pipeline.

        Safe for concurrent use — reads are lock-free (reference read).
        """
        pipe = self._pipeline  # snapshot the reference
        return await pipe.run(payload)

    def run_sync(self, payload: Any) -> Any:
        """Synchronous version of run()."""
        pipe = self._pipeline
        return pipe.run_sync(payload)

    def reload(self, config_path: Optional[str] = None) -> Dict[str, Any]:
        """Build a new Pipeline from config and swap it in atomically.

        Args:
            config_path: Optional new config path. If None, reloads current.

        Returns:
            Dict with 'version', 'config', 'steps' for confirmation.

        Raises:
            Exception: If the new config fails to parse/build. The old
                       pipeline remains active (safe rollback).
        """
        from codeupipe.core.pipeline import Pipeline

        path = config_path or self._config_path
        # Build first — if this fails, old pipeline stays active
        new_pipeline = Pipeline.from_config(path, registry=self._registry)

        with self._lock:
            self._pipeline = new_pipeline
            if config_path:
                self._config_path = config_path
            self._version += 1
            version = self._version

        step_names = [name for name, _step, _type in new_pipeline._steps]
        return {
            "version": version,
            "config": path,
            "steps": step_names,
        }
