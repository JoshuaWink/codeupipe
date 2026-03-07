# codeupipe

<!-- cup:ref file=codeupipe/__init__.py hash=9b0673d -->

Python pipeline framework — composable **Payload → Filter → Pipeline** pattern with streaming support. Zero external dependencies.

Experimental successor to [codeuchain](https://github.com/codeuchain/codeuchain) (Python only).

<!-- /cup:ref -->

## Core Concepts

<!-- cup:ref file=codeupipe/core/__init__.py hash=bd391f6 -->
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
| **CircuitOpenError** | Raised when a pipeline circuit breaker is open and rejecting calls |
<!-- /cup:ref -->

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

## Synchronous Execution

No manual `asyncio.run()` needed — `run_sync()` handles it:

```python
pipeline = Pipeline()
pipeline.add_filter(CleanInput(), name="clean")
pipeline.add_filter(Validate(), name="validate")

result = pipeline.run_sync(Payload({"text": "  hello  "}))
print(result.get("text"))  # "hello"
```

## Parallel Execution (Fan-out / Fan-in)

Run independent filters concurrently; results merge back into the payload:

```python
pipeline = Pipeline()
pipeline.add_parallel([
    FetchUserFilter(),
    FetchOrdersFilter(),
    FetchRecommendationsFilter(),
], name="fan-out")

result = pipeline.run_sync(Payload({"user_id": 42}))
```

## Pipeline Nesting

Compose pipelines from smaller pipelines:

```python
validation = Pipeline()
validation.add_filter(CleanInput(), name="clean")
validation.add_filter(Validate(), name="validate")

processing = Pipeline()
processing.add_pipeline(validation, name="validation-sub")
processing.add_filter(TransformFilter(), name="transform")

result = processing.run_sync(Payload({"text": "  hello  "}))
```

## Retry & Circuit Breaker

Pipeline-level resilience wrappers:

```python
# Retry the entire pipeline up to 3 times on failure
retrying = pipeline.with_retry(max_retries=3)
result = retrying.run_sync(Payload({"input": "data"}))

# Open the circuit after 5 consecutive failures
from codeupipe import CircuitOpenError

breaker = pipeline.with_circuit_breaker(failure_threshold=5)
try:
    result = breaker.run_sync(Payload({"input": "data"}))
except CircuitOpenError:
    print("Service unavailable — circuit is open")
```

## Execution State

```python
result = await pipeline.run(payload)
print(pipeline.state.executed)           # ['clean', 'validate']
print(pipeline.state.skipped)            # ['admin_only']
print(pipeline.state.chunks_processed)   # {'upper': 3}  (streaming mode)
```

## Docs

| Document | Purpose |
|----------|---------|
| [INDEX.md](INDEX.md) | Project structure map (verified by `cup doc-check`) |
| [CONCEPTS.md](CONCEPTS.md) | Full API reference with runnable examples |
| [BEST_PRACTICES.md](BEST_PRACTICES.md) | Project structure, naming, testing strategy |
| [SKILL.md](SKILL.md) | Agent skill reference — types, patterns, conversion |
| [ROADMAP.md](ROADMAP.md) | Expansion rings — from framework to platform |

## CLI (`cup`)

<!-- cup:ref file=codeupipe/cli.py symbols=main,scaffold,bundle,lint,coverage,report,doc_check hash=12f4911 -->
The `cup` command-line tool scaffolds, lints, and analyzes CUP projects:

```bash
cup new filter validate_email src/signup   # Scaffold a filter + test
cup new pipeline signup src/signup --steps validate_email hash_password
cup list                                   # Show available component types
cup bundle src/signup                      # Generate __init__.py re-exports
cup lint src/signup                        # Check CUP conventions (CUP000–CUP008)
cup coverage src/signup                    # Map component↔test coverage gaps
cup report src/signup                      # Health report with scores, orphans, staleness
cup doc-check .                            # Verify doc freshness (cup:ref markers)
cup run pipeline.json --discover ./filters # Execute a pipeline from config
```
<!-- /cup:ref -->

## Testing Utilities

<!-- cup:ref file=codeupipe/testing.py symbols=run_filter,assert_payload,mock_filter hash=c119f9c -->
`codeupipe.testing` provides zero-boilerplate test helpers:

```python
from codeupipe.testing import run_filter, assert_payload, mock_filter

def test_my_filter():
    result = run_filter(MyFilter(), {"input": "data"})
    assert_payload(result, output="expected")

def test_with_mock():
    f = mock_filter(status="ok")
    result = run_filter(f, {"x": 1})
    assert f.call_count == 1
```
<!-- /cup:ref -->

## Test

```bash
pytest  # 1024 tests
```

## License

Apache 2.0
