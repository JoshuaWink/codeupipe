# codeupipe

Python pipeline framework — composable Payload-Filter-Pipeline pattern.

Experimental successor to [codeuchain](https://github.com/codeuchain/codeuchain) (Python only).

## Core Concepts

| Concept | Role |
|---|---|
| **Payload** | Immutable data container flowing through the pipeline |
| **Filter** | Processing unit — takes a Payload in, returns a transformed Payload out |
| **Pipeline** | Orchestrator — runs Filters in sequence with lifecycle hooks |
| **Valve** | Conditional flow control — gates a Filter with a predicate |
| **Tap** | Non-modifying observation point — inspect without changing |
| **State** | Pipeline execution metadata — tracks what ran, what was skipped, errors |
| **Hook** | Lifecycle hooks — before/after/on_error for pipeline execution |

## Install

```bash
pip install -e .
```

## Quick Start

```python
from codeupipe import Payload, Filter, Pipeline, Valve

# Define filters
class CleanInput(Filter):
    async def call(self, payload):
        return payload.insert("text", payload.get("text").strip())

class Validate(Filter):
    async def call(self, payload):
        if not payload.get("text"):
            raise ValueError("Empty input")
        return payload

# Build a pipeline
pipeline = Pipeline()
pipeline.add_filter(CleanInput(), "clean")
pipeline.add_filter(Validate(), "validate")

import asyncio
result = asyncio.run(pipeline.run(Payload({"text": "  hello  "})))
print(result.get("text"))  # "hello"
```

## Valve (Conditional Flow)

```python
from codeupipe import Valve

# Only run DiscountFilter if customer is premium
pipeline.add_filter(
    Valve("discount", DiscountFilter(), lambda p: p.get("tier") == "premium"),
    "discount"
)
```

## Tap (Observation)

```python
class AuditTap:
    async def observe(self, payload):
        print(f"Payload at this point: {payload.to_dict()}")

pipeline.add_tap(AuditTap(), "audit")
```

## Execution State

```python
result = await pipeline.run(payload)
print(pipeline.state.executed)  # ['clean', 'validate', 'discount']
print(pipeline.state.skipped)   # ['admin_only']
```

## Test

```bash
pytest
```

## License

Apache 2.0
