# codeupipe Roadmap

The expansion plan for codeupipe — from pipeline framework to full-stack production accelerator.

The guiding principle: **zero to production in moments.** Every ring we add should shrink the distance between an idea and a running, monitored, monetizable system.

---

## Where We Are

```
Ring 1  Ship           ████████████  v0.1.0  ✅
Ring 2  Compose        ████████████  v0.2.0  ✅
Ring 3  Execute        ████████████  v0.3.0  ✅
Ring 4  Observe        ████████████  v0.4.0  ✅
Ring 5  Distribute     ████████████  v0.4.0  ✅
Ring 6  Govern         ████████████  v0.5.0  ✅  (no tag — bundled into v0.4.0 release)
Ring 7  Accelerate     ████████████  v0.7.0  ✅
Ring 8  Connect        ████████████  v0.8.0  ✅
Ring 9  Marketplace    ████████████  v0.9.0  ✅  ← YOU ARE HERE
Ring 10 ???            ░░░░░░░░░░░░          next
```

**1326 core tests + 31 connector tests = 1357 total. 59 doc refs verified. Zero external dependencies in core.**

---

## Completed Rings

### Ring 1 — Ship ✅ (v0.1.0)

Automated release pipeline. Push to main, tag, publish to PyPI.

- CI workflow (Python 3.9–3.13 matrix, pytest, lint)
- Release workflow (tag `v*` → build → publish to PyPI)
- `cup` CLI with 9 commands (scaffold, lint, bundle, coverage, report, doc-check, run)
- `cup:ref` doc verification system + pre-commit hook enforcement

### Ring 2 — Compose ✅ (v0.2.0)

Name-based component catalog and config-driven pipeline assembly.

- `Registry` — register, get, discover, `cup_component` decorator
- `Pipeline.from_config()` — build pipelines from TOML/JSON configs
- `cup run` — execute config-driven pipelines from CLI
- AST-based auto-discovery of filter/tap/hook/stream-filter components

### Ring 3 — Execute ✅ (v0.3.0)

Execution modes, parallelism, nesting, and resilience.

- `run_sync()` — synchronous convenience (no manual `asyncio.run()`)
- `add_parallel()` — fan-out/fan-in with `asyncio.gather`
- `add_pipeline()` — nest pipelines as steps, arbitrary depth
- `with_retry()` / `with_circuit_breaker()` — pipeline-level resilience
- Full config support for parallel, nesting, retry, and circuit breaker

### Ring 4 — Observe ✅ (v0.4.0)

Know what your pipeline is doing without instrumenting every filter by hand.

- **Timing middleware** — automatic per-step duration tracking in `State.timings`
- **Payload lineage** — trace ID and step lineage propagate through Payload operations
- **Structured event emitter** — `PipelineEvent` / `EventEmitter` with `pipeline.on()` / `pipeline.off()`
- Events: `pipeline.start`, `pipeline.end`, `step.start`, `step.end`, `step.error`, `pipeline.retry`, `circuit.open`
- **`pipeline.describe()`** — machine-readable tree of pipeline structure
- **State diffing** — `state.diff(other)` compares two pipeline runs
- Config-driven: `"pipeline": { "observe": { "timing": true, "lineage": true } }`

### Ring 5 — Distribute ✅ (v0.4.0)

Cross-process and network boundaries without changing pipeline logic.

- **Payload serialization** — `payload.serialize()` / `Payload.deserialize()` (JSON)
- **RemoteFilter** — HTTP-based filter that sends payloads to remote services (stdlib urllib)
- **Checkpoint + CheckpointHook** — persist payload state for crash recovery
- **Source adapters** — `IterableSource`, `FileSource` for `pipeline.stream()`
- **WorkerPool** — thread/process pool for CPU-bound work inside filters

### Ring 6 — Govern ✅ (v0.5.0)

Guarantees at the pipeline level — shape, time, rate, and failure policy.

