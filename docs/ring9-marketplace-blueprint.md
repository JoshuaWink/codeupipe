# Ring 9 — Marketplace + First Connectors: Blueprint

**Goal:** Stand up a connector marketplace that lets the community discover, install, and rate connectors — and ship the first 4 connectors that prove the pattern works.

---

## Part 1: Deep Analysis — The Marketplace Problem

### Problem Definition

We have the protocol. We have the entry point convention. We have `cup connect --list` to show what's installed. What we don't have is *discoverability* — a developer building a pipeline that talks to Stripe has no way to know `codeupipe-stripe` exists unless they already know to look for it. The marketplace closes that gap.

### Perspective Shift: Developer Experience

From the developer's seat, the ideal flow is:

```bash
# "I need Stripe in my pipeline"
cup marketplace search stripe
# → codeupipe-stripe (v0.2.1) ★★★★☆ — Checkout, Subscriptions, Webhooks
#   by codeuchain • 12k installs • verified

pip install codeupipe-stripe

# Done. It self-registers via entry points.
cup connect --list
# → stripe: StripeCheckout, StripeSubscription, StripeWebhook
```

No configuration ceremony. No adapter wiring. `pip install` + entry point convention = instant availability.

### Perspective Shift: Package Author

A community member who wraps Twilio wants to publish. Their flow:

1. Write a Filter that wraps the Twilio SDK
2. Add `[project.entry-points."codeupipe.connectors"]` to pyproject.toml
3. `pip install codeupipe-twilio` works locally, `cup connect --list` shows it
4. Publish to PyPI as normal
5. Register with the codeupipe marketplace index (metadata + verification)

The marketplace is a **thin layer** on top of PyPI, not a replacement.

### Perspective Shift: Trust & Security

Connectors handle API keys. A malicious connector could exfiltrate credentials. We need:

- **Verified badge**: Connectors from `codeuchain` org are verified. Community connectors are unverified until reviewed.
- **Manifest declaration**: cup.toml `[connectors]` section makes it explicit which services are wired — no silent network calls.
- **Health check as trust signal**: A connector that implements `health()` is more trustworthy because it's observable.
- **Audit trail integration**: Ring 6's AuditHook can record every connector invocation, making behavior auditable.

### Perspective Shift: Business / Ecosystem

The marketplace is the growth flywheel:

```
More connectors → More use cases → More users → More connectors
```

NPM didn't succeed because Node was the best runtime. It succeeded because every problem had a package. The marketplace makes codeupipe the framework where "there's a connector for that."

---

## Part 2: Marketplace Architecture

### Design Principles

1. **PyPI is the package host.** We don't build a package registry. PyPI already handles hosting, versioning, and distribution.
2. **The marketplace is an index.** A lightweight metadata layer that annotates PyPI packages with codeupipe-specific info (provider, categories, verification status, install count).
3. **CLI-first, web-second.** `cup marketplace search` is the primary interface. A web UI can come later.
4. **Entry points are the contract.** If a package registers under `codeupipe.connectors`, it's marketplace-eligible.
5. **Trust tiers, not gatekeeping.** Anyone can publish. Verification is a signal, not a gate.

### System Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                     codeupipe Marketplace                       │
│                                                                 │
│  ┌───────────────┐    ┌──────────────────┐    ┌──────────────┐  │
│  │ Index (JSON)  │    │ cup marketplace   │    │ Web UI       │  │
│  │               │    │ CLI commands      │    │ (future)     │  │
│  │ - packages    │◄───│ - search          │    │ - browse     │  │
│  │ - metadata    │    │ - info            │    │ - rate       │  │
│  │ - categories  │    │ - install         │    │ - verify     │  │
│  │ - ratings     │    │ - publish         │    │              │  │
│  │ - trust tier  │    │                   │    │              │  │
│  └───────┬───────┘    └──────────────────┘    └──────────────┘  │
│          │                                                       │
└──────────┼───────────────────────────────────────────────────────┘
           │
           ▼
