# Ring 8 — Connect: Implementation Blueprint

**Goal:** Wire pipelines to real services. Make the CLI usable by both humans and AI agents without special infrastructure.

---

## Core Insight

A connector **is** a Filter. There is no new type.

A Filter that trims whitespace and a Filter that calls Stripe share the same protocol:
`async call(payload) → payload`. The difference is intent, not interface.

What we're building is the **wiring layer** — the power strip between a Filter and the service it needs. The user declares what services their project uses in `cup.toml`, installs a connector package (or uses the built-in HTTP connector), and their Filters get configured connections without manual plumbing.

---

## What Changes

| Concern | What We Build | Where |
|---|---|---|
| **Configuration convention** | `[connectors]` section in cup.toml — names, providers, env var references | `codeupipe/connect/config.py` |
| **Connector discovery** | Entry point group `codeupipe.connectors` + built-in HttpConnector | `codeupipe/connect/discovery.py` |
| **Health check convention** | Optional `async health() → bool` method on service Filters | Convention, not enforced |
| **Built-in HTTP connector** | stdlib `urllib`-based Filter for REST APIs without an SDK | `codeupipe/connect/http.py` |
| **Registry integration** | `kind="connector"` tag in existing Registry | Already supported |
| **CLI: `cup connect`** | `--list` shows connectors, `--health` pre-flight checks | `codeupipe/cli.py` |
| **CLI: `cup describe`** | Inspect a pipeline — inputs, outputs, steps, connectors needed | `codeupipe/cli.py` |
| **CLI: `--json` flag** | Machine-readable output on all commands | `codeupipe/cli.py` |
| **Consistent exit codes** | 0 = success, 1 = user error, 2 = system error | `codeupipe/cli.py` |

## What We're NOT Building

- No agent hosting, reasoning loops, or tool registries
- No LLM integration in core
- No special "agent mode" — the CLI is just well-structured enough that agents use it naturally
- No SDK wrappers in core — those are separate `codeupipe-{service}` packages

---

## Architecture

### The Mental Model

```
cup.toml                    Registry                      Filter
[connectors.stripe]   →     kind="connector"         →    self.stripe.execute(...)
provider = "stripe"         name="StripeCheckout"
key_env = "STRIPE_KEY"      auto-configured from toml
```

### System Diagram

```
┌─────────────────────────────────────────────────────────┐
│  cup.toml                                               │
│                                                         │
│  [connectors.stripe]                                    │
│  provider = "stripe"                                    │
│  key_env = "STRIPE_API_KEY"                             │
│                                                         │
│  [connectors.google-ai]                                    │
│  provider = "google-ai"                                    │
│  key_env = "GOOGLE_AI_API_KEY"                             │
│  model = "gemini-2.0-flash"                                │
│                                                         │
│  [connectors.my-webhook]                                │
│  provider = "http"              ← built-in, no install  │
│  base_url_env = "WEBHOOK_URL"                           │
│  method = "POST"                                        │
└───────────────┬─────────────────────────────────────────┘
                │
                ▼
┌───────────────────────────┐     ┌──────────────────────┐
│  ConnectorConfig          │     │  Entry Points         │
│  parse [connectors.*]     │     │  codeupipe.connectors │
│  resolve env vars         │     │  ├─ stripe            │
│  validate provider exists │     │  ├─ google-ai         │
└───────────┬───────────────┘     │  └─ postgres          │
            │                     └──────────┬───────────┘
            ▼                                │
┌───────────────────────────────────────────────────────┐
│  Registry                                             │
│  ┌─────────────────┐  ┌──────────────────┐            │
│  │ kind="filter"   │  │ kind="connector" │            │
│  │ SanitizeInput   │  │ StripeCheckout   │            │
│  │ FormatResponse  │  │ GeminiGenerate   │            │
│  │ ValidateEmail   │  │ HttpConnector    │ ← built-in │
│  └─────────────────┘  └──────────────────┘            │
└───────────────────────────────────────────────────────┘
            │
            ▼
┌───────────────────────────────────────────────────────┐
│  Pipeline                                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐            │
│  │ Sanitize │→ │ Gemini   │→ │ Format   │            │
│  │ (filter) │  │(connector│  │ (filter) │            │
│  │          │  │  filter) │  │          │            │
│  └──────────┘  └──────────┘  └──────────┘            │
└───────────────────────────────────────────────────────┘
```

### What a Connector Package Looks Like

A connector package (e.g. `codeupipe-stripe`) is a standard Python package that:

1. Exposes one or more Filters that wrap the SDK
2. Registers them via entry points with `kind="connector"`
3. Reads its config from cup.toml's `[connectors]` section

```
codeupipe-stripe/
├── pyproject.toml          # depends on stripe SDK
├── codeupipe_stripe/
│   ├── __init__.py
│   ├── checkout.py         # StripeCheckoutFilter — a Filter
│   ├── subscription.py     # StripeSubscriptionFilter — a Filter
│   └── webhook.py          # StripeWebhookFilter — a Filter
```

