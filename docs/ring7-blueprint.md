# Ring 7 — Accelerate: Implementation Blueprint

**Goal:** Zero to production. Express intent → codeupipe assembles, deploys, connects, monitors.

This document is the engineering blueprint for Ring 7. It defines the architecture, interfaces, phasing, and deliverables.

---

## Architecture Decision: Core vs. Contrib

Ring 7 spans two concerns:

| Concern | Lives In | Why |
|---|---|---|
| **Deploy protocol + CLI** | `codeupipe` core | The `DeployAdapter` protocol, `cup deploy`, `cup recipe`, `cup init` are framework-level. Zero external deps. |
| **Cloud adapters** | `codeupipe-deploy-{target}` packages | Each adapter pulls in cloud-specific SDKs (boto3, azure-functions-core-tools, etc.). Separate packages keep core zero-dep. |
| **Service connectors** | `codeupipe-{service}` packages | Each filter pack is its own installable package with its own deps (stripe, openai, etc.). |
| **Recipes** | `codeupipe` core (bundled TOML) or `codeupipe-recipes` | Recipe configs are just TOML files — no deps. Can live in core or a lightweight companion. |

### Zero-Dependency Constraint

codeupipe core remains zero-dep. All external SDK usage lives in adapter/connector packages that users install separately. Core provides:
- The `DeployAdapter` protocol
- The `cup deploy` / `cup recipe` / `cup init` CLI commands
- Recipe template resolution
- Dockerfile and config generation (string templates, no Jinja)

---

## Phase 1: Deploy Protocol + CLI Foundation

### 1.1 DeployAdapter Protocol

```python
# codeupipe/deploy/adapter.py

class DeployTarget:
    """Metadata about a deployment target."""
    name: str           # "aws-lambda", "azure-functions", "fly", etc.
    description: str
    requires: List[str] # pip packages needed: ["boto3", "aws-cdk-lib"]

class DeployAdapter(ABC):
    """Protocol for deployment adapters."""

    @abstractmethod
    def target(self) -> DeployTarget:
        """Return metadata about this deploy target."""

    @abstractmethod
    def validate(self, pipeline_config: dict) -> List[str]:
        """Pre-flight checks. Return list of issues (empty = OK)."""

    @abstractmethod
    def generate(self, pipeline_config: dict, output_dir: Path) -> List[Path]:
        """Generate deployment artifacts (handler, infra, Dockerfile).
        Returns list of generated file paths."""

    @abstractmethod
    def deploy(self, output_dir: Path, *, dry_run: bool = False) -> str:
        """Execute the deployment. Returns deployment URL or status."""
```

### 1.2 Adapter Discovery

Adapters register via Python entry points:

```toml
# In codeupipe-deploy-aws/pyproject.toml
[project.entry-points."codeupipe.deploy"]
aws-lambda = "codeupipe_deploy_aws:LambdaAdapter"
aws-fargate = "codeupipe_deploy_aws:FargateAdapter"
```

Core discovers them:

```python
# codeupipe/deploy/discovery.py
def find_adapters() -> Dict[str, DeployAdapter]:
    """Discover all installed deploy adapters via entry points."""
    # Uses importlib.metadata.entry_points (stdlib)
```

### 1.3 `cup deploy` CLI Command

```bash
# List available targets
cup deploy --list

# Deploy to a target
cup deploy aws-lambda pipeline.toml
cup deploy azure-functions pipeline.toml --dry-run
cup deploy fly pipeline.toml

# With options
cup deploy aws-lambda pipeline.toml --region us-east-1 --memory 256
```

Implementation in `cli.py`:

```python
def _deploy(args):
    target_name = args.target
    config_path = args.config
    dry_run = args.dry_run

    adapters = find_adapters()
    if target_name not in adapters:
        print(f"Unknown target '{target_name}'. Available: {', '.join(adapters)}")
        sys.exit(1)

    adapter = adapters[target_name]
    issues = adapter.validate(config)
    if issues:
        for issue in issues:
            print(f"  ✗ {issue}")
        sys.exit(1)

    generated = adapter.generate(config, output_dir)
    if not dry_run:
        url = adapter.deploy(output_dir)
        print(f"Deployed: {url}")
```

---

## Phase 2: First Adapter — Docker / Generic Container

Before cloud-specific adapters, build the foundational one: **containerized pipeline**.

### 2.1 `DockerAdapter`