┌─────────────────────┐     ┌──────────────────────────────────┐
│  PyPI               │     │  GitHub                          │
│  (actual packages)  │     │  (source, issues, CI badges)     │
│                     │     │                                  │
│  codeupipe-stripe   │     │  codeuchain/codeupipe-stripe     │
│  codeupipe-openai   │     │  codeuchain/codeupipe-openai     │
│  codeupipe-twilio   │     │  community/codeupipe-twilio      │
└─────────────────────┘     └──────────────────────────────────┘
```

### The Index

The marketplace index is a static JSON file (later backed by a simple API) hosted alongside documentation:

```json
{
  "version": 1,
  "updated": "2026-03-07T00:00:00Z",
  "connectors": [
    {
      "name": "codeupipe-stripe",
      "provider": "stripe",
      "pypi": "codeupipe-stripe",
      "repo": "https://github.com/codeuchain/codeupipe-stripe",
      "description": "Stripe checkout, subscriptions, and webhooks",
      "categories": ["payments", "billing"],
      "filters": ["StripeCheckout", "StripeSubscription", "StripeWebhook"],
      "trust": "verified",
      "min_codeupipe": "0.8.0",
      "latest": "0.2.1"
    },
    {
      "name": "codeupipe-openai",
      "provider": "openai",
      "pypi": "codeupipe-openai",
      "repo": "https://github.com/codeuchain/codeupipe-openai",
      "description": "OpenAI chat completions, embeddings, and image generation",
      "categories": ["ai", "llm", "embeddings"],
      "filters": ["OpenAIChat", "OpenAIEmbed", "OpenAIImage"],
      "trust": "verified",
      "min_codeupipe": "0.8.0",
      "latest": "0.1.0"
    }
  ]
}
```

### Trust Tiers

| Tier | Badge | Meaning | How to Get |
|------|-------|---------|------------|
| **Verified** | ✅ | Published by codeuchain org, reviewed, tested | Be a first-party package |
| **Community** | 🔷 | Published on PyPI, entry point registered | Publish and register with index |
| **Unindexed** | — | Installed locally, works via entry points | Just `pip install` — no indexing needed |

All three tiers work with `cup connect --list`. The marketplace only affects discoverability, not functionality.

### CLI Commands

```bash
# Search the marketplace index
cup marketplace search "payments"
# → codeupipe-stripe ✅ (v0.2.1) — Checkout, Subscriptions, Webhooks
#   Categories: payments, billing
#   pip install codeupipe-stripe

cup marketplace search "ai"
# → codeupipe-openai ✅ (v0.1.0) — Chat, Embeddings, Images
# → codeupipe-anthropic 🔷 (v0.3.0) — Claude completions
#   Categories: ai, llm

# Get detailed info
cup marketplace info codeupipe-stripe
# → Name: codeupipe-stripe
#   Provider: stripe
#   Trust: ✅ verified
#   Filters: StripeCheckout, StripeSubscription, StripeWebhook
#   Requires: codeupipe >= 0.8.0, stripe >= 5.0.0
#   Repo: https://github.com/codeuchain/codeupipe-stripe

# Install (convenience wrapper around pip)
cup marketplace install codeupipe-stripe
# → pip install codeupipe-stripe ... done
# → Connector 'stripe' now available. Run: cup connect --list

