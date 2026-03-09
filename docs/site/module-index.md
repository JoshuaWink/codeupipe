# codeupipe — Index

Quick-reference map of the project. Every path listed here is verified by `cup doc-check`.

---

## Docs

| Document | Purpose |
|----------|---------|
| [Home](index.md) | Quick-start, install, examples |
| [Concepts](concepts.md) | Full API reference with runnable examples |
| [Best Practices](best-practices.md) | Project structure, naming, testing strategy |
| [Module Index](module-index.md) | This file — project map |

---

## Package Structure

<!-- cup:ref file=codeupipe/__init__.py hash=3053319 -->
```
codeupipe/
├── __init__.py              # Public API re-exports
├── py.typed                 # PEP 561 typed marker
│
├── core/                    # Primitives
│   ├── payload.py           # Payload, MutablePayload
│   ├── filter.py            # Filter Protocol
│   ├── stream_filter.py     # StreamFilter Protocol
│   ├── pipeline.py          # Pipeline orchestrator + from_config()
│   ├── valve.py             # Valve — conditional gate
│   ├── tap.py               # Tap Protocol — observation
│   ├── state.py             # State — execution metadata
│   ├── hook.py              # Hook ABC — lifecycle
│   ├── event.py             # PipelineEvent, EventEmitter
│   └── govern.py            # Schemas, contracts, audit, dead-letter
│
├── connect/                 # Service connectors (Ring 8)
│   ├── config.py            # ConnectorConfig, load_connector_configs
│   ├── discovery.py         # discover_connectors, check_health
│   └── http.py              # HttpConnector — built-in REST connector
│
├── deploy/                  # Deployment adapters (Ring 7)
│   ├── adapter.py           # DeployTarget, DeployAdapter ABC
│   ├── discovery.py         # find_adapters
│   ├── docker.py            # DockerAdapter
│   ├── handlers.py          # Serverless handler renderers
│   ├── init.py              # cup init scaffolding
│   ├── manifest.py          # cup.toml manifest — load & validate
│   ├── netlify.py           # NetlifyAdapter
│   ├── recipe.py            # Recipes — list, resolve, dependencies
│   └── vercel.py            # VercelAdapter
│
├── distribute/              # Distributed execution (Ring 7a)
│   ├── checkpoint.py        # Checkpoint, CheckpointHook
│   ├── remote.py            # RemoteFilter
│   ├── source.py            # IterableSource, FileSource
│   └── worker.py            # WorkerPool
│
├── runtime.py               # TapSwitch, HotSwap — zero-downtime production control
│
├── auth/                    # OAuth2 integration (browser-based login, credential persistence)
│   ├── credential.py        # Credential, CredentialStore
│   ├── provider.py          # AuthProvider, GoogleOAuth, GitHubOAuth
│   ├── hook.py              # AuthHook
│   └── _server.py           # Local OAuth callback server
│
├── registry.py              # Registry, cup_component, default_registry
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
└── cli/                     # CLI package — registry-routed command dispatch
    ├── __init__.py          # Thin main() + backward-compat re-exports
    ├── __main__.py          # python -m codeupipe.cli entry
    ├── _registry.py         # CommandRegistry — routes command name → handler
    ├── _templates.py        # 9 component template strings
    ├── _scaffold.py         # scaffold engine, name utils, composed builder
    ├── _bundle.py           # bundle engine
    └── commands/            # One module per command group
        ├── scaffold_cmds.py # new, list
        ├── analysis_cmds.py # lint, coverage, report, doc-check
        ├── run_cmds.py      # run, describe, graph, runs
        ├── deploy_cmds.py   # deploy, recipe, init, ci
        ├── connect_cmds.py  # connect, marketplace
        ├── project_cmds.py  # test, doctor, upgrade, publish, version, bundle
        ├── distribute_cmds.py # distribute checkpoint/remote/worker
        └── auth_cmds.py     # auth login/status/revoke/list
```
<!-- /cup:ref -->

---

## Core Types

<!-- cup:ref file=codeupipe/core/__init__.py hash=6ed16dd -->
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

## Govern (Ring 6)

