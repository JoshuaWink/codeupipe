# codeupipe Roadmap

The expansion plan for codeupipe — from pipeline framework to full-stack production accelerator.

The guiding principle: **zero to production in moments.** Every ring we add should shrink the distance between an idea and a running, monitored, monetizable system.

---

## Completed Rings

### Ring 1 — Ship ✅ (v0.1.0)

Automated release pipeline. Push to main, tag, publish to PyPI.

- CI workflow (Python 3.9–3.13 matrix, pytest, lint)
- Release workflow (tag `v*` → build → publish to PyPI)
- `cup` CLI with 9 commands (scaffold, lint, bundle, coverage, report, doc-check, run)
- `cup:ref` doc verification system

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

---

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

---

### Ring 7 — Accelerate ✅ (v0.6.0)

**Goal:** Zero to production. A developer (or agent) expresses intent; codeupipe assembles, deploys, connects, and monitors the system.

**Implemented (Ring 7a — Foundation):**
- `codeupipe.deploy` package — `DeployAdapter` protocol, `DeployTarget` metadata, adapter discovery via entry points
- `DockerAdapter` — built-in adapter generating Dockerfile, entrypoint, requirements.txt (auto-detects http/worker/cli mode)
- `cup.toml` manifest parser — project metadata, deploy target, dependencies
- Recipe engine — `resolve_recipe()` with `${variable}` substitution, 5 bundled templates (saas-signup, api-crud, etl, ai-chat, webhook-handler)
- `cup init` project scaffolding — 4 templates (saas, api, etl, chatbot), generates cup.toml, pyproject.toml, pipelines/, filters/, tests/, CI workflow, README
- CLI: `cup deploy`, `cup recipe`, `cup init` commands
- 67 new tests (1204 total)

**Designed (future phases):**

#### Infrastructure Scaffolding

| Feature | Description |
|---|---|
| **`cup deploy`** | One command to deploy a pipeline to a cloud target. `cup deploy aws`, `cup deploy azure`, `cup deploy fly`. Detects the pipeline config, generates infra, deploys. |
| **AWS Lambda adapter** | Wrap any Pipeline as a Lambda handler. `cup deploy aws-lambda pipeline.json` generates the handler, SAM/CDK template, and deploys. |
| **AWS ECS/Fargate adapter** | For long-running or streaming pipelines. Generates Dockerfile + task definition. |
| **Azure Functions adapter** | Same pattern — wrap Pipeline as an Azure Function trigger. |
| **Azure Container Apps adapter** | Streaming/long-running pipelines on ACA. |
| **GCP Cloud Run adapter** | Pipeline → containerized Cloud Run service. |
| **Fly.io / Railway adapters** | For indie/startup speed. `cup deploy fly` and you're live. |

#### Service Connectors (Contrib Filters)

Pre-built, tested, registry-discoverable filters for common services:

| Filter Pack | Services |
|---|---|
| **`codeupipe-payments`** | Stripe (checkout, subscriptions, webhooks, invoicing), PayPal, LemonSqueezy |
| **`codeupipe-auth`** | Auth0, Clerk, Supabase Auth, Firebase Auth, JWT validation |
| **`codeupipe-email`** | SendGrid, Resend, Postmark, SES, Mailgun |
| **`codeupipe-storage`** | S3, GCS, Azure Blob, R2, Supabase Storage |
| **`codeupipe-database`** | PostgreSQL, MySQL, SQLite, DynamoDB, Supabase, PlanetScale |
| **`codeupipe-cache`** | Redis, Memcached, DynamoDB DAX |
| **`codeupipe-search`** | Algolia, Meilisearch, Elasticsearch, Typesense |
| **`codeupipe-ai`** | OpenAI, Anthropic, Ollama, Hugging Face, LangChain bridge |
| **`codeupipe-cms`** | Contentful, Sanity, Strapi, Notion API |
| **`codeupipe-analytics`** | Mixpanel, PostHog, Amplitude, Segment |
| **`codeupipe-notifications`** | Twilio (SMS), Pusher, OneSignal, Firebase Cloud Messaging |
| **`codeupipe-files`** | CSV, Excel, Parquet, PDF parse, image resize, video transcode |

#### Rapid Composition Recipes

Pre-built pipeline configs for common business workflows:

```bash
# SaaS signup flow — validate, create user, send welcome email, start trial
cup recipe saas-signup --auth clerk --email resend --payments stripe

# E-commerce checkout — cart validation, payment, inventory update, confirmation
cup recipe checkout --payments stripe --email sendgrid --db postgres

# Content pipeline — CMS webhook → transform → CDN purge → notify
cup recipe content-publish --cms contentful --storage s3 --notifications pusher

# AI chatbot — input sanitize → LLM call → safety filter → response format
cup recipe ai-chat --ai openai --safety moderate --output json

# Data ETL — extract from API, transform, load to warehouse
cup recipe etl --source rest-api --transform json --sink postgres
```

Each recipe is a TOML/JSON pipeline config + the filter dependencies. `cup recipe` writes the config, discovers or installs the filters, and optionally deploys.

#### Project Bootstrapping

```bash
# Full-stack SaaS in one command
cup init saas my-app \
  --frontend next \
  --api codeupipe \
  --auth clerk \
  --payments stripe \
  --db supabase \
  --deploy vercel+aws-lambda

# Generates:
#   my-app/
#   ├── frontend/          (Next.js scaffold)
#   ├── api/
#   │   ├── pipelines/     (signup, checkout, webhook handlers)
#   │   ├── filters/       (auth, payment, db filters)
#   │   └── pipeline.toml  (composable config)
#   ├── infra/             (CDK/Terraform for AWS Lambda)
#   ├── .github/workflows/ (CI + deploy)
#   └── cup.toml           (project manifest)
```

