# codeupipe — Agent Navigation Guide

> This file helps AI agents, LLMs, and automated tools navigate the
> codeupipe documentation efficiently. All pages are available as
> plain-text Markdown at `<page-url>.txt` — no HTML parsing required.

---

## What Is codeupipe?

codeupipe is a Python pipeline framework for composing data-processing workflows.
Core pattern: Payload → Filter → Pipeline. Zero external dependencies. Python 3.9+.

**Key types:**

| Type | Role |
|------|------|
| `Payload` | Immutable data container; `.get(key)` / `.insert(key, value)` |
| `Filter` | Sync or async `.call(payload) → Payload` |
| `Pipeline` | Orchestrator; `.run()` / `.run_sync()` / `.stream()` |
| `Valve` | Conditional filter; only runs when predicate returns True |
| `Tap` | Observation point; `.observe()` without modifying payload |
| `Hook` | Lifecycle callbacks: before / after / on_error |
| `StreamFilter` | Async generator; receives one chunk, yields 0..N chunks |
| `State` | Execution metadata: executed, skipped, errors, chunks |
| `TapSwitch` | Toggle taps on/off at runtime — zero-downtime observability |
| `HotSwap` | Atomically replace the active Pipeline from config — zero-downtime updates |

**Install:** `pip install codeupipe`
**Repo:** https://github.com/codeuchain/codeupipe

---

## Navigation — Plain Text Endpoints (no HTML)

**Start here** (recommended first page):

```
curl https://codeuchain.github.io/codeupipe/getting-started.txt
```

**Full API reference** (every type, every method):

```
curl https://codeuchain.github.io/codeupipe/concepts.txt
```

**All page URLs:**

```
curl https://codeuchain.github.io/codeupipe/curl.txt
```

---

## Page Map

| Path | Description |
|------|-------------|
| `/getting-started.txt` | Quick start, first pipeline, CLI, testing helpers |
| `/install.txt` | Install instructions, connectors, Python versions |
| `/concepts.txt` | Full API reference — all types with examples |
| `/best-practices.txt` | Project structure, naming, testing strategy |
| `/deploy-guide.txt` | Docker, Render (free), Vercel, Netlify — cup.toml |
| `/module-index.txt` | Package structure map, all public symbols |
| `/roadmap.txt` | Expansion rings v0.1–v0.9+ with status |
| `/blueprints/ring7.txt` | Ring 7 design: deploy adapters, manifest, CLI |
| `/blueprints/ring8.txt` | Ring 8 design: connector protocol, marketplace |
| `/blueprints/ring9.txt` | Ring 9 design: marketplace index, first-party connectors |

---

## Quick Reference — Core Patterns

### Minimal Pipeline

```python
from codeupipe import Payload, Pipeline

class MyFilter:
    def call(self, payload):
        return payload.insert("result", payload.get("input").upper())

pipeline = Pipeline()
pipeline.add_filter(MyFilter(), name="upper")
result = pipeline.run_sync(Payload({"input": "hello"}))
# result.get("result") == "HELLO"
```

### Payload Is Immutable — always return a new one

```python
# CORRECT
def call(self, payload):
    return payload.insert("key", "value")   # returns new Payload

# WRONG — modifying in place does nothing
def call(self, payload):
    payload["key"] = "value"                # AttributeError
```

### Testing

```python
from codeupipe.testing import run_filter, assert_payload
result = run_filter(MyFilter(), {"input": "hello"})
assert_payload(result, result="HELLO")
```

### CLI

```bash
cup new filter <name> <dir>             # scaffold filter + test
cup new pipeline <name> <dir>           # scaffold pipeline
cup lint <dir>                          # convention checks
cup run pipeline.json                   # execute from config
cup deploy docker cup.toml              # generate Docker artifacts
cup deploy render cup.toml              # generate Render (free cloud) artifacts
cup distribute checkpoint cp.json --status  # manage payload checkpoints
cup distribute remote https://api.example   # test remote filter endpoint
cup test                                # smart test runner
cup doctor                              # project health diagnostics
cup graph pipeline.json                 # Mermaid pipeline visualization
cup version --bump patch                # show/bump semver
```

### Runtime Control (Zero-Downtime)

```python
from codeupipe import Pipeline, TapSwitch, HotSwap

# Toggle taps without restarting the server
switch = TapSwitch(pipeline)
switch.disable("verbose_logger")  # silence a noisy tap
switch.enable("verbose_logger")   # bring it back
switch.status()                   # {"verbose_logger": True, ...}

# Hot-swap the pipeline from a new config (in-flight requests finish safely)
swap = HotSwap("pipeline.json", registry=my_registry)
result = await swap.run(payload)
swap.reload("pipeline_v2.json")   # atomic swap, version increments
```

---

## Connectors (optional packages)

```bash
pip install codeupipe-postgres     # PostgreSQL: Query, Execute, Transaction
pip install codeupipe-stripe       # Stripe payments
pip install codeupipe-resend       # Email via Resend
pip install codeupipe-google-ai    # Google Gemini AI
```

Connectors auto-register via entry points. Declared in `cup.toml` `[connectors.*]`.

---

## Deploy Targets

| Target | What it generates |
|--------|-------------------|
| `docker` | Dockerfile + docker-compose.yml (local dev) |
| `render` | render.yaml blueprint (free tier, no credit card) |
| `vercel` | vercel.json + serverless functions |
| `netlify` | netlify.toml + serverless functions |

---

## Notes for Agents

- Strip HTML comment markers (`<!-- cup:ref ... -->`) from `.txt` files — these
  are doc-freshness tracking markers used by the `cup doc-check` tool, not
  content intended for end users.
- Code blocks use standard Markdown fenced syntax.
- Tables use standard Markdown pipe syntax.
- All examples in `concepts.txt` are verified against the actual source code
  by the test suite (`tests/test_docs_examples.py`).
- The framework has zero external runtime dependencies — everything shown
  in the docs runs with only the Python standard library.
