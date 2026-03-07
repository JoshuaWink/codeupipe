# codeupipe — Agent Skill Reference

> **Repository:** [github.com/codeuchain/codeupipe](https://github.com/codeuchain/codeupipe)
> **Branch:** `main`
> **Language:** Python 3.9+
> **Dependencies:** Zero — pure stdlib
> **Tests:** 909 passing (`pytest`)
> **License:** Apache 2.0

---

## What Is codeupipe?

A composable **Payload → Filter → Pipeline** framework for Python. Data flows through immutable Payloads, is transformed by Filters, and orchestrated by Pipelines — with Valves for conditional flow, Taps for observation, Hooks for lifecycle events, and StreamFilters for constant-memory streaming.

Experimental successor to [codeuchain](https://github.com/codeuchain/codeuchain) (Python package).

---

## Architecture Overview

<!-- cup:ref file=codeupipe/__init__.py hash=791f774 -->
```
Payload (data)
   │
   ▼
Pipeline.run(payload)  ──or──  Pipeline.run_sync(payload)  ──or──  Pipeline.stream(async_iter)
   │
   ├─ Hook.before()
   │
   ├─ Filter.call(payload) → payload     ← sync or async
   │   └─ Valve wraps a Filter + predicate
   │
   ├─ add_parallel([filters]) → fan-out/fan-in via asyncio.gather
   │
   ├─ add_pipeline(inner) → nested Pipeline as a single step
   │
   ├─ StreamFilter.stream(chunk) → yields 0..N chunks
   │
   ├─ Tap.observe(payload)               ← sync or async, read-only
   │
   ├─ Hook.after()
   │
   ├─ Hook.on_error()  (on exception)
   │
   ├─ with_retry(max_retries) → pipeline-level retry wrapper
   │
   └─ with_circuit_breaker(threshold) → opens after N consecutive failures
```
<!-- /cup:ref -->

---

## Project Structure

<!-- cup:ref file=codeupipe/__init__.py hash=791f774 -->

```
codeupipe/
├── __init__.py              # Public API — all exports
├── py.typed                 # PEP 561 marker
├── registry.py              # Registry, cup_component, default_registry
├── core/
│   ├── __init__.py          # Re-exports core types
│   ├── payload.py           # Payload[T], MutablePayload[T]
│   ├── filter.py            # Filter Protocol
│   ├── stream_filter.py     # StreamFilter Protocol
│   ├── pipeline.py          # Pipeline orchestrator (.run, .stream)
│   ├── valve.py             # Valve — conditional filter gating
│   ├── tap.py               # Tap Protocol — observation
│   ├── state.py             # State — execution metadata
│   └── hook.py              # Hook ABC — lifecycle hooks
├── converter/
│   ├── __init__.py          # Exports: load_config, DEFAULT_CONFIG, PATTERN_DEFAULTS
│   ├── config.py            # Config parsing, 4 pattern defaults (mvc/clean/hexagonal/flat)
│   ├── filters/
│   │   ├── __init__.py
│   │   ├── parse_config.py      # ParseConfigFilter — reads .cup.json or pattern defaults
│   │   ├── analyze.py           # AnalyzePipelineFilter — introspects Pipeline steps
│   │   ├── classify.py          # ClassifyStepsFilter — maps steps to roles via fnmatch
│   │   ├── classify_files.py    # ClassifyFilesFilter — maps files by directory to roles
│   │   ├── generate_export.py   # GenerateExportFilter — CUP → standard Python
│   │   ├── scan_project.py      # ScanProjectFilter — walks directory tree
│   │   └── generate_import.py   # GenerateImportFilter — standard Python → CUP
│   ├── taps/
│   │   ├── __init__.py
│   │   └── conversion_log.py    # ConversionLogTap — logs conversion progress
│   └── pipelines/
│       ├── __init__.py          # Exports: build_export_pipeline, build_import_pipeline
│       ├── export_pipeline.py   # CUP → Standard pipeline
│       └── import_pipeline.py   # Standard → CUP pipeline
├── linter/
│   ├── __init__.py          # 24 exports across lint, coverage, report, and doc-check pipelines
│   ├── scan_directory.py    # ScanDirectory — walks directory tree
│   ├── check_naming.py      # CheckNaming — CUP007 snake_case enforcement
│   ├── check_structure.py   # CheckStructure — CUP001 one-per-file
│   ├── check_protocols.py   # CheckProtocols — CUP003-006 method checks
│   ├── check_tests.py       # CheckTests — CUP002 test file pairing
│   ├── check_bundle.py      # CheckBundle — CUP008 stale __init__.py
│   ├── lint_pipeline.py     # build_lint_pipeline()
│   ├── scan_components.py   # ScanComponents — component discovery
│   ├── scan_tests.py        # ScanTests — test file discovery
│   ├── map_coverage.py      # MapCoverage — component↔test mapping
│   ├── report_gaps.py       # ReportGaps — missing test detection
│   ├── coverage_pipeline.py # build_coverage_pipeline()
│   ├── detect_orphans.py    # DetectOrphans — orphaned file detection
│   ├── git_history.py       # GitHistory — git blame/commit data
│   ├── assemble_report.py   # AssembleReport — health score generation
│   ├── report_pipeline.py   # build_report_pipeline()
│   ├── scan_docs.py         # ScanDocs — extract cup:ref markers from .md files
│   ├── resolve_refs.py      # ResolveRefs — resolve file paths in markers
│   ├── check_symbols.py     # CheckSymbols — verify symbols exist in source
│   ├── detect_drift.py      # DetectDrift — hash comparison for staleness
│   ├── assemble_doc_report.py  # AssembleDocReport — build doc-check report
│   └── doc_check_pipeline.py   # build_doc_check_pipeline()
├── testing.py               # Test utilities — run_filter, assert_payload, mock_filter, etc.
├── cli.py                   # CLI entry point — cup new/list/bundle/lint/coverage/report/doc-check/run
├── utils/
│   ├── __init__.py
│   └── error_handling.py    # ErrorHandlingMixin, RetryFilter
tests/
├── conftest.py              # Shared fixtures (pytest-asyncio strict mode)
├── test_payload.py          # 13 tests
├── test_filter.py           # 11 tests
├── test_pipeline.py         # 12 tests
├── test_valve.py            # 5 tests
├── test_tap.py              # 4 tests
├── test_state.py            # 7 tests
├── test_hook.py             # 7 tests
├── test_error_handling.py   # 11 tests
├── test_typed.py            # 10 tests
├── test_docs_examples.py    # 37 tests (verifies CONCEPTS.md examples)
├── test_streaming.py        # 18 tests
├── test_sync_support.py     # 9 tests
├── test_core_edge_cases.py  # 31 tests — core framework edge cases
├── test_mixed_stream_pipeline.py  # 8 tests — sync+async+stream coexistence
├── test_stream_filter_run_protection.py  # 8 tests — StreamFilter on .run() guard
├── test_unintended_usage.py # 68 tests — misuse and boundary conditions
├── test_real_world_pipelines.py  # 36 tests — realistic multi-stage demos
├── test_cli.py              # 210 tests — CLI scaffolding, bundle, lint, coverage, report
├── test_scan_directory.py   # 20 tests — ScanDirectory filter
├── test_check_naming.py     # 8 tests — CheckNaming filter
├── test_check_structure.py  # 8 tests — CheckStructure filter
├── test_check_protocols.py  # 14 tests — CheckProtocols filter
├── test_check_tests.py      # 8 tests — CheckTests filter
├── test_check_bundle.py     # 7 tests — CheckBundle filter
├── test_lint_pipeline.py    # 12 tests — lint pipeline integration
├── test_scan_components.py  # 14 tests — ScanComponents filter
├── test_scan_tests.py       # 11 tests — ScanTests filter
├── test_map_coverage.py     # 9 tests — MapCoverage filter
├── test_report_gaps.py      # 7 tests — ReportGaps filter
├── test_coverage_pipeline.py  # 8 tests — coverage pipeline integration
├── test_detect_orphans.py   # 11 tests — DetectOrphans filter
├── test_git_history.py      # 7 tests — GitHistory filter
├── test_assemble_report.py  # 11 tests — AssembleReport filter
├── test_report_pipeline.py  # 7 tests — report pipeline integration
├── test_scan_docs.py        # 8 tests — ScanDocs filter
├── test_resolve_refs.py     # 6 tests — ResolveRefs filter
├── test_check_symbols.py    # 6 tests — CheckSymbols filter
├── test_detect_drift.py     # 6 tests — DetectDrift filter
├── test_assemble_doc_report.py  # 6 tests — AssembleDocReport filter
├── test_doc_check_pipeline.py   # 9 tests — doc-check pipeline + CLI integration
├── test_testing.py          # 33 tests — testing wrapper utilities
└── converter/
    ├── __init__.py
    ├── test_unit.py         # 36 tests — config, all 7 filters, log tap
    ├── test_integration.py  # 12 tests — export & import pipeline integration
    ├── test_integration_edge.py  # 16 tests — edge cases for full pipelines
    ├── test_e2e.py          # 11 tests — round-trip: MVC, Clean, Hexagonal, Flat
    ├── test_edge_cases.py   # 75 tests — boundary conditions, tricky inputs
    └── test_workflows.py    # 18 tests — real-world ETL, auth, validation workflows
examples/
├── simple_math.py
├── typed_example.py
├── context_default_demo.py
├── typed_vs_untyped_comparison.py
├── typed_workflow_patterns.py
└── components/              # Organized filter/hook/tap/pipeline files
INDEX.md                     # Project structure map (verified by cup doc-check)
CONCEPTS.md                  # Full API reference with runnable examples
BEST_PRACTICES.md            # Project structure, naming, testing guidance
README.md                    # Quick-start guide
```
<!-- /cup:ref -->

---

## Core Types — Quick Reference

<!-- cup:ref file=codeupipe/core/__init__.py hash=bd391f6 -->
| Type | Kind | Purpose |
|---|---|---|
| `Payload[T]` | Class | Immutable data container. `.get()`, `.insert()`, `.merge()`, `.to_dict()`, `.with_mutation()` |
| `MutablePayload[T]` | Class | Mutable sibling. `.get()`, `.set()`, `.to_immutable()` |
| `Filter[TInput, TOutput]` | Protocol | Processing unit. Implement `.call(payload) → Payload` (sync or async) |
| `StreamFilter[TInput, TOutput]` | Protocol | Streaming unit. Implement `async def stream(chunk) → AsyncIterator[Payload]` |
| `Pipeline[TInput, TOutput]` | Class | Orchestrator. `.add_filter()`, `.add_tap()`, `.use_hook()`, `.run()`, `.stream()` |
| `Valve[TInput, TOutput]` | Class | Conditional gate. Wraps a Filter + predicate. Conforms to Filter protocol. |
| `Tap[T]` | Protocol | Read-only observer. Implement `.observe(payload) → None` (sync or async) |
| `State` | Class | Execution metadata. `.executed`, `.skipped`, `.errors`, `.metadata`, `.chunks_processed` |
| `Hook` | ABC | Lifecycle hooks. Override `.before()`, `.after()`, `.on_error()` (sync or async) |
| `RetryFilter` | Class | Resilience wrapper. Retries an inner Filter up to N times. |
| `ErrorHandlingMixin` | Mixin | Error routing for pipelines. `.on_error(source, handler, condition)` |
| `load_config` | Function | Parse `.cup.json` or apply pattern defaults (`mvc`, `clean`, `hexagonal`, `flat`). |
| `build_export_pipeline` | Function | Returns a Pipeline that converts CUP → standard Python (with pattern layout). |
| `build_import_pipeline` | Function | Returns a Pipeline that converts standard Python → CUP. |
| `build_lint_pipeline` | Function | Returns a Pipeline that checks CUP conventions (CUP000–CUP008). |
| `build_coverage_pipeline` | Function | Returns a Pipeline that maps component↔test coverage gaps. |
| `build_report_pipeline` | Function | Returns a Pipeline that generates project health reports. |
| `build_doc_check_pipeline` | Function | Returns a Pipeline that verifies doc freshness (cup:ref markers). |
<!-- /cup:ref -->

### Testing Utilities (`from codeupipe.testing import ...`)

<!-- cup:ref file=codeupipe/testing.py symbols=run_filter,run_pipeline,assert_payload,assert_keys,assert_state,mock_filter hash=c119f9c -->

| Export | Kind | Purpose |
|---|---|---|
| `run_filter` | Function | Run a single filter with dict or Payload — handles sync/async transparently. |
| `run_pipeline` | Function | Run a pipeline, optionally returning `(result, state)`. |
| `assert_pipeline_streaming` | Function | Run pipeline in streaming mode, collect output chunks for assertion. |
| `assert_payload` | Function | Assert payload contains expected key=value pairs. |
| `assert_keys` | Function | Assert payload contains specified keys. |
| `assert_state` | Function | Assert pipeline state after execution. |
| `mock_filter` | Function | Create a mock filter that inserts predefined data and records calls. |
| `mock_tap` | Function | Create a recording tap for testing. |
| `mock_hook` | Function | Create a recording hook for testing. |
| `cup_component` | Function | Scaffold a CUP component file on disk for analysis tests. |
| `RecordingTap` | Class | Tap that records every payload it observes. |
| `RecordingHook` | Class | Hook that records all lifecycle events. |
<!-- /cup:ref -->

---

## Import

```python
from codeupipe import (
    Payload, MutablePayload,
    Filter, StreamFilter,
    Pipeline, Valve, Tap,
    State, Hook,
    ErrorHandlingMixin, RetryFilter,
    # Converter
    load_config, build_export_pipeline, build_import_pipeline,
)

# Linter / Analysis pipelines
from codeupipe.linter import (
    build_lint_pipeline, build_coverage_pipeline, build_report_pipeline,
    build_doc_check_pipeline,
)

# Testing utilities
from codeupipe.testing import (
    run_filter, run_pipeline, assert_pipeline_streaming,
    assert_payload, assert_keys, assert_state,
    mock_filter, mock_tap, mock_hook,
    cup_component, RecordingTap, RecordingHook,
)
```

---

## How to Write a Filter

Filters are structural (Protocol-based) — no base class needed. Just implement `.call()`.

### Sync Filter

```python
class Trim:
    def call(self, payload):
        return payload.insert("text", payload.get("text", "").strip())
```

### Async Filter

```python
class FetchUser:
    async def call(self, payload):
        user = await db.get_user(payload.get("user_id"))
        return payload.insert("user", user)
```

### Generic Typed Filter

```python
from typing import TypedDict

class RawInput(TypedDict):
    text: str

class CleanOutput(TypedDict):
    text: str
    length: int

class CleanAndMeasure:
    def call(self, payload: Payload[RawInput]) -> Payload[CleanOutput]:
        text = payload.get("text", "").strip()
        return payload.insert("text", text).insert("length", len(text))
```

---

## How to Write a StreamFilter

Yield-based interface for streaming. Yield nothing to drop, one to map, many to fan-out.

```python
from typing import AsyncIterator

class SplitWords:
    async def stream(self, chunk: Payload) -> AsyncIterator[Payload]:
        for word in chunk.get("text", "").split():
            yield Payload({"word": word})

class DropEmpty:
    async def stream(self, chunk: Payload) -> AsyncIterator[Payload]:
        if chunk.get("line", "").strip():
            yield chunk
        # yield nothing → chunk is dropped
```

---

## How to Build and Run a Pipeline

### Batch Mode

```python
import asyncio

pipeline = Pipeline()
pipeline.add_filter(Trim(), name="trim")
pipeline.add_filter(Validate(), name="validate")
pipeline.add_tap(LogTap(), name="log")
pipeline.use_hook(TimingHook())

result = asyncio.run(pipeline.run(Payload({"text": "  hello  "})))
print(result.get("text"))         # "hello"
print(pipeline.state.executed)    # ["trim", "validate", "log"]
```

### Streaming Mode

```python
async def lines():
    for line in open("data.txt"):
        yield Payload({"line": line})

pipeline = Pipeline()
pipeline.add_filter(SplitWords(), name="split")  # StreamFilter
pipeline.add_filter(Uppercase(), name="upper")    # Regular Filter (auto-adapted)

async for chunk in pipeline.stream(lines()):
    print(chunk.get("word"))

print(pipeline.state.chunks_processed)  # {"split": N, "upper": M}
```

---

## How to Use Valves

```python
class PremiumDiscount:
    def call(self, payload):
        price = payload.get("price", 0)
        return payload.insert("price", price * 0.9)

pipeline.add_filter(
    Valve("discount", PremiumDiscount(), lambda p: p.get("tier") == "premium"),
    name="discount",
)
# Skipped payloads pass through unchanged; state.skipped tracks them.
```

---

## How to Use Taps

```python
class AuditTap:
    def observe(self, payload):  # sync or async
        print(f"Observed: {payload.to_dict()}")

pipeline.add_tap(AuditTap(), name="audit")
```

---

## How to Use Hooks

```python
class TimingHook(Hook):
    def __init__(self):
        self.start = None

    async def before(self, filter, payload):
        import time
        self.start = time.time()

    async def after(self, filter, payload):
        import time
        if self.start:
            elapsed = time.time() - self.start
            print(f"Step took {elapsed:.3f}s")

    async def on_error(self, filter, error, payload):
        print(f"Error: {error}")
```

- `filter=None` → pipeline-level event (start/end)
- `filter=<instance>` → per-filter event

---

## How to Use RetryFilter

```python
class FlakyService:
    async def call(self, payload):
        # might fail intermittently
        ...

resilient = RetryFilter(FlakyService(), max_retries=3)
pipeline.add_filter(resilient, name="flaky_call")
# On exhaustion, returns payload with "error" key — does NOT raise
```

**Important:** `RetryFilter` swallows exceptions after all retries are exhausted. It returns `payload.insert("error", f"Max retries: {e}")` instead of raising. The pipeline continues with the error-annotated payload.

---

## How to Use Payload and MutablePayload

```python
# Immutable — every mutation returns a NEW Payload
p = Payload({"name": "alice", "score": 10})
p2 = p.insert("score", 20)        # p unchanged, p2 has score=20
p3 = p.merge(Payload({"bonus": 5}))  # combines both

# Mutable — for performance-critical bulk edits
mp = p.with_mutation()
mp.set("score", 99)
mp.set("rank", 1)
safe = mp.to_immutable()           # back to immutable when done
```

---

## State After Execution

```python
result = await pipeline.run(payload)

pipeline.state.executed           # ['trim', 'validate', 'log']
pipeline.state.skipped            # ['admin_only']  (valve-skipped)
pipeline.state.errors             # [(name, exception), ...]
pipeline.state.has_errors         # bool
pipeline.state.last_error         # Exception or None
pipeline.state.metadata           # dict — arbitrary via state.set(k, v)
pipeline.state.chunks_processed   # {'split': 42, 'upper': 42}  (streaming)
pipeline.state.reset()            # clear everything for a fresh run
```

---

## Conventions & Best Practices

1. **Filters in their own files.** One filter per file under a `filters/` directory. Same for taps, hooks, chains/pipelines.
2. **Sync by default.** Use async only when doing I/O. The framework handles both transparently.
3. **Payloads are immutable.** Use `.insert()` to create new payloads. Only use `MutablePayload` when you have a measurable performance concern.
4. **Name everything.** Always pass `name=` to `.add_filter()` and `.add_tap()`. State tracking depends on it.
5. **StreamFilter for streaming, Filter for batch.** Regular Filters are auto-adapted in `.stream()` mode (1→1). Use StreamFilter only when you need drop/fan-out/batch.
6. **Check state after runs.** Use `pipeline.state` to verify execution, catch skips, and debug issues.
7. **RetryFilter swallows.** It does not re-raise — it annotates the payload with an `"error"` key. Check for it downstream.

---

## Testing

```bash
# Run all 909 tests
pytest

# Run with verbose output
pytest -v

# Run a specific test file
pytest tests/test_streaming.py

# Run tests matching a keyword
pytest -k "valve"
```

Test configuration lives in `pyproject.toml` — `asyncio_mode = strict`, test paths under `tests/`.

### Test Structure

| File | Count | Covers |
|---|---|---|
| `test_payload.py` | 13 | Payload/MutablePayload immutability, generics |
| `test_filter.py` | 11 | Filter protocol compliance |
| `test_pipeline.py` | 12 | Pipeline batch execution, ordering |
| `test_valve.py` | 5 | Valve conditional gating |
| `test_tap.py` | 4 | Tap observation without modification |
| `test_state.py` | 7 | State tracking and metadata |
| `test_hook.py` | 7 | Hook lifecycle (before/after/on_error) |
| `test_error_handling.py` | 11 | ErrorHandlingMixin, RetryFilter |
| `test_typed.py` | 10 | Generic typing, TypedDict workflows |
| `test_docs_examples.py` | 37 | Every runnable example from CONCEPTS.md |
| `test_streaming.py` | 18 | StreamFilter, Pipeline.stream(), streaming state |
| `test_sync_support.py` | 9 | Sync filters, taps, hooks, valves |
| `test_core_edge_cases.py` | 31 | Core framework edge cases |
| `test_mixed_stream_pipeline.py` | 8 | Sync+async+stream filter coexistence |
| `test_stream_filter_run_protection.py` | 8 | StreamFilter on .run() guard |
| `test_unintended_usage.py` | 68 | Misuse patterns and boundary conditions |
| `test_real_world_pipelines.py` | 36 | Realistic multi-stage pipeline demos |
| `test_cli.py` | 210 | CLI scaffolding, bundle, lint, coverage, report |
| `test_scan_directory.py` | 20 | ScanDirectory filter |
| `test_check_naming.py` | 8 | CheckNaming filter |
| `test_check_structure.py` | 8 | CheckStructure filter |
| `test_check_protocols.py` | 14 | CheckProtocols filter |
| `test_check_tests.py` | 8 | CheckTests filter |
| `test_check_bundle.py` | 7 | CheckBundle filter |
| `test_lint_pipeline.py` | 12 | Lint pipeline integration |
| `test_scan_components.py` | 14 | ScanComponents filter |
| `test_scan_tests.py` | 11 | ScanTests filter |
| `test_map_coverage.py` | 9 | MapCoverage filter |
| `test_report_gaps.py` | 7 | ReportGaps filter |
| `test_coverage_pipeline.py` | 8 | Coverage pipeline integration |
| `test_detect_orphans.py` | 11 | DetectOrphans filter |
| `test_git_history.py` | 7 | GitHistory filter |
| `test_assemble_report.py` | 11 | AssembleReport filter |
| `test_report_pipeline.py` | 7 | Report pipeline integration |
| `test_scan_docs.py` | 8 | ScanDocs doc-check filter |
| `test_resolve_refs.py` | 6 | ResolveRefs doc-check filter |
| `test_check_symbols.py` | 6 | CheckSymbols doc-check filter |
| `test_detect_drift.py` | 6 | DetectDrift doc-check filter |
| `test_assemble_doc_report.py` | 6 | AssembleDocReport doc-check filter |
| `test_doc_check_pipeline.py` | 9 | Doc-check pipeline + CLI integration |
| `test_testing.py` | 33 | Testing wrapper utilities |
| converter/`test_unit.py` | 36 | Config, all 7 converter filters, log tap |
| converter/`test_integration.py` | 12 | Export & import pipeline integration |
| converter/`test_integration_edge.py` | 16 | Edge cases for full pipelines |
| converter/`test_e2e.py` | 11 | Round-trip: MVC, Clean, Hexagonal, Flat |
| converter/`test_edge_cases.py` | 75 | Boundary conditions, tricky inputs |
| converter/`test_workflows.py` | 18 | Real-world ETL, auth, validation workflows |

---

## Key Design Decisions

- **Protocol over ABC for Filter/Tap/StreamFilter.** Structural subtyping — no need to inherit. Just implement the method.
- **ABC for Hook.** Nominal subtyping — must inherit from `Hook`. Provides default no-op implementations for all three methods.
- **`inspect.isawaitable()` bridge.** All internal dispatch uses this check. Sync callables work without wrapping; async callables are awaited. This is in `Pipeline._invoke()` and `Valve.call()`.
- **Async generators for streaming.** `Pipeline.stream()` chains steps as nested async generators. Backpressure is natural — each step only pulls the next chunk when yielded to.
- **Immutable-first data flow.** `Payload.insert()` returns a new `Payload`. No side effects in the data layer. `MutablePayload` is opt-in for performance.
- **Zero dependencies.** Uses only `typing`, `abc`, `inspect`, `asyncio` from stdlib.

---

## Common Patterns

### Error-annotated pipeline (RetryFilter + downstream check)

```python
pipeline = Pipeline()
pipeline.add_filter(RetryFilter(FlakyAPI(), max_retries=2), name="api_call")
pipeline.add_filter(CheckError(), name="check")

class CheckError:
    def call(self, payload):
        if payload.get("error"):
            return payload.insert("status", "failed")
        return payload.insert("status", "ok")
```

### Fan-out streaming (one input → many outputs)

```python
class Tokenize:
    async def stream(self, chunk):
        for token in chunk.get("text", "").split():
            yield Payload({"token": token})

async for result in pipeline.stream(source):
    process(result.get("token"))
```

### Valve chains (multi-condition branching)

```python
pipeline.add_filter(Valve("admin", AdminFilter(), lambda p: p.get("role") == "admin"), name="admin")
pipeline.add_filter(Valve("user", UserFilter(), lambda p: p.get("role") == "user"), name="user")
# Only the matching valve executes; others pass through
```

### MutablePayload bulk edit

```python
class BulkEnrich:
    def call(self, payload):
        mp = payload.with_mutation()
        mp.set("enriched", True)
        mp.set("timestamp", time.time())
        mp.set("version", 2)
        return mp.to_immutable()
```

---

## Bidirectional Conversion: Standard Python ↔ CUP

CUP's protocol layer maps 1:1 to standard Python constructs. Code can be mechanically converted in either direction.

### The Mapping

| CUP | Standard Python Equivalent |
|---|---|
| `Payload(data)` | `dict` / dataclass / TypedDict / Pydantic model |
| `payload.get(k)` | `data.get(k)` or `data[k]` |
| `payload.insert(k, v)` | `{**data, k: v}` (immutable) or `data[k] = v` (mutable) |
| `Filter.call(payload) → payload` | `def fn(data: dict) → dict` — a pure function |
| `Pipeline.run(payload)` | `functools.reduce(lambda d, f: f(d), fns, data)` |
| `Valve(name, filter, pred)` | `if pred(data): data = fn(data)` |
| `Tap.observe(payload)` | `print(data)` / `logger.info(data)` between steps |
| `Hook.before/after/on_error` | `contextlib.contextmanager` or try/except wrapping |
| `StreamFilter.stream(chunk) → yields` | `async def gen(data: dict) → AsyncIterator[dict]` |
| `Pipeline.stream(source)` | Chained async generators |
| `RetryFilter(inner, N)` | `tenacity.retry(stop=stop_after_attempt(N))` or manual loop |
| `State` | Manual tracking dict + logging — **has no standard equivalent** |

### What CUP Adds Over Standard Code

State tracking (executed/skipped/errors/chunks), immutability guarantees, named steps, lifecycle hooks, streaming with backpressure, retry resilience. **Converting CUP → standard loses all observability unless you manually replicate it.**

---

### Standard → CUP (Wrapping Existing Code)

Use the function signature as the guide:

**Pure function → Filter**

```python
# STANDARD
def clean(data: dict) -> dict:
    data["text"] = data["text"].strip()
    return data

# CUP — wrap the logic, keep immutability
class CleanFilter:
    def call(self, payload):
        return payload.insert("text", payload.get("text", "").strip())
```

Or adapt without rewriting — wrap the function directly:

```python
def adapt_function(fn):
    """Wrap a dict→dict function as a CUP Filter."""
    class _Adapted:
        def call(self, payload):
            result = fn(payload.to_dict())
            return Payload(result)
    _Adapted.__name__ = fn.__name__
    return _Adapted()

# Use it
pipeline.add_filter(adapt_function(clean), name="clean")
```

**Side-effect function → Tap**

```python
# STANDARD
def log_step(data: dict) -> None:
    print(f"Processing: {data}")

# CUP
class LogTap:
    def observe(self, payload):
        print(f"Processing: {payload.to_dict()}")

# Or adapt directly
def adapt_tap(fn):
    """Wrap a dict→None function as a CUP Tap."""
    class _Adapted:
        def observe(self, payload):
            fn(payload.to_dict())
    return _Adapted()
```

**Predicate + function → Valve**

```python
# STANDARD
if user["role"] == "admin":
    data = admin_process(data)

# CUP
pipeline.add_filter(
    Valve("admin", AdminFilter(), lambda p: p.get("role") == "admin"),
    name="admin",
)
```

**Async generator → StreamFilter**

```python
# STANDARD
async def tokenize(text: str):
    for word in text.split():
        yield word

# CUP
class TokenizeFilter:
    async def stream(self, chunk):
        for word in chunk.get("text", "").split():
            yield Payload({"word": word})

# Or adapt
def adapt_stream(fn):
    """Wrap an async generator function as a CUP StreamFilter."""
    class _Adapted:
        async def stream(self, chunk):
            async for item in fn(chunk.to_dict()):
                yield Payload(item) if isinstance(item, dict) else Payload({"value": item})
    return _Adapted()
```

**Sequential calls → Pipeline**

```python
# STANDARD
data = clean(data)
data = validate(data)
data = enrich(data)
if data.get("premium"):
    data = apply_discount(data)
log(data)
result = save(data)

# CUP — direct translation
pipeline = Pipeline()
pipeline.add_filter(adapt_function(clean), name="clean")
pipeline.add_filter(adapt_function(validate), name="validate")
pipeline.add_filter(adapt_function(enrich), name="enrich")
pipeline.add_filter(
    Valve("discount", adapt_function(apply_discount), lambda p: p.get("premium")),
    name="discount",
)
pipeline.add_tap(adapt_tap(log), name="log")
pipeline.add_filter(adapt_function(save), name="save")
result = await pipeline.run(Payload(data))
# Now you get: state.executed, state.skipped, hooks, streaming — free.
```

**Try/except/retry → RetryFilter**

```python
# STANDARD
for attempt in range(3):
    try:
        result = flaky_api(data)
        break
    except Exception:
        if attempt == 2:
            raise

# CUP
pipeline.add_filter(RetryFilter(FlakyFilter(), max_retries=3), name="flaky")
```

---

### CUP → Standard (Unwrapping to Plain Python)

Extract the business logic from CUP's structure:

**Filter → function**

```python
# CUP
class CleanFilter:
    def call(self, payload):
        return payload.insert("text", payload.get("text", "").strip())

# STANDARD — extract the logic
def clean(data: dict) -> dict:
    data = dict(data)  # copy for safety
    data["text"] = data.get("text", "").strip()
    return data
```

Or unwrap mechanically:

```python
def unwrap_filter(filter_instance):
    """Convert a CUP Filter to a plain dict→dict function."""
    import asyncio, inspect
    def fn(data: dict) -> dict:
        payload = Payload(data)
        result = filter_instance.call(payload)
        if inspect.isawaitable(result):
            result = asyncio.run(result)
        return result.to_dict()
    return fn

# Use it
clean_fn = unwrap_filter(CleanFilter())
result = clean_fn({"text": "  hello  "})  # {"text": "hello"}
```

**Pipeline → composed function**

```python
def unwrap_pipeline(pipeline):
    """Convert a CUP Pipeline to a single dict→dict function."""
    import asyncio
    def fn(data: dict) -> dict:
        result = asyncio.run(pipeline.run(Payload(data)))
        return result.to_dict()
    return fn

# Use it
process = unwrap_pipeline(pipeline)
result = process({"text": "  hello  ", "tier": "premium"})
```

**Valve → inline conditional**

```python
# CUP
Valve("discount", DiscountFilter(), lambda p: p.get("tier") == "premium")

# STANDARD
if data.get("tier") == "premium":
    data = discount(data)
```

**StreamFilter → async generator**

```python
# CUP
class SplitWords:
    async def stream(self, chunk):
        for word in chunk.get("text", "").split():
            yield Payload({"word": word})

# STANDARD
async def split_words(data: dict):
    for word in data.get("text", "").split():
        yield {"word": word}
```

---

### Recognition Patterns for Agents

When converting existing code to CUP, look for these standard patterns:

| Standard Pattern | CUP Equivalent |
|---|---|
| Sequential `data = fn(data)` calls | Pipeline with Filters |
| `if condition: data = fn(data)` | Valve |
| `print(data)` / `logger.info()` between steps | Tap |
| `try: ... except: retry` loop | RetryFilter |
| `for item in stream: process(item)` | Pipeline.stream() with Filters |
| Generator that yields subsets | StreamFilter (fan-out) |
| Generator that skips items | StreamFilter (drop) |
| `@contextmanager` wrapping steps | Hook |
| Dictionary passed through functions | Payload |
| Mutable dict accumulating fields | MutablePayload → `.to_immutable()` |

When decomposing CUP back to standard code:

1. Read each `add_filter` / `add_tap` in order — that's the sequence of function calls
2. Valves become `if` statements
3. Hooks become try/except or context managers wrapping the sequence
4. RetryFilter becomes a retry loop around one step
5. State tracking disappears — add logging if needed
6. Streaming becomes a `for` loop with generators

---

### The Conversion Is Asymmetric

**Standard → CUP** is always a net gain: you get state tracking, named steps, lifecycle hooks, immutability, streaming, and retry — for free.

**CUP → Standard** preserves business logic but loses observability. Only do this when:
- Debugging — flatten to see raw data flow
- Environments that can't take the dependency
- Explaining CUP code to someone unfamiliar with the framework

---

## Pattern-Targeted Conversion

When converting between CUP and standard code, a **conversion config** specifies the target architecture pattern. Instead of just flattening to functions or wrapping as Filters, the conversion sorts code into the right structural slots for a given pattern.

### Why This Works

A CUP Pipeline is a flat manifest of named, typed steps. Each filter has a name, a role (filter/tap/valve/hook), and a position in the sequence. That metadata is enough to sort into any layered pattern — you just need a mapping from **step name/tag → architectural slot**.

### The Config File

Place a `.cup.yaml` at the project root (or a `[tool.cup]` section in `pyproject.toml`):

```yaml
# .cup.yaml — conversion configuration
pattern: mvc              # mvc | clean | hexagonal | flat | custom

# Map filter names/prefixes to architectural roles
roles:
  model:
    - fetch_*             # Filters that touch persistence
    - save_*
    - db_*
  view:
    - format_*            # Filters that shape output
    - render_*
    - serialize_*
  controller:
    - validate_*          # Filters that orchestrate/validate
    - authorize_*
    - route_*
  middleware:
    - _tap                # All Taps → middleware
    - _hook               # All Hooks → middleware
    - _valve              # All Valves → middleware (guards)

# Output structure when converting CUP → standard
output:
  base: src/
  # Pattern-specific directories
  mvc:
    model: models/
    view: views/
    controller: controllers/
    middleware: middleware/
```

### Supported Patterns

#### MVC (Model-View-Controller)

```
src/
├── models/               ← Filters that read/write data
│   ├── fetch_user.py
│   └── save_order.py
├── views/                ← Filters that format responses
│   ├── format_receipt.py
│   └── render_email.py
├── controllers/          ← Orchestration + validation
│   ├── validate_input.py
│   └── order_pipeline.py   ← The Pipeline itself
└── middleware/            ← Taps, Hooks, Valves
    ├── auth_guard.py        ← Valve
    ├── audit_logger.py      ← Tap
    └── timing_hook.py       ← Hook
```

CUP role mapping:

| CUP Type | MVC Slot | Why |
|---|---|---|
| Filter (I/O, persistence) | Model | Reads/writes external state |
| Filter (transform, format) | View | Shapes data for output |
| Filter (validation, auth) | Controller | Enforces rules |
| Pipeline | Controller | Orchestrates the sequence |
| Valve | Middleware | Guards/routes control flow |
| Tap | Middleware | Cross-cutting observation |
| Hook | Middleware | Lifecycle concerns |

#### Clean Architecture

```
src/
├── entities/             ← Payload types / TypedDicts / dataclasses
│   └── order.py
├── use_cases/            ← Core business Filters
│   ├── calculate_total.py
│   └── apply_discount.py
├── interface_adapters/   ← I/O Filters, Valves, Taps
│   ├── fetch_order.py
│   ├── save_order.py
│   └── auth_guard.py
├── frameworks/           ← Hooks, external integrations
│   └── timing_hook.py
└── main.py               ← Pipeline composition
```

| CUP Type | Clean Slot | Why |
|---|---|---|
| Payload / TypedDict | Entity | Core data structures |
| Filter (pure logic) | Use Case | Business rules, no I/O |
| Filter (I/O) | Interface Adapter | Crosses the boundary |
| Valve | Interface Adapter | Policy enforcement at boundary |
| Tap | Interface Adapter | Observation is a boundary concern |
| Hook | Framework | Infrastructure lifecycle |
| Pipeline | Main / Composition Root | Wires everything together |

#### Hexagonal (Ports & Adapters)

```
src/
├── domain/               ← Pure business Filters + Payload types
│   ├── calculate_total.py
│   └── order_types.py
├── ports/                ← Protocol definitions (Filter/Tap/Hook interfaces)
│   ├── order_repository.py
│   └── notification_service.py
├── adapters/
│   ├── inbound/          ← Validation Filters, pipeline entry
│   │   └── validate_order.py
│   └── outbound/         ← I/O Filters, external calls
│       ├── postgres_order_repo.py
│       └── email_notifier.py
└── app.py                ← Pipeline composition
```

| CUP Type | Hexagonal Slot | Why |
|---|---|---|
| Filter (pure) | Domain | Core logic, no dependencies |
| Filter protocol | Port | Interface contract |
| Filter (I/O) | Adapter (outbound) | Implements a port |
| Filter (validation) | Adapter (inbound) | Accepts input |
| Valve | Adapter (inbound) | Guards at the boundary |
| Pipeline | Application Service | Orchestration |

#### Flat (Default)

No structural reorganization. Each filter becomes a function in a single module or one file per function in a `steps/` directory.

```
steps/
├── clean.py
├── validate.py
├── fetch_user.py
├── format_response.py
└── pipeline.py
```

### How the Agent Uses the Config

**Standard → CUP:** Read existing project structure. If files are in `models/`, `views/`, `controllers/` — recognize MVC. Map each file to the appropriate CUP type:

```
models/user.py       → Filter (I/O)     → pipeline.add_filter(FetchUser(), name="fetch_user")
views/receipt.py     → Filter (format)   → pipeline.add_filter(FormatReceipt(), name="format_receipt")
controllers/app.py   → Pipeline          → the orchestrator itself
middleware/auth.py   → Valve             → Valve("auth", ..., predicate)
middleware/logger.py → Tap               → pipeline.add_tap(Logger(), name="logger")
```

**CUP → Standard:** Read `.cup.yaml`. Match each pipeline step name against the `roles` glob patterns. Place the extracted function in the corresponding directory:

```python
# Pipeline has these steps:
#   fetch_user      → matches fetch_* → model    → models/fetch_user.py
#   validate_input  → matches validate_* → controller → controllers/validate_input.py
#   format_receipt  → matches format_* → view     → views/format_receipt.py
#   auth_guard (Valve) → _valve → middleware → middleware/auth_guard.py
```

### Example: Full Round-Trip

**1. Start with CUP pipeline:**

```python
pipeline = Pipeline()
pipeline.add_filter(FetchOrder(), name="fetch_order")
pipeline.add_filter(
    Valve("premium_check", DiscountFilter(), lambda p: p.get("tier") == "premium"),
    name="premium_check",
)
pipeline.add_filter(CalcTotal(), name="calc_total")
pipeline.add_tap(AuditTap(), name="audit_tap")
pipeline.add_filter(FormatInvoice(), name="format_invoice")
pipeline.add_filter(SaveOrder(), name="save_order")
pipeline.use_hook(TimingHook())
```

**2. Convert to MVC (using `.cup.yaml` roles):**

```
src/
├── models/
│   ├── fetch_order.py          ← def fetch_order(data): ...
│   └── save_order.py           ← def save_order(data): ...
├── views/
│   └── format_invoice.py       ← def format_invoice(data): ...
├── controllers/
│   ├── calc_total.py           ← def calc_total(data): ...
│   └── order_controller.py     ← def process_order(data):
│                                    data = fetch_order(data)
│                                    if data.get("tier") == "premium":
│                                        data = apply_discount(data)
│                                    data = calc_total(data)
│                                    log_audit(data)
│                                    data = format_invoice(data)
│                                    data = save_order(data)
│                                    return data
└── middleware/
    ├── premium_check.py        ← predicate + discount logic
    ├── audit_logger.py         ← def log_audit(data): ...
    └── timing.py               ← context manager or decorator
```

**3. Convert back to CUP:** Agent reads the MVC structure, recognizes the pattern, and reconstitutes the Pipeline — gaining back state tracking, immutability, streaming, and hooks.

### Custom Patterns

Define your own in `.cup.yaml`:

```yaml
pattern: custom

roles:
  ingestion:
    - fetch_*
    - pull_*
    - read_*
  transformation:
    - clean_*
    - enrich_*
    - calc_*
    - merge_*
  validation:
    - validate_*
    - check_*
  output:
    - save_*
    - send_*
    - publish_*
    - format_*
  observability:
    - _tap
    - _hook
    - log_*

output:
  custom:
    ingestion: pipeline/ingestion/
    transformation: pipeline/transform/
    validation: pipeline/validation/
    output: pipeline/output/
    observability: pipeline/observability/
```

### pyproject.toml Alternative

```toml
[tool.cup]
pattern = "mvc"

[tool.cup.roles]
model = ["fetch_*", "save_*", "db_*"]
view = ["format_*", "render_*"]
controller = ["validate_*", "calc_*"]
middleware = ["_tap", "_hook", "_valve"]

[tool.cup.output]
base = "src/"

[tool.cup.output.mvc]
model = "models/"
view = "views/"
controller = "controllers/"
middleware = "middleware/"
```

---

## Converter Usage

The converter is itself built with CUP (dogfooding). Two pipelines handle each direction.

### Export: CUP → Standard Python

```python
import asyncio
from codeupipe import Payload, Pipeline, build_export_pipeline
from codeupipe.converter.taps import ConversionLogTap

# Build a sample CUP pipeline to export
class FetchUser:
    def call(self, payload):
        return payload.insert("user", {"id": payload.get("user_id")})

class ValidateUser:
    def call(self, payload):
        if not payload.get("user"):
            raise ValueError("No user")
        return payload

source_pipeline = Pipeline()
source_pipeline.add_filter("fetch_user", FetchUser())
source_pipeline.add_filter("validate_user", ValidateUser())

# Export to MVC structure
log_tap = ConversionLogTap()
export_pipe = build_export_pipeline(log_tap)

result = asyncio.run(export_pipe.run(
    Payload({"pipeline": source_pipeline, "pattern": "mvc"})
))

for f in result.get("files"):
    print(f["path"])
    # src/models/fetch_user.py
    # src/controllers/validate_user.py
    # src/controllers/pipeline.py  (orchestrator)
```

### Import: Standard Python → CUP

```python
import asyncio
from codeupipe import Payload, build_import_pipeline
from codeupipe.converter.taps import ConversionLogTap

log_tap = ConversionLogTap()
import_pipe = build_import_pipeline(log_tap)

result = asyncio.run(import_pipe.run(
    Payload({"project_path": "src/", "pattern": "mvc"})
))

for f in result.get("cup_files"):
    print(f["path"])
    # filters/fetch_user.py
    # filters/validate_user.py

print(result.get("cup_pipeline"))
# Pipeline composition code with all filters wired up
```

### Round-Trip Verification

Export a CUP pipeline to MVC, then import it back. The converter preserves step names, ordering, and role assignments across patterns.

### Supported Patterns

| Pattern | Roles | Directory Layout |
|---|---|---|
| `mvc` | model, view, controller, middleware | `models/`, `views/`, `controllers/`, `middleware/` |
| `clean` | entity, usecase, interface, infra | `entities/`, `usecases/`, `interfaces/`, `infra/` |
| `hexagonal` | domain, port, adapter, application | `domain/`, `ports/`, `adapters/`, `application/` |
| `flat` | logic, side_effect | `logic/`, `side_effects/` |

---

## Setup & Development

```bash
# Clone
git clone https://github.com/codeuchain/codeupipe.git
cd codeupipe

# Install editable (no external deps)
pip install -e .

# Run tests
pytest

# Run an example
python3 examples/streaming_demo.py
```

---

## Further Reading

- [CONCEPTS.md](CONCEPTS.md) — Full API reference with runnable, test-verified examples for every type
- [README.md](README.md) — Quick-start and overview
- [examples/](examples/) — Runnable demo scripts
- [codeuchain (parent project)](https://github.com/codeuchain/codeuchain) — The polyglot CodeUChain framework
