# codeupipe

Python pipeline framework — composable Payload-Filter-Pipeline pattern with streaming support.

Experimental successor to [codeuchain](https://github.com/codeuchain/codeuchain) (Python only).

## Core Concepts

| Concept | Role |
|---|---|
| **Payload** | Immutable data container flowing through the pipeline |
| **MutablePayload** | Mutable sibling for performance-critical bulk edits |
| **Filter** | Processing unit — takes a Payload in, returns a transformed Payload out (sync or async) |
| **StreamFilter** | Streaming processing unit — receives one chunk, yields 0, 1, or N output chunks |
| **Pipeline** | Orchestrator — `.run()` for batch, `.stream()` for streaming |
| **Valve** | Conditional flow control — gates a Filter with a predicate |
| **Tap** | Non-modifying observation point — inspect without changing (sync or async) |
| **State** | Pipeline execution metadata — tracks what ran, what was skipped, errors, chunk counts |
| **Hook** | Lifecycle hooks — before/after/on_error for pipeline execution (sync or async) |
| **RetryFilter** | Resilience wrapper — retries a Filter up to N times before giving up |

## Install

```bash
pip install -e .
```

## Quick Start

```python
import asyncio
from codeupipe import Payload, Pipeline

# Filters can be sync or async — both work
class CleanInput:
    def call(self, payload):
        return payload.insert("text", payload.get("text", "").strip())

class Validate:
    def call(self, payload):
        if not payload.get("text"):
            raise ValueError("Empty input")
        return payload

# Build and run
pipeline = Pipeline()
pipeline.add_filter(CleanInput(), name="clean")
pipeline.add_filter(Validate(), name="validate")

result = asyncio.run(pipeline.run(Payload({"text": "  hello  "})))
print(result.get("text"))  # "hello"
```

## Valve (Conditional Flow)

```python
from codeupipe import Valve

class DiscountFilter:
    def call(self, payload):
        price = payload.get("price", 0)
        return payload.insert("price", price * 0.9)

# Only applies when predicate returns True
pipeline.add_filter(
    Valve("discount", DiscountFilter(), lambda p: p.get("tier") == "premium"),
    name="discount",
)
```

## Tap (Observation)

```python
class AuditTap:
    async def observe(self, payload):
        print(f"Payload at this point: {payload.to_dict()}")

pipeline.add_tap(AuditTap(), name="audit")
```

## Streaming

Process an async stream of chunks through the same pipeline at constant memory.

```python
from codeupipe import Payload, Pipeline

class UppercaseFilter:
    def call(self, payload):
        return payload.insert("name", payload.get("name", "").upper())

async def names():
    for n in ["alice", "bob", "charlie"]:
        yield Payload({"name": n})

async def main():
    pipeline = Pipeline()
    pipeline.add_filter(UppercaseFilter(), name="upper")

    async for result in pipeline.stream(names()):
        print(result.get("name"))  # ALICE, BOB, CHARLIE

asyncio.run(main())
```

Use `StreamFilter` to drop, fan-out, or batch:

```python
from typing import AsyncIterator

class DropEmpty:
    async def stream(self, chunk: Payload) -> AsyncIterator[Payload]:
        if chunk.get("line", "").strip():
            yield chunk

class SplitWords:
    async def stream(self, chunk: Payload) -> AsyncIterator[Payload]:
        for word in chunk.get("text", "").split():
            yield Payload({"word": word})
```

## Execution State

```python
result = await pipeline.run(payload)
print(pipeline.state.executed)           # ['clean', 'validate']
print(pipeline.state.skipped)            # ['admin_only']
print(pipeline.state.chunks_processed)   # {'upper': 3}  (streaming mode)
```

## Docs

See [CONCEPTS.md](CONCEPTS.md) for comprehensive examples and API reference for every type, verified by `tests/test_docs_examples.py`.

## Test

```bash
pytest
```

## License

Apache 2.0