```toml
# codeupipe-stripe/pyproject.toml
[project.entry-points."codeupipe.connectors"]
stripe = "codeupipe_stripe:register"
```

The register function:
```python
def register(registry, config):
    """Called by codeupipe when this connector is configured in cup.toml."""
    api_key = os.environ.get(config.get("key_env", "STRIPE_API_KEY"))
    registry.register("StripeCheckout", StripeCheckoutFilter, kind="connector")
    registry.register("StripeSubscription", StripeSubscriptionFilter, kind="connector")
```

### What a Connector Filter Looks Like

It's just a Filter. The only convention is the optional `health()` method:

```python
class StripeCheckoutFilter:
    """Connector filter — creates a Stripe checkout session."""

    def __init__(self, api_key: str):
        self.api_key = api_key

    async def call(self, payload):
        # Use the Stripe SDK to create a checkout session
        import stripe
        stripe.api_key = self.api_key
        session = stripe.checkout.Session.create(
            line_items=[{"price": payload.get("price_id"), "quantity": 1}],
            mode="payment",
            success_url=payload.get("success_url"),
        )
        return payload.insert("checkout_url", session.url)

    async def health(self):
        """Optional — called by `cup connect --health`."""
        import stripe
        stripe.api_key = self.api_key
        try:
            stripe.Account.retrieve()
            return True
        except Exception:
            return False
```

### Services Without an SDK — Built-in HttpConnector

For services that only expose a REST API, core ships an `HttpConnector` Filter built on `urllib` (zero deps):

```toml
# cup.toml
[connectors.my-webhook]
provider = "http"
base_url_env = "WEBHOOK_URL"
method = "POST"
headers = { "Content-Type" = "application/json" }
```

```python
class HttpConnector:
    """Built-in connector for REST APIs. Zero external dependencies."""

    def __init__(self, base_url: str, method: str = "GET", headers: dict = None):
        self.base_url = base_url
        self.method = method
        self.headers = headers or {}

    async def call(self, payload):
        # Uses urllib.request — stdlib, no deps
        import json
        import urllib.request
        url = self.base_url + payload.get("path", "")
        body = json.dumps(payload.get("body", {})).encode() if self.method != "GET" else None
        req = urllib.request.Request(url, data=body, headers=self.headers, method=self.method)
        with urllib.request.urlopen(req) as resp:
            result = json.loads(resp.read())
        return payload.insert("response", result)

    async def health(self):
        import urllib.request
        try:
            urllib.request.urlopen(self.base_url)
            return True
        except Exception:
            return False
```

---

## Agent-Ready CLI

An AI agent using codeupipe is like a developer who actually reads `--help`, parses JSON output instead of skimming colored text, and validates before deploying. We don't build anything "for agents" — we just make the CLI good enough that any structured consumer (human or machine) can use it predictably.

### `--json` Flag (All Commands)

Every `cup` command gains `--json` for structured output:

```bash
# Human-friendly (default)
$ cup connect --list
Connectors:
  stripe        StripeCheckout, StripeSubscription
  google-ai     GeminiGenerate

# Machine-friendly
$ cup connect --list --json
{
  "connectors": [
    {"provider": "stripe", "filters": ["StripeCheckout", "StripeSubscription"]},
    {"provider": "google-ai", "filters": ["GeminiGenerate"]}
  ]
}
```

### `cup connect` Commands

```bash
# List configured connectors and their filters
cup connect --list

# Pre-flight health checks — verify all services are reachable
cup connect --health

# Check a specific connector
cup connect --health stripe
```

### `cup describe` Command

Inspect a pipeline config — what it needs, what it guarantees, what services it uses:

```bash
$ cup describe pipelines/ai-chat.json
Pipeline: ai-chat
  Steps:
    1. SanitizeInput      (filter)
    2. GeminiGenerate      (connector → google-ai)
    3. SafetyFilter        (filter)
    4. FormatResponse      (filter)
  Requires input:  message
  Guarantees output: response
  Connectors needed: google-ai

$ cup describe pipelines/ai-chat.json --json
{
  "name": "ai-chat",
  "steps": [
    {"name": "SanitizeInput", "kind": "filter"},
    {"name": "GeminiGenerate", "kind": "connector", "provider": "google-ai"},
    {"name": "SafetyFilter", "kind": "filter"},
    {"name": "FormatResponse", "kind": "filter"}
  ],
  "require_input": ["message"],
  "guarantee_output": ["response"],
  "connectors": ["google-ai"]
}
```

### Consistent Exit Codes

| Code | Meaning | Example |
|---|---|---|
| 0 | Success | Command completed normally |
| 1 | User error | Bad args, missing config, unknown template |
| 2 | System error | Service unreachable, permission denied, runtime crash |

---

## cup.toml `[connectors]` Section