---

### Ring 8 — Ecosystem

**Goal:** Community-driven growth. Other people build and share filters, pipelines, and tools.

| Feature | Description |
|---|---|
| **`codeupipe-contrib`** | Curated collection of common filters — community-reviewed, well-tested, registry-discoverable. |
| **Plugin protocol** | Formal extension points via Python entry points. Custom step types, serializers, executors, deploy targets. |
| **Pipeline hub** | Shareable pipeline configs. `cup install recipe-name` pulls a config + resolves filter dependencies. |
| **`cup studio`** | Visual pipeline builder — local web UI or VS Code extension. Drag filters, connect them, export config. Non-developers can build pipelines. |
| **Template marketplace** | Full project templates (SaaS, API, data pipeline, chatbot) that teams can fork and customize. |
| **Organization registries** | Private Registry servers for enterprise teams. `cup login org.registry.io` + `cup discover --registry org`. |

---

### Ring 9 — Polyglot Runtime

**Goal:** Write pipeline configs once, run them in any language. The codeuchain vision fully realized.

| Feature | Description |
|---|---|
| **Wire protocol spec** | Formal specification for Payload serialization, Filter invocation, Pipeline execution. Language-agnostic. |
| **Rust runtime** | Native-speed Pipeline executor that reads the same .toml/.json configs. For performance-critical production workloads. |
| **Go runtime** | Concurrent Pipeline executor for infrastructure-heavy deployments. |
| **TypeScript runtime** | For edge/serverless (Cloudflare Workers, Deno Deploy, Vercel Edge). |
| **Cross-runtime orchestration** | A pipeline where some filters run in Python, some in Rust, some in Go. The orchestrator handles serialization and dispatch transparently. |
| **WASM filter support** | Filters compiled to WebAssembly run in any runtime. Write once in Rust/Go, use everywhere. |

---

## Late Game — Platform Vision (Years 3–5+)

```
                              ┌──────────────────┐
                              │    cup studio     │
                              │   (visual IDE)    │
                              └────────┬─────────┘
                                       │
                     ┌─────────────────┼─────────────────┐
                     │                 │                 │
               ┌─────┴─────┐   ┌──────┴──────┐   ┌─────┴─────┐
               │  Pipeline  │   │  Template    │   │  Recipe    │
               │  Hub       │   │  Market      │   │  Library   │
               └─────┬─────┘   └──────┬──────┘   └─────┬─────┘
                     │                 │                 │
                     └─────────────────┼─────────────────┘
                                       │
                              ┌────────┴─────────┐
                              │ Pipeline Config   │
                              │ (.toml / .json)   │
                              └────────┬─────────┘
                                       │
               ┌───────────────────────┼───────────────────────┐
               │                       │                       │
         ┌─────┴─────┐         ┌──────┴──────┐         ┌─────┴─────┐
         │ Python RT  │         │  Rust RT    │         │  TS RT    │
         │ (core)     │         │  (perf)     │         │  (edge)   │
         └─────┬─────┘         └──────┬──────┘         └─────┴─────┘
               │                       │                       │
               └───────────────────────┼───────────────────────┘
                                       │
         ┌─────────────────────────────┼─────────────────────────────┐
         │                             │                             │
   ┌─────┴─────┐               ┌──────┴──────┐              ┌──────┴──────┐
   │ AWS        │               │ Azure       │              │ Fly/Railway │
   │ Lambda/ECS │               │ Functions   │              │ Edge        │
   └───────────┘               │ Container   │              └─────────────┘
                               └─────────────┘
```

### The Compounding Moat

1. **Config portability** — a pipeline config works across runtimes and clouds
2. **Registry network effects** — every filter anyone writes is discoverable and reusable
3. **Visual accessibility** — non-developers build pipelines in `cup studio`, developers debug them
4. **Institutional documentation** — pipeline configs *are* the system documentation
5. **Rapid deployment** — `cup deploy` eliminates the infra gap between idea and production
6. **Service connectors** — pre-built integrations with every major service mean you wire, not build

### What We Will NOT Build

Equally important — the boundaries that keep the core sharp:

- **Not a scheduler.** Airflow/Prefect/Dagster schedule tasks. codeupipe is the logic *inside* the task.
- **Not a message broker.** Kafka/RabbitMQ move messages. codeupipe *consumes from* them via source adapters.
- **Not an ORM.** Database filters are thin wrappers, not a query builder.
- **Not a web framework.** Flask/FastAPI serve HTTP. codeupipe pipelines are the handler logic behind a route.
- **Zero-dep core, always.** Every ring beyond 3 is an optional extra. The core stays pure Python, zero dependencies, Python 3.9+.

---

## Timeline

| Phase | Rings | Version | Focus |
|---|---|---|---|
| **Foundation** | 1–3 | v0.1–v0.3 | Core framework, CLI, composability, execution modes |
| **Production** | 4–5 | v0.4 | Observability, distribution, serialization |
| **Enterprise** | 6–7 | v0.5–v1.0 | Governance, deployment adapters, service connectors |
| **Community** | 8 | v1.x | Contrib, plugins, hub, visual tooling |
| **Platform** | 9 | v2.x | Multi-language runtimes, cross-runtime orchestration |

Each ring builds on the previous. No ring is started until the prior ring is tested, documented, and shipped.
