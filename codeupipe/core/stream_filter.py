"""
StreamFilter Protocol: Chunk-at-a-Time Processing

A StreamFilter processes one Payload chunk and yields zero or more output chunks.
This enables filtering (drop), mapping (1→1), and fan-out (1→N) at constant memory.

Regular Filters are auto-adapted for streaming (1 chunk in → 1 chunk out).
StreamFilters opt in to the richer yield-based interface.
"""

from typing import AsyncIterator, Protocol, TypeVar
from .payload import Payload

__all__ = ["StreamFilter"]

TInput = TypeVar('TInput')
TOutput = TypeVar('TOutput')


class StreamFilter(Protocol[TInput, TOutput]):
    """
    Streaming processing unit — receives one chunk, yields zero or more output chunks.

    Use for:
    - Filtering: yield nothing to drop a chunk
    - Mapping: yield one transformed chunk (same as a regular Filter)
    - Fan-out: yield multiple chunks from one input
    - Batching/windowing: accumulate internally, yield when ready
    """

    async def stream(self, chunk: Payload[TInput]) -> AsyncIterator[Payload[TOutput]]:
        """Process a single chunk and yield output chunks."""
        ...