```toml
[project]
name = "my-saas"
version = "0.1.0"

[connectors.stripe]
provider = "stripe"              # matches entry point name
key_env = "STRIPE_API_KEY"       # env var — never hardcoded

[connectors.google-ai]
provider = "google-ai"
key_env = "GOOGLE_AI_API_KEY"
model = "gemini-2.0-flash"           # provider-specific config

[connectors.my-api]
provider = "http"                # built-in, no install needed
base_url_env = "MY_API_URL"
method = "POST"
headers = { "Authorization" = "Bearer ${MY_API_TOKEN}" }

[deploy]
target = "vercel"

[dependencies]
codeupipe = ">=0.7.0"
codeupipe-stripe = ">=0.1.0"    # pip install codeupipe-stripe
codeupipe-google-ai = ">=0.1.0"
```

### Config Resolution Rules

1. `key_env` / `base_url_env` / `${VAR}` — resolved from `os.environ` at connect time, never stored
2. Provider name maps to an entry point in `codeupipe.connectors` group
3. `provider = "http"` is always available (built-in)
4. Extra keys (like `model`, `method`, `headers`) are passed as config dict to the connector's register function

---

## File Layout

```
codeupipe/
├── connect/
│   ├── __init__.py          # exports: ConnectorConfig, HttpConnector, load_connectors
│   ├── config.py            # parse [connectors] from cup.toml, resolve env vars
│   ├── discovery.py         # find connector packages via entry points
│   └── http.py              # HttpConnector — built-in REST connector (urllib)
```

---

## Phased Implementation

### Phase 1 — Connector Wiring (Ring 8a)

| # | Task | Detail |
|---|---|---|
| 1 | `codeupipe/connect/config.py` | Parse `[connectors.*]` from cup.toml, resolve `key_env` / `base_url_env` / `${VAR}` from env, validate provider exists |
| 2 | `codeupipe/connect/discovery.py` | Discover connector packages via `codeupipe.connectors` entry point group, call their `register()` with config |
| 3 | `codeupipe/connect/http.py` | `HttpConnector` Filter — urllib-based, configurable method/headers/base_url, optional `health()` |
| 4 | `codeupipe/connect/__init__.py` | Exports |
| 5 | `cup connect --list` CLI | List connectors from config + installed packages |
| 6 | `cup connect --health` CLI | Call `health()` on all/specific connectors, report status |
| 7 | Manifest validation | Validate `[connectors]` section in cup.toml |
| 8 | Tests | Config parsing, HttpConnector, discovery, health checks, CLI commands |

### Phase 2 — Agent-Ready CLI (Ring 8b)

| # | Task | Detail |
|---|---|---|
| 9 | `--json` flag on all commands | Add `--json` to argument parser, wrap output in JSON when set |
| 10 | `cup describe` command | Inspect pipeline.json — steps, kinds, inputs, outputs, connector deps |
| 11 | Consistent exit codes | Audit all command handlers — 0/1/2 scheme |
| 12 | Structured error output | Errors as `{"error": "message", "code": 1}` when `--json` is set |
| 13 | Tests | JSON output parsing, describe output, exit code verification |

### Phase 3 — First-Party Connector Packages (Separate Repos)

| Package | Service | Entry Point |
|---|---|---|
| `codeupipe-google-ai` | Google AI / Gemini (multimodal generation, embeddings, vision) | `codeupipe.connectors: google-ai` |
| `codeupipe-stripe` | Stripe (checkout, subscriptions, webhooks) | `codeupipe.connectors: stripe` |
| `codeupipe-postgres` | PostgreSQL (query, transaction) | `codeupipe.connectors: postgres` |
| `codeupipe-resend` | Resend (send email, templates) | `codeupipe.connectors: resend` |

These are separate repos/packages. Core provides the convention; packages provide the implementation.

### Future — Connector Marketplace

Once the connector protocol is proven and the first-party packages are stable, we open a **connector marketplace** where the community can publish and discover connectors. Think npm/PyPI but scoped to codeupipe service integrations — searchable by provider, rated by usage, verified by us. The entry point convention makes this frictionless: any package that registers under `codeupipe.connectors` is marketplace-eligible. The `cup connect --list` command already shows what's installed; the marketplace becomes the discovery layer for what's *available*.

---

## Coverage Matrix

| Service Has... | What Ships | User Installs |
|---|---|---|
| SDK (Stripe, Google AI, AWS) | Nothing in core | `pip install codeupipe-stripe` — wraps SDK, registers as connector |
| REST API only | `HttpConnector` in core | Nothing extra — configure in cup.toml |
| Database | Nothing in core | `pip install codeupipe-postgres` — wraps driver |
| Custom / internal | User writes a Filter with `kind="connector"` | Nothing — uses existing Registry |

---

## Key Design Decisions

1. **A connector is a Filter, not a new type.** The Registry already supports `kind="connector"` as a tag. No new ABC.

2. **Config lives in cup.toml.** Credentials reference env vars, never hardcoded. Resolution happens at connect time.

3. **The agent is a CLI user.** We don't build agent infrastructure — we make the CLI predictable, discoverable, and machine-readable with `--json` and `cup describe`.

4. **Zero-dep constraint holds.** `HttpConnector` uses `urllib`. Everything else is a separate package.

5. **Entry point discovery reuses the deploy pattern.** Same mechanics as `codeupipe.deploy` but under `codeupipe.connectors`.