Lives in core (no external deps — generates files, doesn't call Docker API):

```python
# codeupipe/deploy/docker.py

class DockerAdapter(DeployAdapter):
    """Generates Dockerfile + entrypoint for any pipeline config."""

    def generate(self, pipeline_config, output_dir):
        # 1. Write entrypoint.py — imports pipeline config, runs it
        # 2. Write Dockerfile — FROM python:3.12-slim, pip install codeupipe + deps
        # 3. Write docker-compose.yml (optional)
        ...
```

Generated structure:
```
deploy/
├── Dockerfile
├── entrypoint.py      # Pipeline runner script
├── pipeline.toml      # Copy of the config
├── requirements.txt   # Extracted from pipeline deps
└── docker-compose.yml # Optional orchestration
```

The `entrypoint.py` generated:
```python
"""Auto-generated pipeline entrypoint."""
from codeupipe import Pipeline, Registry
from codeupipe.registry import default_registry

pipeline = Pipeline.from_config("pipeline.toml", registry=default_registry)
# HTTP mode: wrap as Flask/FastAPI endpoint
# Worker mode: poll source, run pipeline
# CLI mode: read stdin, run pipeline, write stdout
```

### 2.2 Execution Modes

The deploy adapter detects the pipeline shape and generates the right entrypoint:

| Pipeline Shape | Execution Mode | Generated |
|---|---|---|
| Filter chain (batch) | HTTP request handler | FastAPI/Flask endpoint |
| StreamFilter chain | Long-running worker | Process loop with source |
| Timer/schedule config | Cron job | Schedule wrapper |
| Queue trigger config | Message consumer | Queue listener |

---

## Phase 3: Cloud Adapters (separate packages)

### 3.1 `codeupipe-deploy-aws`

```
codeupipe-deploy-aws/
├── pyproject.toml       # deps: boto3, aws-cdk-lib (optional)
├── codeupipe_deploy_aws/
│   ├── __init__.py
│   ├── lambda_adapter.py   # LambdaAdapter — generates handler.py + SAM template
│   ├── fargate_adapter.py  # FargateAdapter — generates Dockerfile + task def
│   └── templates/          # SAM/CDK template strings
```

### 3.2 `codeupipe-deploy-azure`

```
codeupipe-deploy-azure/
├── codeupipe_deploy_azure/
│   ├── functions_adapter.py   # Azure Functions trigger
│   ├── container_adapter.py   # Azure Container Apps
│   └── templates/
```

### 3.3 `codeupipe-deploy-fly`

```
codeupipe-deploy-fly/
├── codeupipe_deploy_fly/
│   ├── fly_adapter.py   # fly.toml generation + flyctl deploy
│   └── templates/
```

---

## Phase 4: `cup recipe` — Composable Workflow Templates

### 4.1 Recipe Format

Recipes are TOML configs with variable slots:

```toml
# recipes/saas-signup.toml
[recipe]
name = "saas-signup"
description = "SaaS signup flow — validate, create user, send welcome, start trial"
variables = ["auth_provider", "email_provider", "payment_provider"]

[pipeline]
name = "signup"

[[pipeline.steps]]
name = "ValidateEmail"
type = "filter"

[[pipeline.steps]]
name = "${auth_provider}CreateUser"
type = "filter"

[[pipeline.steps]]
name = "${email_provider}SendWelcome"
type = "filter"

[[pipeline.steps]]
name = "${payment_provider}StartTrial"
type = "filter"

[pipeline.require_input]
keys = ["email", "password", "plan"]

[pipeline.guarantee_output]
keys = ["user_id", "trial_id"]
```

### 4.2 `cup recipe` CLI

```bash
# List available recipes
cup recipe --list

# Generate a recipe (writes pipeline.toml + installs deps)
cup recipe saas-signup \
  --auth clerk \
  --email resend \
  --payments stripe

# Preview without writing
cup recipe saas-signup --auth clerk --email resend --payments stripe --dry-run
```

### 4.3 Recipe Resolution

```python
def resolve_recipe(recipe_name, variables):
    """Load recipe template, substitute variables, resolve filter deps."""
    template = load_recipe(recipe_name)  # from bundled or installed recipes
    config = substitute(template, variables)
    deps = resolve_dependencies(config)  # which codeupipe-* packages needed
    return config, deps
```

---

## Phase 5: `cup init` — Project Bootstrapping

### 5.1 Project Templates

```bash
cup init saas my-app --auth clerk --payments stripe --db supabase --deploy aws-lambda
cup init api my-api --db postgres --deploy docker
cup init etl my-etl --source rest --sink postgres --deploy aws-fargate
cup init chatbot my-bot --ai openai --deploy fly
```

### 5.2 Generated Structure

```
my-app/
├── cup.toml              # Project manifest (name, version, deploy target, deps)
├── pipelines/
│   ├── signup.toml       # Generated from recipe
│   ├── checkout.toml     # Generated from recipe
│   └── webhook.toml      # Generated from recipe
├── filters/
│   ├── __init__.py
│   └── custom.py         # Placeholder for user's custom filters
├── tests/
│   ├── __init__.py
│   └── test_signup.py    # Generated test scaffold
├── deploy/
│   ├── Dockerfile        # Generated by deploy adapter
│   └── infra/            # CDK/Terraform/SAM templates
├── .github/
│   └── workflows/
│       └── ci.yml        # Generated CI workflow
├── pyproject.toml
└── README.md
```

### 5.3 `cup.toml` — Project Manifest

```toml
[project]
name = "my-app"
version = "0.1.0"

[deploy]
target = "aws-lambda"
region = "us-east-1"

[dependencies]
codeupipe = ">=0.5.0"
codeupipe-auth = { provider = "clerk" }
codeupipe-payments = { provider = "stripe" }
codeupipe-database = { provider = "supabase" }
```

---

## Phase 6: Service Connector Packs (separate repos/packages)

Each connector pack follows the same structure:

```
codeupipe-{service}/
├── pyproject.toml            # deps: service SDK
├── codeupipe_{service}/
│   ├── __init__.py           # cup_component decorators for auto-discovery
│   ├── filters/
│   │   ├── create.py         # e.g., StripeCreateCheckout
│   │   ├── read.py           # e.g., StripeGetPayment
│   │   └── webhook.py        # e.g., StripeWebhookValidate
│   └── hooks/
│       └── logging.py        # Service-specific audit hooks
├── tests/
│   ├── test_create.py
│   └── test_webhook.py
└── README.md
```

### Connector Protocol

All connectors:
1. Use `@cup_component` decorator for Registry auto-discovery
2. Accept config via constructor (API keys from env vars, not hardcoded)
3. Follow the Filter protocol (async `call(payload) -> payload`)
4. Include comprehensive tests (unit + integration with real APIs where possible)

### Priority Order for Connectors

| Priority | Pack | Rationale |
|---|---|---|
| 1 | `codeupipe-ai` | Hottest market, immediate developer demand |
| 2 | `codeupipe-database` | Every app needs data persistence |
| 3 | `codeupipe-auth` | Every SaaS needs auth |
| 4 | `codeupipe-email` | Transactional email is universal |
| 5 | `codeupipe-payments` | Monetization layer |
| 6 | `codeupipe-storage` | File/blob handling |
| 7+ | Rest | Based on community demand |

---

## Implementation Order (What to build when)

### Ring 7a — Foundation (next)
1. `codeupipe/deploy/` package in core — `DeployAdapter` protocol, adapter discovery, `DockerAdapter`
2. `cup deploy` CLI command
3. `cup.toml` manifest parser
4. Tests for all of the above

### Ring 7b — Recipes
5. Recipe template format + resolution engine
6. `cup recipe` CLI command
7. 3-5 bundled recipes (saas-signup, api-crud, etl, ai-chat, webhook-handler)
8. Tests

### Ring 7c — Init
9. Project template engine
10. `cup init` CLI command with template types (saas, api, etl, chatbot)
11. Generated test scaffolds + CI workflows
12. Tests

### Ring 7d — Cloud Adapters (separate packages)
13. `codeupipe-deploy-aws` (Lambda + Fargate)
14. `codeupipe-deploy-azure` (Functions + Container Apps)
15. `codeupipe-deploy-fly`
16. Integration tests with real cloud deployments

### Ring 7e — First Connector Packs (separate packages)
17. `codeupipe-ai` (OpenAI, Anthropic, Ollama)
18. `codeupipe-database` (PostgreSQL, SQLite)
19. `codeupipe-auth` (JWT validation, basic schemes)

---

## Key Design Principles

1. **Config is king.** Everything expressible in TOML/JSON. No code required for standard workflows.
2. **Progressive disclosure.** `cup deploy docker` works with zero config beyond the pipeline. Cloud targets add a few flags.
3. **Fail fast with clear messages.** `cup deploy` validates before generating, validates before deploying.
4. **Adapter isolation.** Cloud SDKs never touch core. Users install only what they need.
5. **Recipe composability.** Recipes are just pipeline configs with variables. Users can fork, edit, and share them.
6. **Entry point discovery.** All adapters and connectors use Python entry points for zero-config registration.

---

## Open Questions for Ring 7a

- **Entrypoint mode detection:** Should we auto-detect (batch vs streaming vs scheduled) or require explicit config?
  - Recommendation: Auto-detect with override. If pipeline has StreamFilters → worker mode. Otherwise → HTTP handler.

- **Secrets management:** How do connectors get API keys?
  - Recommendation: Environment variables with a `[secrets]` section in `cup.toml` that documents which env vars are needed. No secret storage in code or config files.

- **Testing adapters:** How do we test `cup deploy aws-lambda` without an AWS account?
  - Recommendation: Test the generate step (artifact correctness) without deploying. Integration tests in CI use ephemeral cloud resources with cleanup.