- **PayloadSchema** — shape validation with key presence + type checking, `PayloadSchema.keys()` shorthand
- **Pipeline contracts** — `pipeline.require_input()` / `pipeline.guarantee_output()` for pre/post conditions
- **Schema validation** — `pipeline.require_input_schema()` / `pipeline.guarantee_output_schema()` on run boundaries
- **Timeout policies** — `pipeline.with_timeout(seconds=5)` with clean cancellation via `PipelineTimeoutError`
- **Rate limiting** — `pipeline.with_rate_limit(calls_per_second=10)` token-bucket throttle
- **Dead letter handling** — `pipeline.with_dead_letter(handler)` routes failures to `DeadLetterHandler`
- **Audit trail** — `AuditTrail` + `AuditHook` for immutable transformation logging, `pipeline.enable_audit()`
- **LogDeadLetterHandler** — built-in dead letter collector for testing and debugging
- Events: `pipeline.timeout`, `dead_letter`
- Config-driven: `timeout`, `rate_limit`, `require_input`, `guarantee_output`, `dead_letter`

### Ring 7 — Accelerate ✅ (v0.7.0)

Zero to production. Intent → scaffold → deploy.

- `codeupipe.deploy` package — `DeployAdapter` protocol, `DeployTarget` metadata, adapter discovery via entry points
- `DockerAdapter` — Dockerfile, entrypoint, requirements.txt (auto-detects http/worker/cli mode)
- `VercelAdapter` / `NetlifyAdapter` — serverless handler wrappers + frontend scaffolding
- `cup.toml` manifest parser — project metadata, deploy target, dependencies
- Recipe engine — `resolve_recipe()` with `${variable}` substitution, 5 bundled templates (saas-signup, api-crud, etl, ai-chat, webhook-handler)
- `cup init` project scaffolding — 4 templates (saas, api, etl, chatbot), generates cup.toml, pyproject.toml, pipelines/, filters/, tests/, CI workflow, README
- CLI: `cup deploy`, `cup recipe`, `cup init`

### Ring 8 — Connect ✅ (v0.8.0)

Connector protocol — standardized way to wire external services into pipelines.

- `ConnectorConfig` — parse `[connectors.*]` from cup.toml, env-var resolution
- `discover_connectors()` — entry-point discovery + auto-registration into Registry
- `check_health()` — pre-flight health checks for all registered connectors
- `HttpConnector` — built-in REST connector (stdlib urllib, zero deps)
- CLI: `cup connect --list`, `cup describe <connector>`, `--json` global flag

### Ring 9 — Marketplace ✅ (v0.9.0)

Connector discoverability + first four production connectors.

- **Marketplace infrastructure:**
  - `codeupipe.marketplace` package — `fetch_index`, `search`, `info`, `MarketplaceError`
  - JSON index with cache (1hr TTL, stale-on-error fallback), `CUP_MARKETPLACE_URL` env override
  - CLI: `cup marketplace search|info|install` with `--json` support
  - Trust tiers: verified (✅) / community (🔷)
  - `marketplace/index.json` — static index with 4 verified entries

- **First-party connectors** (each a standalone PyPI package in `connectors/`):

  | Package | Filters | SDK |
  |---|---|---|
  | `codeupipe-google-ai` | generate, generate_stream, embed, vision | google-genai |
  | `codeupipe-stripe` | checkout, subscription, webhook, customer | stripe |
  | `codeupipe-postgres` | query, execute, transaction, bulk_insert | psycopg |
  | `codeupipe-resend` | email, template | resend |

- 40 marketplace tests + 31 connector tests = 71 new tests

---

## What's Next — Open Directions

Everything below is **unscheduled**. These are the natural next moves given what exists, not commitments. Pick what creates the most value and build it.

### Harden & Ship (v1.0 candidate)

The framework has 9 rings, 1357 tests, and a connector ecosystem. A v1.0 signals stability.

| Work | What It Means |
|---|---|
| **API stability audit** | Lock down public interfaces — breaking changes are versioned after this |
| **Documentation site** | Real docs (mkdocs/sphinx), not just INDEX.md. Tutorials, API reference, connector authoring guide |
| **PyPI presence for connectors** | Actually publish codeupipe-google-ai, codeupipe-stripe, etc. to PyPI |
| **Integration test suite** | Real SDK calls against sandbox accounts (Stripe test mode, Resend test domain, etc.) |
| **Error message polish** | Every user-facing error should guide them to the fix |

### Expand the Connector Catalog

More connectors follow the exact same pattern. Each is an independent package.

