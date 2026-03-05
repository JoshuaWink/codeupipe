"""
Streaming Example: Word Count Pipeline

Demonstrates streaming mode — processing chunks at constant memory.
Uses a StreamFilter for fan-out (splitting lines into words)
and a regular Filter for transformation (uppercasing).
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import asyncio
from typing import AsyncIterator
from codeupipe import Payload, Pipeline


# --- Source: async generator simulating a file read ---

async def read_lines():
    """Simulate reading lines from a large file, one at a time."""
    lines = [
        "the quick brown fox",
        "jumps over the lazy dog",
        "hello world",
    ]
    for line in lines:
        yield Payload({"line": line})


# --- StreamFilter: fan-out (1 line → N words) ---

class SplitWords:
    """Split each line into individual word chunks."""

    async def stream(self, chunk: Payload) -> AsyncIterator[Payload]:
        line = chunk.get("line", "")
        for word in line.split():
            yield Payload({"word": word})


# --- Regular Filter: transform each word (auto-adapted for streaming) ---

class UppercaseFilter:
    """Uppercase each word — sync filter, works in stream mode too."""

    def call(self, payload: Payload) -> Payload:
        return payload.insert("word", payload.get("word", "").upper())


# --- Run ---

async def main():
    pipeline = Pipeline()
    pipeline.add_filter(SplitWords(), name="split")
    pipeline.add_filter(UppercaseFilter(), name="uppercase")

    words = []
    async for result in pipeline.stream(read_lines()):
        words.append(result.get("word"))

    print("Words:", words)
    print("Chunks processed:", pipeline.state.chunks_processed)
    # split: 9 words emitted, uppercase: 9 words transformed


if __name__ == "__main__":
    asyncio.run(main())