<!-- cup:ref file=codeupipe/core/event.py symbols=PipelineEvent,EventEmitter hash=d106174 -->
<!-- cup:ref file=codeupipe/core/govern.py symbols=SchemaViolation,ContractViolation,PipelineTimeoutError,PayloadSchema,AuditEntry,AuditTrail,AuditHook,DeadLetterHandler,LogDeadLetterHandler hash=f98fbce -->
| Type | Source | Role |
|------|--------|------|
| `PipelineEvent` | core/event.py | Typed event emitted by pipelines |
| `EventEmitter` | core/event.py | Pub/sub event bus |
| `PayloadSchema` | core/govern.py | Declarative payload validation |
| `SchemaViolation` | core/govern.py | Schema check failure |
| `ContractViolation` | core/govern.py | Pre/post-condition failure |
| `PipelineTimeoutError` | core/govern.py | Timeout exceeded |
| `AuditEntry` / `AuditTrail` | core/govern.py | Immutable audit log |
| `AuditHook` | core/govern.py | Hook that records audit entries |
| `DeadLetterHandler` | core/govern.py | Failed-payload routing ABC |
| `LogDeadLetterHandler` | core/govern.py | Dead-letter → logger |
<!-- /cup:ref -->
<!-- /cup:ref -->

---

## Deploy (Ring 7)

<!-- cup:ref file=codeupipe/deploy/__init__.py hash=0cf43d2 -->
<!-- cup:ref file=codeupipe/deploy/adapter.py symbols=DeployTarget,DeployAdapter hash=fb707c9 -->
<!-- cup:ref file=codeupipe/deploy/discovery.py symbols=find_adapters hash=2057718 -->
<!-- cup:ref file=codeupipe/deploy/docker.py symbols=DockerAdapter hash=bb3410f -->
<!-- cup:ref file=codeupipe/deploy/handlers.py symbols=render_vercel_handler,render_netlify_handler,render_lambda_handler hash=33fb03d -->
<!-- cup:ref file=codeupipe/deploy/init.py symbols=init_project,list_templates hash=381c944 -->
<!-- cup:ref file=codeupipe/deploy/manifest.py symbols=ManifestError,load_manifest hash=717235e -->
<!-- cup:ref file=codeupipe/deploy/netlify.py symbols=NetlifyAdapter hash=5659642 -->
<!-- cup:ref file=codeupipe/deploy/render.py symbols=RenderAdapter hash=c94da8d -->
<!-- cup:ref file=codeupipe/deploy/fly.py symbols=FlyAdapter -->
<!-- cup:ref file=codeupipe/deploy/railway.py symbols=RailwayAdapter -->
<!-- cup:ref file=codeupipe/deploy/cloudrun.py symbols=CloudRunAdapter -->
<!-- cup:ref file=codeupipe/deploy/koyeb.py symbols=KoyebAdapter -->
<!-- cup:ref file=codeupipe/deploy/apprunner.py symbols=AppRunnerAdapter -->
<!-- cup:ref file=codeupipe/deploy/oracle.py symbols=OracleAdapter -->
<!-- cup:ref file=codeupipe/deploy/azure_container_apps.py symbols=AzureContainerAppsAdapter -->
<!-- cup:ref file=codeupipe/deploy/huggingface.py symbols=HuggingFaceAdapter -->
<!-- cup:ref file=codeupipe/deploy/recipe.py symbols=RecipeError,list_recipes,resolve_recipe hash=6e84b7a -->
<!-- cup:ref file=codeupipe/deploy/vercel.py symbols=VercelAdapter hash=33ddeb5 -->
| Type | Source | Role |
|------|--------|------|
| `DeployTarget` | deploy/adapter.py | Enum — docker, vercel, netlify, lambda |
| `DeployAdapter` | deploy/adapter.py | ABC — `prepare()`, `deploy()` |
| `find_adapters` | deploy/discovery.py | Auto-discover platform adapters |
| `DockerAdapter` | deploy/docker.py | Docker build + push |
| `VercelAdapter` | deploy/vercel.py | Vercel deployment |
| `NetlifyAdapter` | deploy/netlify.py | Netlify deployment |
| `RenderAdapter` | deploy/render.py | Render free-tier deployment |
| `FlyAdapter` | deploy/fly.py | Fly.io edge deployment |
| `RailwayAdapter` | deploy/railway.py | Railway deployment |
| `CloudRunAdapter` | deploy/cloudrun.py | Google Cloud Run |
| `KoyebAdapter` | deploy/koyeb.py | Koyeb free-tier deployment |
| `AppRunnerAdapter` | deploy/apprunner.py | AWS App Runner |
| `OracleAdapter` | deploy/oracle.py | Oracle Cloud Always Free VM |
| `AzureContainerAppsAdapter` | deploy/azure_container_apps.py | Azure Container Apps |
| `HuggingFaceAdapter` | deploy/huggingface.py | Hugging Face Spaces |
| `render_*_handler` | deploy/handlers.py | Serverless entry-point renderers |
| `init_project` | deploy/init.py | `cup init` scaffolding |
| `load_manifest` | deploy/manifest.py | Parse & validate cup.toml |
| `list_recipes` / `resolve_recipe` | deploy/recipe.py | Recipe system |
<!-- /cup:ref -->
<!-- /cup:ref -->
<!-- /cup:ref -->
<!-- /cup:ref -->
<!-- /cup:ref -->
<!-- /cup:ref -->
<!-- /cup:ref -->
<!-- /cup:ref -->
<!-- /cup:ref -->
<!-- /cup:ref -->