# All with --json
cup marketplace search "payments" --json
```

### Index Hosting — Start Simple

**Phase 1:** Static JSON file in the `codeuchain/marketplace` repo, fetched by the CLI via raw GitHub URL. Updated via PR when packages publish.

**Phase 2:** GitHub Pages site at `marketplace.codeuchain.com` with browse/search.

**Phase 3:** Small API (Cloudflare Workers or similar) for ratings, install counts, automated verification.

We don't need Phase 3 to launch. Static JSON + CLI search is enough.

---

## Part 3: First Connectors — The Fab Four

### Selection Criteria

The first connectors need to:

1. **Prove the pattern** — Show that `Filter + entry point + cup.toml` works for real services
2. **Cover different service shapes** — SDK-heavy, REST-only, database, auth-gated
3. **Serve real use cases** — Things developers actually build pipelines for
4. **Be independently valuable** — Worth installing even outside codeupipe

### The Four

| # | Package | Provider | Why This One |
|---|---------|----------|-------------|
| 1 | `codeupipe-openai` | OpenAI | **The gravity well.** Every AI pipeline needs an LLM connector. Proves the pattern for SDK-heavy services with API-key auth. Chat completions, embeddings, and image gen cover 80% of AI pipeline use cases. |
| 2 | `codeupipe-stripe` | Stripe | **The payments workhorse.** Most SaaS pipelines need payments. Proves the pattern for webhook-driven services with complex objects. Checkout, subscription management, and webhook verification. |
| 3 | `codeupipe-postgres` | PostgreSQL | **The database anchor.** Pipelines that don't touch a database are demos. Proves the pattern for connection-pooled, stateful services. Query, transaction, and bulk insert cover data pipeline needs. |
| 4 | `codeupipe-resend` | Resend | **The modern email sender.** Simpler than SendGrid, developer-friendly API, proves the pattern for lightweight REST-first services. Send transactional email, template rendering, audience management. |

### Why These Four Specifically

#### 1. `codeupipe-openai` — AI is the draw

```
User writes a pipeline → needs LLM → installs codeupipe-openai → discovers codeupipe
```

OpenAI is the most common first integration for any AI framework. If we don't have this, developers will roll their own HTTP calls and never reach for the connector system. This validates:
- **SDK wrapping**: openai Python SDK → Filter
- **Config-driven models**: `model = "gpt-4"` in cup.toml
- **Streaming**: OpenAI's streaming API maps to `StreamFilter`
- **Multi-filter packages**: Chat, Embed, Image are separate Filters in one package

**Filters:**
| Filter | Purpose |
|--------|---------|
| `OpenAIChat` | Chat completions (sync) |
| `OpenAIChatStream` | Chat completions (streaming via StreamFilter) |
| `OpenAIEmbed` | Text embeddings |
| `OpenAIImage` | Image generation (DALL-E) |

#### 2. `codeupipe-stripe` — Payments are the validator

Stripe is the validation test for the connector protocol. If our design handles Stripe's complexity (webhooks, idempotency keys, expandable objects, event types), it can handle anything. This validates:
- **Complex auth**: API keys + webhook signing secrets
- **Webhook handling**: Stripe sends events, connector verifies and routes
- **Idempotency**: Filter passes idempotency_key through payload
- **Multiple service shapes**: Checkout (create+redirect), Subscriptions (CRUD), Webhooks (verify+dispatch)

**Filters:**
| Filter | Purpose |
|--------|---------|
| `StripeCheckout` | Create checkout sessions |
| `StripeSubscription` | CRUD subscription management |
| `StripeWebhook` | Verify + parse incoming webhook events |
| `StripeCustomer` | Customer lookup/create |

#### 3. `codeupipe-postgres` — Databases prove durability

A framework that can't talk to a database is a toy. Postgres is the default database for Python developers building real services. This validates:
- **Connection pooling**: Config-driven pool size, managed lifecycle
- **Transactions**: Begin/commit/rollback as pipeline semantics
- **Parameterized queries**: SQL injection prevention built into the Filter contract
- **Health checks**: `SELECT 1` is the canonical health check

**Filters:**
| Filter | Purpose |
|--------|---------|
| `PostgresQuery` | Run parameterized SELECT, return rows |
| `PostgresExecute` | Run INSERT/UPDATE/DELETE, return affected count |
| `PostgresTransaction` | Wrap N operations in a transaction |
| `PostgresBulkInsert` | Batch insert rows efficiently |

**Note:** This connector depends on `psycopg` (or `asyncpg`). The zero-dep constraint doesn't apply to connector packages — only to core.

#### 4. `codeupipe-resend` — Email proves simplicity

We chose Resend over SendGrid because:
- **Modern API**: REST-first, no legacy SMTP baggage
- **Developer experience**: Simple SDK, minimal config
- **Proves REST connectors**: Could use `HttpConnector` but the SDK wrapper is cleaner
- **Fast to ship**: Small surface area, 2-3 Filters max

This validates:
- **Lightweight connectors**: Not everything needs 10 Filters — sometimes 2 is right
- **Template rendering**: Send with variables, connector resolves template
- **The smallest possible connector**: Shows the community what "minimum viable connector" looks like

**Filters:**
| Filter | Purpose |
|--------|---------|
| `ResendEmail` | Send a single email (to, subject, body/html) |
| `ResendTemplate` | Send using a Resend template with variables |

### What We're NOT Building First (and Why)

| Service | Why Not Yet |
|---------|-------------|
| **AWS S3** | Complex auth (IAM roles, STS), better served by boto3 directly. Too much scope for a first connector. |
| **MongoDB** | Postgres covers the database category. Mongo adds complexity without proving a new pattern. |
| **Twilio** | Voice/SMS is niche. Resend covers the "communications" category with less surface area. |
| **GitHub API** | We'd use it, but it's a self-referential choice. Let the community build it as proof the protocol works. |
| **Slack** | Webhook-only is already handled by `HttpConnector`. An SDK wrapper adds little value. |

---

## Part 4: Implementation Plan

### Phase 1 — Marketplace Infrastructure (Ring 9a)

| # | Task | Detail |
|---|------|--------|
| 1 | Create `marketplace/index.json` | Static index file with schema |
| 2 | `codeupipe/marketplace/` package | `fetch_index()`, `search()`, `info()` |
| 3 | `cup marketplace search` CLI | Search index by keyword, category, provider |
| 4 | `cup marketplace info` CLI | Detailed package info |
| 5 | `cup marketplace install` CLI | Convenience `pip install` wrapper |
| 6 | Index validation | Schema check for index JSON, CI for marketplace repo |
| 7 | Tests | Search, info, install, offline fallback |

### Phase 2 — First Connectors (Ring 9b, separate repos)

| # | Package | Priority | Surface Area |
|---|---------|----------|-------------|
| 1 | `codeupipe-openai` | Highest — AI is the draw | 4 Filters |
| 2 | `codeupipe-stripe` | High — validates complexity | 4 Filters |
| 3 | `codeupipe-postgres` | High — proves database pattern | 4 Filters |
| 4 | `codeupipe-resend` | Medium — proves simplicity | 2 Filters |

Each connector repo follows the same structure:
```
codeupipe-{provider}/
├── pyproject.toml              # Entry point + SDK dependency
├── README.md                   # Usage + cup.toml config
├── codeupipe_{provider}/
│   ├── __init__.py             # register() function
│   └── {filter_files}.py       # One file per Filter
├── tests/
│   ├── test_unit.py            # Mock SDK, verify Filter behavior
│   ├── test_integration.py     # Real SDK, mock credentials
│   └── test_e2e.py             # Real service, real credentials (CI secret)
└── .github/workflows/ci.yml   # Test + publish to PyPI
```

### Phase 3 — Community & Web (Ring 9c, future)

| # | Task | Detail |
|---|------|--------|
| 1 | Marketplace web UI | GitHub Pages — browse, search, category filter |
| 2 | `cup marketplace publish` | Register a package in the index via CLI |
| 3 | Automated verification | CI checks entry points, health(), test coverage |
| 4 | Ratings / install counts | Simple API for community signals |
| 5 | Connector template | `cup new connector <name>` scaffolds a connector package |

---

## Key Design Decisions

1. **PyPI is the host, marketplace is the index.** We don't build infrastructure that already exists. PyPI handles distribution; we handle discovery.

2. **Static-first index.** A JSON file in a repo is enough to launch. Complexity comes later.

3. **Trust tiers, not gates.** Anyone can publish a connector. Verification adds a signal, not a wall.

4. **Four connectors prove four patterns.** SDK-heavy (OpenAI), complex auth (Stripe), stateful connection (Postgres), lightweight REST (Resend).

5. **Connectors are separate repos.** They have their own release cycles, their own dependencies, their own tests. Core stays zero-dep.

6. **The community builds the long tail.** We ship 4. The community ships 400. The marketplace makes them findable.
