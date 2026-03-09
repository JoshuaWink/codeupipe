---
hide:
  - navigation
---

# codeupipe

**Python pipeline framework — composable Payload → Filter → Pipeline pattern with streaming. Zero external dependencies.**

<div class="marketplace-banner" markdown>
<div class="banner-content" markdown>

:material-store:{ .banner-icon } **Marketplace is Live!** Browse connectors, filters, and hooks built by the community.

<div class="banner-actions" markdown>
[:material-arrow-right: Browse Marketplace](https://codeuchain.github.io/codeupipe-marketplace/){ .md-button .md-button--primary }
[:material-plus-circle: Submit a Component](https://github.com/codeuchain/codeupipe-marketplace/blob/main/CONTRIBUTING.md){ .md-button }
</div>

</div>
</div>

<div class="grid cards" markdown>

-   :material-rocket-launch:{ .lg .middle } **Get Started in 5 Minutes**

    ---

    Install codeupipe and build your first pipeline in minutes.

    [:octicons-arrow-right-24: Quick Start](getting-started.md)

-   :material-book-open-variant:{ .lg .middle } **Concepts & API**

    ---

    Full reference for every type — Payload, Filter, Pipeline, Valve, Tap, and more.

    [:octicons-arrow-right-24: Concepts](concepts.md)

-   :material-check-all:{ .lg .middle } **Best Practices**

    ---

    Project structure, naming conventions, testing strategy, CLI workflow.

    [:octicons-arrow-right-24: Best Practices](best-practices.md)

-   :material-cloud-upload:{ .lg .middle } **Deploy**

    ---

    Docker, Render (free), Vercel, Netlify — from `cup.toml` to running app.

    [:octicons-arrow-right-24: Deploy Guide](deploy-guide.md)

</div>

---

## Core Concepts at a Glance

| Concept | Role |
|---|---|
| **Payload** | Immutable data container flowing through the pipeline |
| **MutablePayload** | Mutable sibling for performance-critical bulk edits |
| **Filter** | Processing unit — sync or async `.call(payload) → Payload` |
| **StreamFilter** | Streaming — async `.stream(payload)` yields 0..N chunks |
| **Pipeline** | Orchestrator — `.run()` for batch, `.stream()` for streaming |
| **Valve** | Conditional flow control — gates a Filter with a predicate |
| **Tap** | Non-modifying observation — inspect without changing |
| **State** | Execution metadata — tracks what ran, skipped, errors |
| **Hook** | Lifecycle — `before()` / `after()` / `on_error()` |
| **RetryFilter** | Resilience — retries a Filter up to N times |

## Minimal Example

```python
import asyncio
from codeupipe import Payload, Pipeline

class CleanInput:
    def call(self, payload):
        return payload.insert("text", payload.get("text", "").strip())

class Validate:
    def call(self, payload):
        if not payload.get("text"):
            raise ValueError("Empty input")
        return payload

pipeline = Pipeline()
pipeline.add_filter(CleanInput(), name="clean")
pipeline.add_filter(Validate(), name="validate")

result = asyncio.run(pipeline.run(Payload({"text": "  hello  "})))
print(result.get("text"))  # "hello"
```

## Install

```bash
pip install codeupipe
```

!!! info "Zero Dependencies"
    codeupipe uses only the Python standard library. No external packages required. Python 3.9+.