---

## Distribute (Ring 7a)

<!-- cup:ref file=codeupipe/distribute/__init__.py hash=59ccacc -->
<!-- cup:ref file=codeupipe/distribute/checkpoint.py symbols=Checkpoint,CheckpointHook hash=c982735 -->
<!-- cup:ref file=codeupipe/distribute/remote.py symbols=RemoteFilter hash=b17b607 -->
<!-- cup:ref file=codeupipe/distribute/source.py symbols=IterableSource,FileSource hash=192a21a -->
<!-- cup:ref file=codeupipe/distribute/worker.py symbols=WorkerPool hash=362b51b -->
| Type | Source | Role |
|------|--------|------|
| `Checkpoint` / `CheckpointHook` | distribute/checkpoint.py | Save/resume pipeline progress |
| `RemoteFilter` | distribute/remote.py | Execute a filter on a remote worker |
| `IterableSource` / `FileSource` | distribute/source.py | Stream data into pipelines |
| `WorkerPool` | distribute/worker.py | Multi-process execution pool |
<!-- /cup:ref -->
<!-- /cup:ref -->
<!-- /cup:ref -->
<!-- /cup:ref -->
<!-- /cup:ref -->

---

## Connect (Ring 8)

<!-- cup:ref file=codeupipe/connect/__init__.py hash=5c80122 -->
<!-- cup:ref file=codeupipe/connect/config.py symbols=ConfigError,ConnectorConfig,load_connector_configs hash=693d3be -->
<!-- cup:ref file=codeupipe/connect/discovery.py symbols=discover_connectors,check_health hash=e9fe17c -->
<!-- cup:ref file=codeupipe/connect/http.py symbols=HttpConnector hash=2bf804b -->
| Type | Source | Role |
|------|--------|------|
| `ConnectorConfig` | connect/config.py | Parse `[connectors.*]` from cup.toml |
| `load_connector_configs` | connect/config.py | Load all connector configs |
| `discover_connectors` | connect/discovery.py | Entry-point discovery + registration |
| `check_health` | connect/discovery.py | Pre-flight health checks |
| `HttpConnector` | connect/http.py | Built-in REST connector (urllib, zero deps) |
<!-- /cup:ref -->
<!-- /cup:ref -->
<!-- /cup:ref -->
<!-- /cup:ref -->

---

## Marketplace (Ring 9)

<!-- cup:ref file=codeupipe/marketplace/__init__.py hash=4dc7675 -->
<!-- cup:ref file=codeupipe/marketplace/index.py symbols=fetch_index,search,info,MarketplaceError hash=c05c5ff -->
| Type | Source | Role |
|------|--------|------|
| `fetch_index` | marketplace/index.py | Fetch & cache marketplace JSON index |
| `search` | marketplace/index.py | Keyword + category/provider search |
| `info` | marketplace/index.py | Package detail lookup by name or provider |
| `MarketplaceError` | marketplace/index.py | Marketplace-specific error |
<!-- /cup:ref -->
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

<!-- cup:ref file=codeupipe/testing.py symbols=run_filter,run_pipeline,assert_payload,assert_keys,assert_state,mock_filter hash=65f0296 -->
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

