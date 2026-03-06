# codeupipe — Index

Quick-reference map of the project. Every path listed here is verified by `cup doc-check`.

---

## Docs

| Document | Purpose |
|----------|---------|
| [README.md](README.md) | Quick-start, install, examples |
| [CONCEPTS.md](CONCEPTS.md) | Full API reference with runnable examples |
| [BEST_PRACTICES.md](BEST_PRACTICES.md) | Project structure, naming, testing strategy |
| [SKILL.md](SKILL.md) | Agent skill reference (types, patterns, conversion) |
| [INDEX.md](INDEX.md) | This file — project map |

---

## Package Structure

<!-- cup:ref file=codeupipe/__init__.py hash=afd4ab5 -->
```
codeupipe/
├── __init__.py              # Public API re-exports
├── py.typed                 # PEP 561 typed marker
│
├── core/                    # Primitives
│   ├── payload.py           # Payload, MutablePayload
│   ├── filter.py            # Filter Protocol
│   ├── stream_filter.py     # StreamFilter Protocol
│   ├── pipeline.py          # Pipeline orchestrator
│   ├── valve.py             # Valve — conditional gate
│   ├── tap.py               # Tap Protocol — observation
│   ├── state.py             # State — execution metadata
│   └── hook.py              # Hook ABC — lifecycle
│
├── utils/
│   └── error_handling.py    # ErrorHandlingMixin, RetryFilter
│
├── converter/               # CodeUChain ↔ codeupipe migration
│   ├── config.py            # Pattern config (mvc/clean/hexagonal/flat)
│   ├── filters/             # 7 conversion filters
│   ├── taps/                # ConversionLogTap
│   └── pipelines/           # build_export_pipeline, build_import_pipeline
│
├── linter/                  # Analysis pipelines (dogfooded as CUP)
│   ├── lint_pipeline.py     # build_lint_pipeline()
│   ├── coverage_pipeline.py # build_coverage_pipeline()
│   ├── report_pipeline.py   # build_report_pipeline()
│   ├── doc_check_pipeline.py# build_doc_check_pipeline()
│   └── (18 filter files)    # ScanDirectory, CheckNaming, etc.
│
├── testing.py               # Test helpers — run_filter, assert_payload, etc.
└── cli.py                   # cup new/list/bundle/lint/coverage/report/doc-check
```
<!-- /cup:ref -->

---

## Core Types

<!-- cup:ref file=codeupipe/core/__init__.py hash=e3e2418 -->
| Type | Source | Role |
|------|--------|------|
| `Payload` | core/payload.py | Immutable data container |
| `MutablePayload` | core/payload.py | Mutable sibling for bulk edits |
| `Filter` | core/filter.py | Processing unit — `.call(payload) → Payload` |
| `StreamFilter` | core/stream_filter.py | Streaming — `.stream(chunk)` yields 0..N |
| `Pipeline` | core/pipeline.py | Orchestrator — `.run()` / `.stream()` |
| `Valve` | core/valve.py | Conditional gate — filter + predicate |
| `Tap` | core/tap.py | Read-only observer — `.observe(payload)` |
| `State` | core/state.py | Execution metadata |
| `Hook` | core/hook.py | Lifecycle — before / after / on_error |
<!-- /cup:ref -->

---

## Utils

<!-- cup:ref file=codeupipe/utils/__init__.py hash=9c3f862 -->
<!-- cup:ref file=codeupipe/utils/error_handling.py symbols=ErrorHandlingMixin,RetryFilter hash=dc0f5ec -->
| Type | Role |
|------|------|
| `ErrorHandlingMixin` | Error routing for pipelines |
| `RetryFilter` | Resilience wrapper — retries N times |
<!-- /cup:ref -->
<!-- /cup:ref -->

---

## Converter

<!-- cup:ref file=codeupipe/converter/__init__.py hash=117430e -->
| Export | Role |
|--------|------|
| `load_config` | Parse `.cup.json` or pattern defaults |
| `DEFAULT_CONFIG` | Default config dict |
| `PATTERN_DEFAULTS` | Pattern configs (mvc/clean/hexagonal/flat) |
| `build_export_pipeline` | CUP → standard Python |
| `build_import_pipeline` | Standard Python → CUP |
<!-- /cup:ref -->

---

## Linter Pipelines

<!-- cup:ref file=codeupipe/linter/__init__.py hash=84e6f07 -->
<!-- cup:ref file=codeupipe/linter/lint_pipeline.py symbols=build_lint_pipeline hash=ccff493 -->
<!-- cup:ref file=codeupipe/linter/coverage_pipeline.py symbols=build_coverage_pipeline hash=004f7b8 -->
<!-- cup:ref file=codeupipe/linter/report_pipeline.py symbols=build_report_pipeline hash=15f61c5 -->
<!-- cup:ref file=codeupipe/linter/doc_check_pipeline.py symbols=build_doc_check_pipeline hash=00e62dc -->
| Pipeline | Command | Purpose |
|----------|---------|---------|
| `build_lint_pipeline()` | `cup lint` | Standards violations (CUP000–CUP008) |
| `build_coverage_pipeline()` | `cup coverage` | Component↔test coverage gaps |
| `build_report_pipeline()` | `cup report` | Health report with scores |
| `build_doc_check_pipeline()` | `cup doc-check` | Doc freshness verification |
<!-- /cup:ref -->
<!-- /cup:ref -->
<!-- /cup:ref -->
<!-- /cup:ref -->
<!-- /cup:ref -->

---

## Testing Utilities

<!-- cup:ref file=codeupipe/testing.py symbols=run_filter,run_pipeline,assert_payload,assert_keys,assert_state,mock_filter hash=c119f9c -->
| Helper | Purpose |
|--------|---------|
| `run_filter(filter, data)` | Run one filter, returns Payload |
| `run_pipeline(pipeline, data)` | Run full pipeline |
| `assert_payload(payload, **kv)` | Assert key=value pairs |
| `assert_keys(payload, *keys)` | Assert keys exist |
| `assert_state(payload, ...)` | Assert State tracking |
| `mock_filter(**sets)` | Mock filter that sets keys |
| `mock_tap()` / `mock_hook()` | Recording mocks |
<!-- /cup:ref -->

---

## CLI

<!-- cup:ref file=codeupipe/cli.py symbols=main,scaffold,bundle,lint,coverage,report,doc_check hash=1e63d0e -->
| Command | Purpose |
|---------|---------|
| `cup new <type> <name> [path]` | Scaffold component + test |
| `cup list` | Show component types |
| `cup bundle <path>` | Generate `__init__.py` re-exports |
| `cup lint <path>` | Check CUP conventions |
| `cup coverage <path>` | Map test coverage |
| `cup report <path>` | Health report |
| `cup doc-check [path]` | Doc freshness check |
<!-- /cup:ref -->

---

## Tests

909 tests across 48 files. Full suite: `pytest`

---

*Maintained via `cup doc-check` — if a referenced file changes, the marker hash drifts and CI catches it.*