| Category | Candidates |
|---|---|
| **AI** | Anthropic, Ollama, Hugging Face |
| **Payments** | PayPal, LemonSqueezy |
| **Auth** | Auth0, Clerk, Supabase Auth, Firebase Auth, JWT validation |
| **Email** | SendGrid, Postmark, SES, Mailgun |
| **Storage** | S3, GCS, Azure Blob, Supabase Storage |
| **Database** | MySQL, SQLite, DynamoDB, MongoDB |
| **Cache** | Redis, Memcached |
| **Search** | Algolia, Meilisearch, Elasticsearch |
| **Notifications** | Twilio (SMS), Pusher, OneSignal |

### Cloud Deploy Adapters

The deploy protocol exists (Ring 7). These are new adapters plugging into it.

| Adapter | What It Does |
|---|---|
| **AWS Lambda** | Pipeline → Lambda handler + SAM/CDK template |
| **AWS ECS/Fargate** | Long-running/streaming pipelines → task definition |
| **Azure Functions** | Pipeline → Azure Function trigger |
| **Azure Container Apps** | Streaming pipelines → ACA deployment |
| **GCP Cloud Run** | Pipeline → containerized Cloud Run service |
| **Fly.io / Railway** | Indie/startup speed deploys |

### Developer Experience

| Feature | What It Does |
|---|---|
| **`cup studio`** | Visual pipeline builder — local web UI or VS Code extension |
| **Pipeline hub** | Shareable pipeline configs: `cup install recipe-name` |
| **Organization registries** | Private Registry servers for enterprise teams |
| **Richer recipes** | Recipes that auto-resolve connector dependencies from the marketplace |

### Polyglot Runtime (Long-term)

Write pipeline configs once, run them in any language. The codeuchain vision.

| Feature | What It Does |
|---|---|
| **Wire protocol spec** | Language-agnostic Payload/Filter/Pipeline serialization spec |
| **TypeScript runtime** | Edge/serverless (Cloudflare Workers, Deno Deploy, Vercel Edge) |
| **Rust runtime** | Native-speed executor for performance-critical workloads |
| **Go runtime** | Concurrent executor for infrastructure-heavy deployments |
| **Cross-runtime orchestration** | Python filters + Rust filters + Go filters in one pipeline |
| **WASM filter support** | Compile filters to WebAssembly, run in any runtime |

---

## Architecture Snapshot (v0.9.0)

```
codeupipe/
├── core/           Ring 1-4   Payload, Filter, Tap, Hook, StreamFilter, Valve,
│                              Pipeline, State, Event, Govern
├── distribute/     Ring 5     RemoteFilter, Checkpoint, Source, WorkerPool
├── deploy/         Ring 7     Adapters (Docker, Vercel, Netlify), Recipes, Init
├── connect/        Ring 8     ConnectorConfig, discover_connectors, HttpConnector
├── marketplace/    Ring 9     fetch_index, search, info, marketplace CLI
├── linter/         Ring 1     Dogfooded lint/coverage/doc-check pipelines
├── converter/      Ring 2     Config pipeline assembly helpers
├── registry.py     Ring 2     Registry, cup_component, default_registry
├── testing.py      Ring 1     run_filter, run_pipeline, assert_payload, mock_filter
└── cli.py          Ring 1+    14 commands: new, list, bundle, lint, coverage,
                               report, doc-check, run, deploy, recipe, init,
                               connect, describe, marketplace

connectors/                    Ring 9 — standalone PyPI packages
├── codeupipe-google-ai/       4 filters (generate, stream, embed, vision)
├── codeupipe-stripe/          4 filters (checkout, subscription, webhook, customer)
├── codeupipe-postgres/        4 filters (query, execute, transaction, bulk_insert)
└── codeupipe-resend/          2 filters (email, template)
```

---

## Principles

### What We Will NOT Build

- **Not a scheduler.** Airflow/Prefect/Dagster schedule tasks. codeupipe is the logic *inside* the task.
- **Not a message broker.** Kafka/RabbitMQ move messages. codeupipe *consumes from* them via source adapters.
- **Not an ORM.** Database filters are thin wrappers, not a query builder.
- **Not a web framework.** Flask/FastAPI serve HTTP. codeupipe pipelines are the handler logic behind a route.
- **Zero-dep core, always.** Connectors have their SDK deps. The core stays pure Python, zero dependencies, Python 3.9+.

### What We Always Do

- Every ring is tested, documented, and shipped before the next starts.
- `cup doc-check` + `cup lint` enforced by pre-commit hook.
- Trust but verify — tests hit real services where possible, mocks where necessary.
- Each ring builds on the previous. No skipping.