<!-- cup:ref file=codeupipe/cli/__init__.py symbols=main hash=4691a2f -->
<!-- cup:ref file=codeupipe/cli/__main__.py hash=eec6b5b -->
<!-- cup:ref file=codeupipe/cli/_registry.py symbols=CommandRegistry hash=8e82ece -->
<!-- cup:ref file=codeupipe/cli/_templates.py hash=c43b99a -->
<!-- cup:ref file=codeupipe/cli/_scaffold.py symbols=scaffold,COMPONENT_TYPES hash=1f62e60 -->
<!-- cup:ref file=codeupipe/cli/_bundle.py symbols=bundle hash=9a1b776 -->
<!-- cup:ref file=codeupipe/cli/commands/__init__.py symbols=setup_all hash=1f2d6ed -->
<!-- cup:ref file=codeupipe/cli/commands/scaffold_cmds.py hash=f410919 -->
<!-- cup:ref file=codeupipe/cli/commands/analysis_cmds.py symbols=lint,coverage,report,doc_check hash=9d54f93 -->
<!-- cup:ref file=codeupipe/cli/commands/run_cmds.py hash=1dbf404 -->
<!-- cup:ref file=codeupipe/cli/commands/deploy_cmds.py hash=de213f2 -->
<!-- cup:ref file=codeupipe/cli/commands/connect_cmds.py hash=973b453 -->
<!-- cup:ref file=codeupipe/cli/commands/project_cmds.py hash=6bad64b -->
<!-- cup:ref file=codeupipe/cli/commands/distribute_cmds.py hash=8cb53eb -->
<!-- cup:ref file=codeupipe/cli/commands/auth_cmds.py hash=a0df015 -->
| Command | Purpose |
|---------|---------||
| `cup new <type> <name> [path]` | Scaffold component + test |
| `cup list` | Show component types |
| `cup bundle <path>` | Generate `__init__.py` re-exports |
| `cup lint <path>` | Check CUP conventions |
| `cup coverage <path>` | Map test coverage |
| `cup report <path>` | Health report |
| `cup doc-check [path]` | Doc freshness check |
| `cup run <config>` | Execute a pipeline from config (TOML/JSON) |
| `cup run --record <config>` | Execute + persist run record |
| `cup connect --list/--health` | List connectors / run health checks |
| `cup describe <config>` | Inspect pipeline inputs, outputs, steps |
| `cup test [path]` | Smart test runner (markers, coverage) |
| `cup doctor [path]` | Project health diagnostics |
| `cup runs` | Show recent pipeline run history |
| `cup upgrade [path]` | Regenerate scaffolded files to latest templates |
| `cup publish <dir>` | Validate & build for publishing |
| `cup graph <config>` | Mermaid pipeline visualization |
| `cup version [--bump]` | Show/bump semver from pyproject.toml |
| `cup distribute checkpoint <path>` | Manage payload checkpoints (save/load/clear/status) |
| `cup distribute remote <url>` | Test a remote filter endpoint |
| `cup distribute worker` | Show worker pool configuration |
| `cup auth login <provider>` | Browser-based OAuth2 login |
| `cup auth status <provider>` | Show credential status |
| `cup auth revoke <provider>` | Remove stored credentials |
| `cup auth list` | List all stored providers |
| `--json` (global) | Machine-readable JSON output |
<!-- /cup:ref -->
<!-- /cup:ref -->
<!-- /cup:ref -->
<!-- /cup:ref -->
<!-- /cup:ref -->
<!-- /cup:ref -->
<!-- /cup:ref -->
<!-- /cup:ref -->
<!-- /cup:ref -->
<!-- /cup:ref -->
<!-- /cup:ref -->
<!-- /cup:ref -->
<!-- /cup:ref -->
<!-- /cup:ref -->
<!-- /cup:ref -->

---

## Observability

<!-- cup:ref file=codeupipe/observe.py symbols=CaptureTap,MetricsTap,RunRecord,save_run_record,load_run_records,export_captures_for_testing hash=6d340cf -->
| Export | Role |
|--------|------|
| `CaptureTap` | Tap that records payload snapshots for replay |
| `MetricsTap` | Tap that counts invocations and timestamps |
| `RunRecord` | Serializable pipeline run summary |
| `save_run_record` | Persist run record to `.cup/runs/` |
| `load_run_records` | Load recent run records |
| `export_captures_for_testing` | Generate pytest fixtures from captures |
<!-- /cup:ref -->

---

## Doctor

