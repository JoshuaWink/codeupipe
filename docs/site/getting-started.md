# Getting Started

Get from zero to a working pipeline in minutes.

## Install

```bash
pip install codeupipe
```

Or for development:

```bash
git clone https://github.com/codeuchain/codeupipe.git
cd codeupipe
pip install -e '.[dev]'
```

## Your First Pipeline

```python
import asyncio
from codeupipe import Payload, Pipeline

# Filters — sync or async, both work
class CleanInput:
    def call(self, payload):
        return payload.insert("text", payload.get("text", "").strip())

class Validate:
    def call(self, payload):
        if not payload.get("text"):
            raise ValueError("Empty input")
        return payload

# Build
pipeline = Pipeline()
pipeline.add_filter(CleanInput(), name="clean")
pipeline.add_filter(Validate(), name="validate")

# Run
result = asyncio.run(pipeline.run(Payload({"text": "  hello  "})))
print(result.get("text"))  # "hello"
```

Or use synchronous execution — no `asyncio.run()` needed:

```python
result = pipeline.run_sync(Payload({"text": "  hello  "}))
```

## Add Conditional Flow (Valve)

```python
from codeupipe import Valve

class DiscountFilter:
    def call(self, payload):
        price = payload.get("price", 0)
        return payload.insert("price", price * 0.9)

# Only runs when predicate is True
pipeline.add_filter(
    Valve("discount", DiscountFilter(), lambda p: p.get("tier") == "premium"),
    name="discount",
)
```

## Observe Without Modifying (Tap)

```python
class AuditTap:
    async def observe(self, payload):
        print(f"Payload: {payload.to_dict()}")

pipeline.add_tap(AuditTap(), name="audit")
```

## Streaming

Process an async stream at constant memory:

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

## Parallel Execution (Fan-out / Fan-in)

Run independent filters concurrently:

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

```python
# Retry up to 3 times on failure
retrying = pipeline.with_retry(max_retries=3)
result = retrying.run_sync(Payload({"input": "data"}))

# Circuit breaker — open after 5 consecutive failures
from codeupipe import CircuitOpenError

breaker = pipeline.with_circuit_breaker(failure_threshold=5)
try:
    result = breaker.run_sync(Payload({"input": "data"}))
except CircuitOpenError:
    print("Service unavailable — circuit is open")
```

## CLI (`cup`)

Scaffold, lint, and manage your project:

```bash
cup new filter validate_email src/signup       # Scaffold filter + test
cup new pipeline signup src/signup --steps validate_email hash_password
cup list                                       # Available component types
cup lint src/signup                            # Convention checks
cup coverage src/signup                        # Component ↔ test coverage
cup report src/signup                          # Health report with scores
cup doc-check .                                # Verify doc freshness
```

## Testing

```python
from codeupipe.testing import run_filter, assert_payload, mock_filter

def test_my_filter():
    result = run_filter(MyFilter(), {"input": "data"})
    assert_payload(result, output="expected")
```

```bash
pytest  # 1382 tests
```

## Next Steps

- [Concepts & API Reference](concepts.md) — every type, every method
- [Best Practices](best-practices.md) — project structure, naming, testing
- [Deploy Guide](deploy-guide.md) — Docker, Render, Vercel, Netlify
