# codeupipe — Concepts & Examples

A practical reference for every type in the framework. Each section shows the class signature, its contract, and runnable examples verified by `tests/test_docs_examples.py`.

---

## Table of Contents

1. [Mental Model](#mental-model)
2. [Payload](#payload)
3. [MutablePayload](#mutablepayload)
4. [Filter](#filter)
5. [Pipeline](#pipeline)
6. [Valve](#valve)
7. [Tap](#tap)
8. [State](#state)
9. [Hook](#hook)
10. [RetryFilter](#retryfilter)
11. [StreamFilter & Streaming](#streamfilter--streaming)
12. [Complete Workflow](#complete-workflow)
13. [Quick Reference](#quick-reference)

---

## Mental Model

```
Payload ──► [ Filter ] ──► [ Valve ] ──► [ Filter ] ──► Payload
                │                │
               Tap              Tap
              (observe)       (observe)

Pipeline controls sequencing.
State records what happened.
Hooks attach lifecycle behaviour.
```

<!-- cup:ref file=codeupipe/core/__init__.py hash=6ed16dd -->
| Concept | Role |
|---|---|
| `Payload` | The data box moving through the pipe — immutable |
| `MutablePayload` | Same box, temporarily unlocked for in-place editing |
| `Filter` | A processing station — receives a Payload, returns a new one |
| `Pipeline` | The pipe itself — sequences filters and taps |
| `Valve` | A conditional gate — runs an inner Filter only when a predicate passes |
| `Tap` | A pressure gauge — reads the Payload without modifying it |
| `State` | An execution log — records which filters ran, were skipped, or errored |
| `Hook` | Lifecycle callbacks — `before`, `after`, `on_error` for every filter call |
| `RetryFilter` | A resilience wrapper — retries a Filter up to N times before giving up |
| `StreamFilter` | A streaming station — receives one chunk, yields 0, 1, or N output chunks |
<!-- /cup:ref -->

---

## Payload

<!-- cup:ref file=codeupipe/core/payload.py symbols=Payload hash=87e463d -->

**Immutable data container.** Every operation returns a fresh copy.

```python
from codeupipe import Payload

# --- Construction ---
p = Payload({"user_id": 42, "role": "admin"})

# --- Read ---
p.get("user_id")          # 42
p.get("missing", "n/a")   # "n/a"

# --- Write (returns new Payload, original unchanged) ---
p2 = p.insert("verified", True)
p.get("verified")    # None  — original untouched
p2.get("verified")   # True

# --- Merge two payloads (other wins on conflict) ---
base = Payload({"x": 1, "y": 2})
override = Payload({"y": 99, "z": 3})
merged = base.merge(override)
merged.get("x")   # 1
merged.get("y")   # 99  — override won
merged.get("z")   # 3

# --- Export ---
merged.to_dict()   # {"x": 1, "y": 99, "z": 3}

# --- Upgrade to mutable for bulk edits ---
mut = p.with_mutation()   # → MutablePayload
```

**Key contract:** `insert()` and `merge()` never mutate `self`. They always return a new `Payload`.

<!-- /cup:ref -->

---

## MutablePayload

<!-- cup:ref file=codeupipe/core/payload.py symbols=MutablePayload hash=87e463d -->

**Mutable sibling of Payload** — use inside a Filter when raw performance matters or when multiple keys need updating in one pass.

```python
from codeupipe import Payload, MutablePayload

# --- Create directly ---
m = MutablePayload({"count": 0})

# --- Edit in place ---
m.set("count", 1)
m.set("flag", True)

# --- Read ---
m.get("count")   # 1

# --- Freeze back to immutable when done ---
p = m.to_immutable()   # → Payload

# --- Common pattern inside a Filter ---
async def normalize(payload):
    m = payload.with_mutation()   # Payload → MutablePayload
    m.set("name", payload.get("name", "").strip().lower())
    m.set("normalized", True)
    return m.to_immutable()       # MutablePayload → Payload
```

<!-- /cup:ref -->

---

## Filter

<!-- cup:ref file=codeupipe/core/filter.py symbols=Filter hash=1800d12 -->

**A `Protocol` — any class with `call(payload) -> payload` qualifies.** Both `async def` and plain `def` work.

```python
import asyncio
from codeupipe import Payload, Filter

# --- Minimal implementation ---
class UppercaseFilter:
    async def call(self, payload: Payload) -> Payload:
        name = payload.get("name", "")
        return payload.insert("name", name.upper())

# --- Run standalone ---
async def main():
    f = UppercaseFilter()
    result = await f.call(Payload({"name": "alice"}))
    print(result.get("name"))   # ALICE

asyncio.run(main())
```

```python
# --- Validation filter (raises to halt the pipeline) ---
class RequireEmailFilter:
    async def call(self, payload: Payload) -> Payload:
        email = payload.get("email", "")
        if "@" not in email:
            raise ValueError(f"Invalid email: {email!r}")
        return payload.insert("email_valid", True)
```

```python
# --- Transformation filter using MutablePayload ---
class NormalizeFilter:
    async def call(self, payload: Payload) -> Payload:
        m = payload.with_mutation()
        m.set("name",  payload.get("name", "").strip().lower())
        m.set("email", payload.get("email", "").strip().lower())
        return m.to_immutable()
```

**Contract:**
- `def call(self, payload: Payload) -> Payload` (sync) or `async def call(...)` (async). Both work.
- Raise an exception to signal failure — the Pipeline propagates it.
- Return the received payload (or a new one) to continue.

<!-- /cup:ref -->

---

## Pipeline

<!-- cup:ref file=codeupipe/core/pipeline.py symbols=Pipeline hash=e846926 -->

**The orchestrator — sequences filters, taps, and valves.**

```python
import asyncio
from codeupipe import Payload, Pipeline

class DoubleFilter:
    async def call(self, payload: Payload) -> Payload:
        return payload.insert("value", payload.get("value", 0) * 2)

class AddTenFilter:
    async def call(self, payload: Payload) -> Payload:
        return payload.insert("value", payload.get("value", 0) + 10)

async def main():
    pipeline = Pipeline()
    pipeline.add_filter(DoubleFilter(), name="double")
    pipeline.add_filter(AddTenFilter(), name="add_ten")

    result = await pipeline.run(Payload({"value": 5}))
    print(result.get("value"))   # (5 * 2) + 10 = 20

asyncio.run(main())
```

**API:**

| Method | Purpose |
|---|---|
| `pipeline.add_filter(filter, name=None)` | Append a Filter (or Valve) to the sequence |
| `pipeline.add_tap(tap, name=None)` | Insert an observation point |
| `pipeline.add_parallel(filters, name, names=None)` | Fan-out: run filters concurrently, merge results |
| `pipeline.add_pipeline(pipeline, name)` | Nest a Pipeline as a single step |
| `pipeline.use_hook(hook)` | Attach a lifecycle Hook |
| `await pipeline.run(payload)` | Execute batch mode — return the final Payload |
| `pipeline.run_sync(payload)` | Synchronous convenience — no manual `asyncio.run()` |
| `async for chunk in pipeline.stream(source)` | Execute stream mode — yield chunks at constant memory |
| `pipeline.with_retry(max_retries=3)` | Return a wrapper that retries the whole pipeline on failure |
| `pipeline.with_circuit_breaker(failure_threshold=5)` | Return a wrapper that opens after N consecutive failures |
| `pipeline.state` | Access execution metadata after `run()` or `stream()` |
| `Pipeline.from_config(path, registry=)` | Build a pipeline from a `.toml` or `.json` config file |

**Config-driven assembly** — all step types and resilience wrappers are expressible in JSON/TOML:

```json
{
  "pipeline": {
    "name": "example",
    "retry": { "max_retries": 3 },
    "circuit_breaker": { "failure_threshold": 5 },
    "steps": [
      { "name": "CleanInput", "type": "filter" },
      {
        "name": "fan-out",
        "type": "parallel",
        "filters": [
          { "name": "FetchA" },
          { "name": "FetchB", "config": { "timeout": 30 } }
        ]
      },
      {
        "name": "validation-sub",
        "type": "pipeline",
        "steps": [
          { "name": "Validate", "type": "filter" },
          { "name": "AuditTap", "type": "tap" }
        ]
      }
    ]
  }
}
```

<!-- /cup:ref -->

---

## Valve

<!-- cup:ref file=codeupipe/core/valve.py symbols=Valve hash=faf6427 -->

**Conditional gate — runs an inner Filter only when a predicate returns `True`.**

```python
import asyncio
from codeupipe import Payload, Pipeline, Valve

class DiscountFilter:
    async def call(self, payload: Payload) -> Payload:
        total = payload.get("total", 0)
        return payload.insert("total", total * 0.9)   # 10% off

def is_premium(payload: Payload) -> bool:
    return payload.get("tier") == "premium"

async def main():
    discount_valve = Valve(
        name="premium_discount",
        inner=DiscountFilter(),
        predicate=is_premium,
    )

    pipeline = Pipeline()
    pipeline.add_filter(discount_valve, name="premium_discount")

    # Premium user — discount applied
    premium = await pipeline.run(Payload({"tier": "premium", "total": 100}))
    print(premium.get("total"))   # 90.0

    # Standard user — passes through unchanged
    standard = await pipeline.run(Payload({"tier": "standard", "total": 100}))
    print(standard.get("total"))   # 100

asyncio.run(main())
```

**How it works:**

1. `Valve.call(payload)` evaluates `predicate(payload)`.
2. If `True` → delegates to `inner.call(payload)` and returns the result.
3. If `False` → returns `payload` unchanged (same object reference).
4. Pipeline detects the unchanged reference and records the valve as **skipped** in `State`.

**Valve conforms to the Filter protocol** — add it with `pipeline.add_filter(valve)`.

<!-- /cup:ref -->

---

## Tap

<!-- cup:ref file=codeupipe/core/tap.py symbols=Tap hash=c344078 -->

**A `Protocol` — any class with `async observe(payload) -> None` qualifies.**

```python
import asyncio
from codeupipe import Payload, Pipeline, Tap

class PrintTap:
    async def observe(self, payload: Payload) -> None:
        print(f"[tap] payload = {payload.to_dict()}")

class MetricsTap:
    def __init__(self):
        self.snapshots = []

    async def observe(self, payload: Payload) -> None:
        self.snapshots.append(payload.to_dict().copy())

async def main():
    metrics = MetricsTap()

    pipeline = Pipeline()
    pipeline.add_tap(PrintTap(), name="print")
    pipeline.add_tap(metrics, name="metrics")

    await pipeline.run(Payload({"x": 1}))
    print(metrics.snapshots)   # [{"x": 1}]

asyncio.run(main())
```

**Contract:**
- `observe()` must **not** modify the payload — it receives it for reading only.
- The pipeline discards the return value, so `return None` is always correct.
- Taps appear between filters in the sequence — place them where you need the snapshot.

<!-- /cup:ref -->

---

## State

<!-- cup:ref file=codeupipe/core/state.py symbols=State hash=c713e64 -->

**Execution metadata — read after `pipeline.run()`.**

```python
import asyncio
from codeupipe import Payload, Pipeline, Valve

class StepA:
    async def call(self, payload: Payload) -> Payload:
        return payload.insert("a", True)

class StepB:
    async def call(self, payload: Payload) -> Payload:
        return payload.insert("b", True)

async def main():
    always_false = Valve(
        name="gated_b",
        inner=StepB(),
        predicate=lambda p: False,   # never runs
    )

    pipeline = Pipeline()
    pipeline.add_filter(StepA(), name="step_a")
    pipeline.add_filter(always_false, name="gated_b")

    await pipeline.run(Payload({}))

    state = pipeline.state
    print(state.executed)    # ["step_a"]
    print(state.skipped)     # ["gated_b"]
    print(state.has_errors)  # False

asyncio.run(main())
```

**State API:**

| Member | Type | Description |
|---|---|---|
| `state.executed` | `List[str]` | Filter/tap names that ran |
| `state.skipped` | `List[str]` | Valve names where predicate was False |
| `state.errors` | `List[Tuple[str, Exception]]` | `(name, exception)` pairs |
| `state.has_errors` | `bool` | True if any errors recorded |
| `state.last_error` | `Exception \| None` | Most recent exception |
| `state.chunks_processed` | `Dict[str, int]` | Per-step chunk counts (streaming mode) |
| `state.metadata` | `Dict[str, Any]` | Arbitrary key-value store |
| `state.mark_executed(name)` | — | Record a filter as executed |
| `state.mark_skipped(name)` | — | Record a filter as skipped |
| `state.increment_chunks(name)` | — | Increment chunk counter for a step |
| `state.set(key, val)` | — | Write custom metadata |
| `state.get(key, default)` | `Any` | Read custom metadata |
| `state.reset()` | — | Clear everything for a fresh run |

<!-- /cup:ref -->

---

## Hook

<!-- cup:ref file=codeupipe/core/hook.py symbols=Hook hash=86339f4 -->

**Lifecycle callbacks — subclass `Hook` and override the methods you need.**

```python
import asyncio
from codeupipe import Payload, Pipeline, Hook

class LoggingHook(Hook):
    def __init__(self):
        self.log = []

    async def before(self, filter, payload: Payload) -> None:
        name = filter.__class__.__name__ if filter else "pipeline"
        self.log.append(f"before:{name}")

    async def after(self, filter, payload: Payload) -> None:
        name = filter.__class__.__name__ if filter else "pipeline"
        self.log.append(f"after:{name}")

    async def on_error(self, filter, error: Exception, payload: Payload) -> None:
        name = filter.__class__.__name__ if filter else "pipeline"
        self.log.append(f"error:{name}:{error}")

class SquareFilter:
    async def call(self, payload: Payload) -> Payload:
        return payload.insert("n", payload.get("n", 0) ** 2)

async def main():
    hook = LoggingHook()

    pipeline = Pipeline()
    pipeline.use_hook(hook)
    pipeline.add_filter(SquareFilter(), name="square")

    await pipeline.run(Payload({"n": 4}))
    print(hook.log)
    # ["before:pipeline", "before:SquareFilter", "after:SquareFilter", "after:pipeline"]

asyncio.run(main())
```

**Hook method signatures:**

```python
class Hook(ABC):
    async def before(self, filter, payload: Payload) -> None: ...
    async def after(self, filter, payload: Payload) -> None: ...
    async def on_error(self, filter, error: Exception, payload: Payload) -> None: ...
```

- `filter` is `None` when called for the pipeline as a whole (start/end/pipeline-level error).
- `filter` is the Filter instance when called per-filter.
- All three methods have no-op defaults — only override what you need.

<!-- /cup:ref -->

---

## RetryFilter

<!-- cup:ref file=codeupipe/utils/error_handling.py symbols=RetryFilter hash=dc0f5ec -->

**Resilience wrapper — retries a failing Filter up to `max_retries` times.**

> **Note:** `RetryFilter` *swallows* exceptions on exhaustion — it returns the payload with an `"error"` key rather than re-raising. The pipeline continues normally after a `RetryFilter`. If you need the pipeline to halt on failure, do not wrap the filter in `RetryFilter`, or check the `"error"` key in the next filter.

```python
import asyncio
from codeupipe import Payload
from codeupipe import RetryFilter

attempt_count = 0

class FlakyFilter:
    async def call(self, payload: Payload) -> Payload:
        global attempt_count
        attempt_count += 1
        if attempt_count < 3:
            raise ConnectionError("not ready")
        return payload.insert("connected", True)

async def main():
    flaky = FlakyFilter()
    resilient = RetryFilter(flaky, max_retries=3)

    result = await resilient.call(Payload({}))
    print(result.get("connected"))   # True  (succeeded on attempt 3)

asyncio.run(main())
```

```python
# --- When retries are exhausted ---
class AlwaysFailsFilter:
    async def call(self, payload: Payload) -> Payload:
        raise RuntimeError("down")

async def main():
    resilient = RetryFilter(AlwaysFailsFilter(), max_retries=2)
    result = await resilient.call(Payload({}))
    print(result.get("error"))   # "Max retries: down"

asyncio.run(main())
```

**API:** `RetryFilter(inner_filter, max_retries=3)`

- If the inner filter succeeds on any attempt, that result is returned.
- If all retries are exhausted, a fresh Payload is returned with `"error"` set to `"Max retries: <message>"`.

<!-- /cup:ref -->

---

## StreamFilter & Streaming

<!-- cup:ref file=codeupipe/core/stream_filter.py symbols=StreamFilter hash=66b4374 -->

**Stream mode** lets you process an async stream of Payload chunks through the pipeline at constant memory — one chunk at a time, with built-in backpressure.

### Batch vs Stream

| | `pipeline.run(payload)` | `pipeline.stream(source)` |
|---|---|---|
| Input | One Payload | AsyncIterable of Payloads |
| Output | One Payload | AsyncIterator of Payloads |
| Memory | Entire dataset at once | One chunk at a time |
| Filter protocol | `call(payload) -> payload` | Same — auto-adapted |
| StreamFilter protocol | N/A | `stream(chunk) -> yield 0..N` |

### Regular Filters work automatically

Every existing Filter (sync or async) is auto-adapted in stream mode — one chunk in, one chunk out.

```python
import asyncio
from codeupipe import Payload, Pipeline

class UppercaseFilter:
    def call(self, payload: Payload) -> Payload:
        return payload.insert("name", payload.get("name", "").upper())

async def source():
    for name in ["alice", "bob", "charlie"]:
        yield Payload({"name": name})

async def main():
    pipeline = Pipeline()
    pipeline.add_filter(UppercaseFilter(), name="upper")

    async for result in pipeline.stream(source()):
        print(result.get("name"))   # ALICE, BOB, CHARLIE

asyncio.run(main())
```

### StreamFilter — drop, map, or fan-out

A `StreamFilter` is a `Protocol` with `async def stream(chunk) -> AsyncIterator[Payload]`. Yield nothing to drop, one to map, or many to fan-out.

```python
import asyncio
from typing import AsyncIterator
from codeupipe import Payload, Pipeline

# --- Drop: yield nothing to filter out chunks ---
class DropEmpty:
    async def stream(self, chunk: Payload) -> AsyncIterator[Payload]:
        if chunk.get("line", "").strip():
            yield chunk

# --- Fan-out: yield multiple chunks from one input ---
class SplitWords:
    async def stream(self, chunk: Payload) -> AsyncIterator[Payload]:
        for word in chunk.get("text", "").split():
            yield Payload({"word": word})

async def lines():
    for line in ["hello world", "", "foo bar baz"]:
        yield Payload({"text": line, "line": line})

async def main():
    pipeline = Pipeline()
    pipeline.add_filter(DropEmpty(), name="drop_empty")
    pipeline.add_filter(SplitWords(), name="split")

    async for result in pipeline.stream(lines()):
        print(result.get("word"))
    # hello, world, foo, bar, baz

asyncio.run(main())
```

### Valves gate per-chunk

In stream mode, the Valve predicate runs on each chunk independently:

```python
import asyncio
from codeupipe import Payload, Pipeline, Valve

class DiscountFilter:
    def call(self, payload: Payload) -> Payload:
        return payload.insert("price", payload.get("price", 0) * 0.9)

valve = Valve(
    name="vip_discount",
    inner=DiscountFilter(),
    predicate=lambda p: p.get("vip") is True,
)

async def orders():
    yield Payload({"vip": True,  "price": 100})   # discounted → 90
    yield Payload({"vip": False, "price": 200})   # full price → 200
    yield Payload({"vip": True,  "price": 50})    # discounted → 45

async def main():
    pipeline = Pipeline()
    pipeline.add_filter(valve, name="vip_discount")

    async for result in pipeline.stream(orders()):
        print(result.get("price"))

asyncio.run(main())
```

### Taps observe each chunk

```python
class CounterTap:
    def __init__(self):
        self.count = 0

    async def observe(self, payload: Payload) -> None:
        self.count += 1
```

### Hooks fire once per filter (not per chunk)

In stream mode, `hook.before(filter)` fires once when the stream enters a filter, and `hook.after(filter)` fires once when the stream exits. This avoids per-chunk hook overhead.

### State tracks chunks

After streaming, `pipeline.state.chunks_processed` is a `Dict[str, int]` counting how many chunks each step emitted:

```python
async def main():
    pipeline = Pipeline()
    pipeline.add_filter(UppercaseFilter(), name="upper")
    pipeline.add_filter(SplitWords(), name="split")

    results = []
    async for r in pipeline.stream(source()):
        results.append(r)

    print(pipeline.state.chunks_processed)
    # {"upper": 3, "split": 5}  — 3 chunks through upper, 5 words out of split
```

<!-- /cup:ref -->

---

## Complete Workflow

A realistic order-processing pipeline using every concept together.

```python
import asyncio
from codeupipe import Payload, Pipeline, Valve, Hook, RetryFilter

# --- Filters ---

class ValidateOrderFilter:
    async def call(self, payload: Payload) -> Payload:
        qty = payload.get("quantity", 0)
        if qty <= 0:
            raise ValueError("quantity must be positive")
        return payload.insert("valid", True)

class ApplyDiscountFilter:
    async def call(self, payload: Payload) -> Payload:
        price = payload.get("price", 0.0)
        return payload.insert("price", round(price * 0.85, 2))   # 15% off

class ChargeFilter:
    async def call(self, payload: Payload) -> Payload:
        price = payload.get("price", 0.0)
        qty   = payload.get("quantity", 0)
        return payload.insert("charged", round(price * qty, 2))

# --- Tap ---

class AuditTap:
    def __init__(self):
        self.snapshots = []

    async def observe(self, payload: Payload) -> None:
        self.snapshots.append(payload.to_dict())

# --- Hook ---

class TimingHook(Hook):
    def __init__(self):
        self.calls = []

    async def before(self, filter, payload: Payload) -> None:
        if filter:
            self.calls.append(f"start:{filter.__class__.__name__}")

    async def after(self, filter, payload: Payload) -> None:
        if filter:
            self.calls.append(f"end:{filter.__class__.__name__}")

# --- Assemble ---

async def process_order(order: dict) -> Payload:
    audit   = AuditTap()
    timing  = TimingHook()

    is_bulk = lambda p: p.get("quantity", 0) >= 10

    pipeline = Pipeline()
    pipeline.use_hook(timing)
    pipeline.add_filter(RetryFilter(ValidateOrderFilter(), max_retries=1), name="validate")
    pipeline.add_tap(audit, name="after_validate")
    pipeline.add_filter(
        Valve("bulk_discount", ApplyDiscountFilter(), predicate=is_bulk),
        name="bulk_discount",
    )
    pipeline.add_filter(ChargeFilter(), name="charge")

    result = await pipeline.run(Payload(order))

    state = pipeline.state
    print("executed:", state.executed)
    print("skipped: ", state.skipped)
    print("snapshots:", len(audit.snapshots))

    return result

# --- Run ---
async def main():
    bulk_order = {"quantity": 20, "price": 50.0}
    result = await process_order(bulk_order)
    print("charged:", result.get("charged"))   # 20 * (50 * 0.85) = 850.0

asyncio.run(main())
```

---

## Quick Reference

<!-- cup:ref file=codeupipe/__init__.py hash=3053319 -->
```python
from codeupipe import (
    Payload,           # immutable data container
    MutablePayload,    # mutable data container
    Filter,            # Protocol — async/sync call(payload) -> payload
    StreamFilter,      # Protocol — async stream(chunk) -> yield payloads
    Pipeline,          # orchestrator — .run() for batch, .stream() for streaming
    Valve,             # conditional gate
    Tap,               # Protocol — async/sync observe(payload) -> None
    State,             # execution metadata (read via pipeline.state)
    Hook,              # ABC — before / after / on_error
    RetryFilter,       # resilience wrapper
    Registry,          # name → component catalog
    cup_component,     # decorator — register a class as a CUP component
    default_registry,  # module-level singleton Registry
)
```
<!-- /cup:ref -->