<!-- cup:ref file=codeupipe/doctor.py symbols=diagnose hash=36b8d51 -->
| Export | Role |
|--------|------|
| `diagnose` | Run 6 project health checks (manifest, CI, tests, lint, connectors, docs) |
<!-- /cup:ref -->

---

## Upgrade

<!-- cup:ref file=codeupipe/upgrade.py symbols=upgrade_project hash=681ba08 -->
| Export | Role |
|--------|------|
| `upgrade_project` | Regenerate CI/README to latest templates |
<!-- /cup:ref -->

---

## Graph

<!-- cup:ref file=codeupipe/graph.py symbols=pipeline_to_mermaid,render_graph hash=0b11399 -->
| Export | Role |
|--------|------|
| `pipeline_to_mermaid` | Convert pipeline config to Mermaid flowchart |
| `render_graph` | Load config file and generate diagram |
<!-- /cup:ref -->

---

## Runtime (Zero-Downtime Control)

<!-- cup:ref file=codeupipe/runtime.py symbols=TapSwitch,HotSwap -->
| Export | Role |
|--------|------|
| `TapSwitch` | Toggle observation taps on/off at runtime without restarting |
| `HotSwap` | Atomically replace the active Pipeline from a new config file |
<!-- /cup:ref -->

---

## Auth (OAuth2 Integration)

<!-- cup:ref file=codeupipe/auth/__init__.py hash=85c76a2 -->
<!-- cup:ref file=codeupipe/auth/credential.py symbols=Credential,CredentialStore hash=c430594 -->
<!-- cup:ref file=codeupipe/auth/provider.py symbols=AuthProvider,GoogleOAuth,GitHubOAuth hash=88a42c5 -->
<!-- cup:ref file=codeupipe/auth/hook.py symbols=AuthHook hash=f2144d0 -->
<!-- cup:ref file=codeupipe/auth/_server.py symbols=run_oauth_flow hash=ae07f5c -->
<!-- cup:ref file=codeupipe/auth/proxy_token.py symbols=ProxyToken hash=686c997 -->
<!-- cup:ref file=codeupipe/auth/token_ledger.py symbols=LedgerEvent,TokenLedger hash=f6cd6dd -->
<!-- cup:ref file=codeupipe/auth/token_vault.py symbols=TokenVault hash=dfd347f -->
<!-- cup:ref file=codeupipe/auth/vault_hook.py symbols=VaultHook hash=899f08a -->
| Export | Role |
|--------|------|
| `Credential` | Token container with expiry tracking and serialization |
| `CredentialStore` | File-backed JSON persistence with auto-refresh |
| `AuthProvider` | ABC for OAuth2 flows (authorize, exchange, refresh) |
| `GoogleOAuth` | Google OAuth2 provider (all Google API scopes) |
| `GitHubOAuth` | GitHub OAuth2 provider |
| `AuthHook` | Pipeline hook that injects credentials before execution |
| `run_oauth_flow` | Browser-based OAuth2 callback server |
| `ProxyToken` | Opaque `cup_tok_*` reference — never exposes real credentials |
| `LedgerEvent` | Audit event (issued / resolved / revoked) with timestamp |
| `TokenLedger` | Append-only audit trail for proxy token lifecycle |
| `TokenVault` | Central authority — issues, resolves, and revokes proxy tokens |
| `VaultHook` | Pipeline hook that injects proxy tokens instead of raw credentials |
<!-- /cup:ref -->
<!-- /cup:ref -->
<!-- /cup:ref -->
<!-- /cup:ref -->
<!-- /cup:ref -->
<!-- /cup:ref -->
<!-- /cup:ref -->
<!-- /cup:ref -->
<!-- /cup:ref -->

---

## Registry (Composability Layer)

<!-- cup:ref file=codeupipe/registry.py symbols=Registry,cup_component,default_registry hash=5af5cbd -->
| Export | Role |
|--------|------|
| `Registry` | Name → component catalog with `register()`, `get()`, `discover()` |
| `cup_component` | Decorator — register a class with auto-name and auto-kind detection |
| `default_registry` | Module-level singleton Registry |
| `Pipeline.from_config()` | Build a Pipeline from a `.toml` or `.json` config file |
<!-- /cup:ref -->

---

## Tests

1844 tests across 60+ files. Full suite: `pytest`

---

*Maintained via `cup doc-check` — if a referenced file changes, the marker hash drifts and CI catches it.*
