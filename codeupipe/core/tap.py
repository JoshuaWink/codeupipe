"""
Tap: Observation Point

A Tap is a non-modifying observation point in the pipeline.
It receives the payload for inspection (logging, metrics, debugging)
but never modifies it. Think of it as a pressure gauge on a pipe.
"""

from typing import Protocol, TypeVar
from .payload import Payload

__all__ = ["Tap"]

T = TypeVar('T')


class Tap(Protocol[T]):
    """
    Non-modifying observation point — inspect the payload without changing it.

    Use Taps for logging, metrics, debugging, and auditing.
    The pipeline calls observe() and discards the return value.
    """

    async def observe(self, payload: Payload[T]) -> None:
        """Observe the payload. Must not modify it."""
        ...
