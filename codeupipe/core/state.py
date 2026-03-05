"""
State: Pipeline Execution Metadata

State tracks what happened during pipeline execution — which filters ran,
which were skipped, timing data, and errors encountered.
Access it after pipeline.run() via pipeline.state.
"""

from typing import Any, Dict, List, Optional, Tuple

__all__ = ["State"]


class State:
    """
    Pipeline execution state — tracks filter execution, timing, and errors.

    Provides visibility into what happened during a pipeline run:
    - Which filters executed and in what order
    - Which filters were skipped (by valves)
    - Errors encountered during execution
    - Arbitrary metadata for custom tracking
    """

    def __init__(self):
        self.executed: List[str] = []
        self.skipped: List[str] = []
        self.errors: List[Tuple[str, Exception]] = []
        self.metadata: Dict[str, Any] = {}
        self.chunks_processed: Dict[str, int] = {}

    def mark_executed(self, name: str) -> None:
        """Record that a filter executed."""
        self.executed.append(name)

    def mark_skipped(self, name: str) -> None:
        """Record that a filter was skipped."""
        self.skipped.append(name)

    def increment_chunks(self, name: str, count: int = 1) -> None:
        """Increment the chunk counter for a streaming step."""
        self.chunks_processed[name] = self.chunks_processed.get(name, 0) + count

    def record_error(self, name: str, error: Exception) -> None:
        """Record an error from a filter."""
        self.errors.append((name, error))

    def set(self, key: str, value: Any) -> None:
        """Store arbitrary metadata."""
        self.metadata[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        """Retrieve metadata."""
        return self.metadata.get(key, default)

    @property
    def has_errors(self) -> bool:
        """Whether any errors were recorded."""
        return len(self.errors) > 0

    @property
    def last_error(self) -> Optional[Exception]:
        """The most recent error, or None."""
        return self.errors[-1][1] if self.errors else None

    def reset(self) -> None:
        """Reset state for a fresh run."""
        self.executed.clear()
        self.skipped.clear()
        self.errors.clear()
        self.metadata.clear()
        self.chunks_processed.clear()

    def __repr__(self) -> str:
        return (
            f"State(executed={self.executed}, skipped={self.skipped}, "
            f"errors={len(self.errors)}, chunks={self.chunks_processed})"
        )