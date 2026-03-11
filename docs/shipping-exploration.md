# Shipping to Production: Where We Are, Where We're Going

**Date**: 2026-03-10  
**Status**: Exploration / RFC  
**Author**: Orchestrate LLC

---

## The Core Insight

Most web applications are **static shells that make API calls**. The app isn't the HTML/JS/CSS — it's the data and the compute behind the API. The shell is a commodity.

This means:

| Layer | Where It Lives | Cost |
|---|---|---|
| **Static shell** (HTML/JS/CSS) | GitHub Pages — public repo, free | $0 |
| **Dynamic data** | API calls to serverless OR OCI free tier | $0 – minimal |
| **Secrets / Auth** | Environment variables on compute layer only | Protected |

**The code being public doesn't matter.** Obfuscated/minified JS in a public repo reveals nothing meaningful. The value is in the **data**, the **API keys**, and the **business logic running server-side**. GitHub Pages handles 90% of our hosting needs for free.

For the other 10% — the compute — we either go serverless (AWS Lambda, Vercel Functions, Cloudflare Workers) or run on an always-on instance (Oracle Cloud free tier: 4 ARM cores, 24 GB RAM — enough for dozens of lightweight Python backends).

This collapses the shipping problem from "12 adapters for 7 product types" into two tiers:

1. **Static shell** → GitHub Pages (free, instant, zero ops)
2. **Compute backend** → OCI free tier (always-on) or serverless (per-request)

---

## The Problem Statement

Getting code from "it works on my machine" to "a customer is using it" is still too many steps. We've built a powerful framework — 10 rings, 1846 tests, marketplace, connectors, deploy adapters — but the last mile is still friction.

The question: **Can `cup ship` be the last command you type?**

---

## Where We Are Today

### What Exists

| Capability | CLI Command | Status |
|---|---|---|
| Scaffold a project | `cup init saas my-app --frontend react` | ✅ Works |
| Generate Docker artifacts | `cup deploy docker cup.toml` | ✅ Works |
| Generate Vercel artifacts | `cup deploy vercel cup.toml` | ✅ Works |
| Generate Netlify artifacts | `cup deploy netlify cup.toml` | ✅ Works |
| Generate Render blueprint | `cup deploy render cup.toml` | ✅ Works |
| Generate Fly.io config | `cup deploy fly cup.toml` | ✅ Works |
| Generate Railway config | `cup deploy railway cup.toml` | ✅ Works |
| Generate Cloud Run config | `cup deploy cloudrun cup.toml` | ✅ Works |
| Generate CI workflow | `cup init ... --ci github` | ✅ Works (14 CI providers) |
| Ship prototype to customer | `./ship.sh org/repo` | ✅ Works (manual) |
| Install marketplace components | `cup marketplace install <name>` | ✅ Works |

### What's Missing

The existing `cup deploy` **generates** artifacts. It does not **deploy** them. After `cup deploy render cup.toml`, you still need to:

1. Push to a GitHub repo
2. Log into Render/Vercel/Fly dashboard
3. Connect the repo
4. Set environment variables manually
5. Wait for build
6. Verify the URL

That's 6 steps of human-driven context switching. It's not hard, but it's not `cup ship` either.

### The Prototype Pattern

Our three prototypes reveal the current "ship" workflow:

| Prototype | Type | How You Ship It |
|---|---|---|
| `google-auth` | CLI + browser flow | `./ship.sh acme-corp/google-auth` → pushes to customer GitHub repo |
| `vault-manager` | Local web UI (server + SPA) | `./ship.sh acme-corp/vault-ui` → pushes to customer GitHub repo |
| `social-login` | Local web UI (server + SPA) | `./ship.sh acme-corp/social-login` → pushes to customer GitHub repo |

The `ship.sh` pattern is clever — it isolates the prototype from the monorepo, creates a fresh git repo, and pushes to the customer's GitHub. But it's still:

- **Manual** — you run a bash script
- **Git-only** — no actual deployment to a running environment
- **No secrets** — customer still has to create `.env` from `.env.example`
- **No health check** — no verification that it's actually running

---

## The Two-Tier Architecture: Static Shell + API Backend

### Why This Works

Look at our existing prototypes. `social-login` is a 706-line `index.html` that makes `fetch()` calls to `/api/*`. The server is 638 lines of Python. The SPA could run *anywhere* — it has zero server-side rendering, zero build step, zero dependencies. It's pure client-side JavaScript talking to a REST API.

This is already the pattern. We just haven't recognized it as the *default* shipping architecture.

```
┌──────────────────────────────────────────┐
│            GitHub Pages (free)           │
│  ┌────────────────────────────────────┐  │
│  │    Static HTML/JS/CSS (public)     │  │
│  │    • Minified / obfuscated         │  │
│  │    • Zero secrets in code          │  │
│  │    • SPA routing via 404.html      │  │
│  └──────────────┬─────────────────────┘  │
└─────────────────┼────────────────────────┘
                  │ fetch("https://api.myapp.com/...")
                  ▼
┌──────────────────────────────────────────┐
│        Compute Backend (private)         │
│  ┌────────────────────────────────────┐  │
│  │  Option A: OCI Free Tier           │  │
│  │  • 4 ARM cores, 24 GB RAM         │  │
│  │  • Always-on, $0/month            │  │
│  │  • Multiple apps via reverse proxy │  │
│  │  • Handles 90% of use cases       │  │
│  ├────────────────────────────────────┤  │
│  │  Option B: Serverless              │  │
│  │  • Vercel Functions / AWS Lambda   │  │
│  │  • Per-request, scale to zero      │  │
│  │  • Better for spiky/unpredictable  │  │
│  └────────────────────────────────────┘  │
│                                          │
│  Secrets live HERE (env vars, vault)     │
│  Business logic lives HERE (codeupipe)   │
│  Data lives HERE (DB, file store)        │
└──────────────────────────────────────────┘
```

### Why Public Repos Are Fine

The static shell is just a UI rendering layer:
- **Minified JS** — unreadable, no intellectual property exposed
- **API endpoints are URLs** — visible in browser devtools anyway
- **Auth tokens are per-session** — not baked into the code
- **Business logic is server-side** — never shipped to the browser

Publishing the shell to a **public** GitHub repo means:
- **Free GitHub Pages hosting** (private repos require Pro or organization)
- **Free CDN** via GitHub's edge network
- **Free SSL** via GitHub's automatic HTTPS
- **Git-based deploys** — `git push` = live in seconds

### Oracle Cloud Free Tier as Default Compute

OCI's Always Free tier is absurdly generous for our use case:

| Resource | Free Tier Allocation |
|---|---|
| Ampere A1 Compute | 4 ARM cores, 24 GB RAM (split across up to 4 VMs) |
| Boot Volume | 200 GB total |
| Object Storage | 20 GB |
| Bandwidth | 10 TB/month outbound |

A single ARM instance running Python backends behind Caddy (auto-SSL reverse proxy) can host **dozens** of lightweight codeupipe apps simultaneously. Each app is a Python process on a different port, Caddy routes by subdomain.

```
api.vault-manager.orchestrate.dev  → localhost:8420
api.social-login.orchestrate.dev   → localhost:8421
api.google-auth.orchestrate.dev    → localhost:8422
```

For apps that don't need always-on compute (webhooks, event handlers, scheduled jobs), serverless is cheaper and simpler. But for most of our prototypes — lightweight Python HTTP servers with minimal traffic — OCI free tier is the obvious choice.

### What This Means for `cup ship`

Instead of 12 deploy adapters each implementing their own `deploy()` method, the happy path becomes:

```bash
cup ship
# 1. Build/minify static assets → push to GitHub Pages repo
# 2. Deploy backend to OCI instance (or serverless target)
# 3. Configure reverse proxy / domain routing
# 4. Set env vars on the compute layer
# 5. Health check the API endpoint
# 6. Done — prints both URLs
```

The 12 adapters still exist for teams that want Render, Fly, Railway, etc. But the *default* path — the one that costs $0 and requires no platform account — is GitHub Pages + OCI.

---

## Product Types We Need to Ship

With the two-tier architecture as our default, "production" becomes much simpler for each product shape:

### 1. Web Application (Backend + Frontend)

**Examples**: SaaS dashboards, admin panels, customer portals  
**Current prototype**: `vault-manager`, `social-login`

**Two-tier approach**:
- **Static shell** → `static/` directory → GitHub Pages (public repo, free)
- **API backend** → `server.py` → OCI free tier or serverless
- HTTPS automatic on both tiers (GitHub Pages + Caddy)
- Secrets live only on the compute layer (`.env` on OCI, env vars on serverless)

**What used to be hard** (provisioning, DNS, SSL, secrets) becomes:
1. `git push` the static shell → live on `myapp.github.io`
2. Deploy the backend to OCI → reverse proxy routes `api.myapp.com`
3. Env vars are set once on the instance, persist across deploys

**Current gap**: We generate Docker/Render artifacts but don't push them. No automated GitHub Pages deploy. No OCI deployment script.

### 2. API Service

**Examples**: REST endpoints, webhook receivers, data pipelines  
**Current prototype**: `google-auth` (partially)

**Two-tier approach**: No static shell needed — this is **compute only**.
- Deploy Python server to OCI free tier (systemd service + Caddy)
- Or deploy as a serverless function (Vercel/Lambda) for spiky workloads

**What "shipped" means**:
- Running on a URL with versioned endpoints
- API key or OAuth2 authentication
- Rate limiting enabled
- Health check endpoint responsive
- Logging and monitoring connected

**Current gap**: `cup deploy` generates the entrypoint server, but it's a bare HTTP server. No auth middleware, no rate limiting in the generated handler. The *pipeline* has these features (Ring 6 — Govern), but the generated *server wrapper* doesn't surface them.

### 3. CLI Tool

**Examples**: Developer tools, data processing scripts, automation  
**Current prototype**: None explicitly, but `cup` itself is one

**What "shipped" means**:
- Installable via `pip install` or `brew install` or downloadable binary
- Entry point registered in `pyproject.toml`
- `--help` and `--version` work
- Published to PyPI or GitHub Releases
- Cross-platform (macOS, Linux, Windows)

**Current gap**: `cup init cli my-tool` scaffolds the project and generates a `pyproject.toml` with an entry point. But there's no `cup ship` that builds a wheel, tests it, and publishes it. No binary bundling (PyInstaller/Nuitka/PyOxidizer). No Homebrew formula generation.

### 4. Desktop Application

**Examples**: Token vault manager (local), developer dashboards  
**Current prototype**: `vault-manager` *is* this, but runs as a local server

**What "shipped" means**:
- `.dmg` on macOS, `.msi` on Windows, `.AppImage` on Linux
- Native window (Tauri, Electron, or system webview)
- Auto-update mechanism
- Code signing for distribution
- No command-line required to launch

**Current gap**: Nothing exists. Our prototypes are "desktop-ish" (local server + browser tab), but they're not real desktop apps. The user has to run `python3 server.py` and open `localhost:8421`. That's fine for developers, terrible for end users.

### 5. Mobile Application

**Examples**: Not our immediate focus, but worth acknowledging

**What "shipped" means**: App store submission, signing, API backend deployed separately.

**Current gap**: Entirely out of scope for now. Mobile frontends would consume codeupipe APIs, not run codeupipe directly.

### 6. Serverless Function

**Examples**: Webhook handlers, event processors, scheduled jobs  
**Current prototype**: None, but `cup deploy vercel` generates serverless handlers

**Two-tier approach**: These *are* the compute tier — no static shell needed.
- Vercel Functions, Cloudflare Workers, or AWS Lambda for truly ephemeral workloads
- Alternatively, a long-running process on OCI with a cron trigger (systemd timer or Python `schedule` library)

**Current gap**: Vercel/Netlify adapters generate handlers but don't deploy them. Lambda adapter generates SAM templates but doesn't `sam deploy`.

### 7. Background Worker / Scheduled Job

**Examples**: Data sync, report generation, cleanup tasks  
**Current prototype**: None, but recipe exists (`scheduled-job`)

**Two-tier approach**: A Python script on OCI with a systemd timer. $0. No Lambda, no CloudWatch, no third-party cron service.

```bash
# On OCI instance:
# /etc/systemd/system/my-job.timer → runs every 6 hours
# /etc/systemd/system/my-job.service → python3 /opt/apps/my-job/run.py
```

**Current gap**: No systemd unit generator. No OCI deployment script. The `scheduled-job` recipe exists but targets Docker, not bare-metal.

---

## The Vision: `cup ship`

### What If

```bash
# One command. That's it.
cup ship
```

Reads `cup.toml`, determines the product type, and applies the two-tier default:

1. **Validates** — checks secrets are set, dependencies are installed, tests pass
2. **Builds** — minifies/obfuscates frontend (if any), bundles backend
3. **Ships static** — pushes `static/` or `dist/` to a GitHub Pages repo (public, free)
4. **Ships compute** — deploys backend to OCI instance (or serverless target)
5. **Routes** — configures reverse proxy (Caddy) to point domain → backend
6. **Verifies** — hits the health endpoint, confirms it's live
7. **Reports** — prints the frontend URL + API URL

### The Default Path vs. Platform Adapters

```
cup ship                                    # → GitHub Pages + OCI (default, $0)
cup ship --target render                    # → Render (paid platform, managed)
cup ship --target fly                       # → Fly.io (paid, edge compute)
cup ship --target vercel --serverless       # → Vercel Functions (serverless)
```

The 12 existing adapters are still there for teams that want managed platforms. But the **default** — the path of least resistance — is free and requires only a GitHub account and an OCI free-tier instance.

### Product Type Detection

`cup.toml` already declares enough to infer the product type:

```toml
# Web app with frontend → static shell + API backend
[frontend]
framework = "vanilla"     # or "react", "vue" — doesn't matter, it's all static at the end
static_dir = "static"     # for SPAs that need no build step

[deploy]
target = "pages+oci"      # default: GitHub Pages for frontend, OCI for backend

# API only → compute only, no static shell
[deploy]
target = "oci"

# CLI tool → PyPI publish
[project]
entry_point = "my_tool.cli:main"

# Desktop app → pywebview bundle
[desktop]
runtime = "webview"
```

### The Ship Pipeline

Here's the elegant part — **`cup ship` is itself a codeupipe pipeline**. Dogfooding all the way down.

```
Payload(cup.toml)
  → ReadManifest         # parse cup.toml
  → DetectProductType    # web | api | cli | desktop | serverless | worker
  → ValidateSecrets      # check .env exists, required keys present
  → RunTests             # pytest -q (fail fast)
  → MinifyFrontend       # uglify/obfuscate static assets (Valve: skip if no frontend)
  → PushToPages          # git push to GitHub Pages repo (Valve: skip if no frontend)
  → DeployBackend        # ssh + rsync to OCI, restart systemd service
  → ConfigureProxy       # update Caddy config for subdomain routing
  → HealthCheck          # GET /health on the API URL, verify 200
  → ReportSuccess        # print both URLs
```

Each step is a Filter. The pipeline uses Valves for conditional steps (skip frontend if API-only). Hooks for timing and audit logging. Taps for progress reporting.

### Progressive Disclosure

Not every user wants the full pipeline. The command should layer:

```bash
# Minimal — just validate and build
cup ship --dry-run

# Normal — deploy to GitHub Pages + OCI (default)
cup ship

# Just the static shell (no backend deploy)
cup ship --frontend-only

# Just the backend (no static deploy)
cup ship --backend-only

# Override target for teams on paid platforms
cup ship --target render

# Ship to a customer's repo (prototype pattern)
cup ship --to acme-corp/my-app
```

---

## Per-Product-Type Breakdown

### Web Applications (Static Shell + API)

**Today**:
```bash
cup deploy docker cup.toml          # generates Dockerfile, compose
docker compose up                   # local only
# then manually: push to GitHub, connect Render, set env vars...
```

**Tomorrow (two-tier default)**:
```bash
cup ship
# → Detects [frontend] + [deploy] → "web application"
# → Minifies/obfuscates static/ directory
# → Pushes to github.com/orchestrate-apps/my-app (public, Pages enabled)
# → ssh + rsync backend to OCI instance
# → Caddy routes api.my-app.orchestrate.dev → localhost:8421
# → Health check: GET /api/health → 200 OK
# → Prints:
#   ✅ Frontend: https://orchestrate-apps.github.io/my-app
#   ✅ API:      https://api.my-app.orchestrate.dev
#   Cost: $0/month
```

**Implementation path**:
1. `PagesToGitHub` filter — creates repo (via `gh` CLI), pushes `static/` or `dist/`
2. `DeployToOCI` filter — `ssh` + `rsync` to OCI instance, restarts systemd service
3. `ConfigureCaddy` filter — appends subdomain → port mapping to Caddyfile
4. `HealthCheck` filter — `GET /api/health`, verify 200
5. GitHub Actions workflow (optional) — auto-redeploy on push to static repo

### API Services

**Today**: Same as web app minus frontend. Works, but no auth layer in generated server.

**Tomorrow (compute-only tier)**:
```bash
cup ship
# → Detects no [frontend] → "API service"
# → ssh + rsync to OCI instance
# → Caddy routes api.my-service.orchestrate.dev → localhost:PORT
# → Health check: GET /health → 200 OK
# → Prints:
#   ✅ API: https://api.my-service.orchestrate.dev
#   Cost: $0/month
```

No static shell. No GitHub Pages. Just compute. The server runs on OCI, Caddy provides SSL and routing.

### CLI Tools

**Today**:
```bash
cup init cli my-tool
# write your filters...
python -m build                     # manual
twine upload dist/*                 # manual PyPI publish
```

**Tomorrow**:
```bash
cup ship
# → Detects [project.entry_point] → "CLI tool"
# → Runs tests
# → Builds wheel + sdist
# → Publishes to PyPI (or GitHub Releases)
# → Prints: ✅ Published my-tool 0.1.0 to PyPI
#           Install: pip install my-tool
```

**Bonus tier** — native binary:
```toml
[cli]
binary = true           # bundle as standalone executable
targets = ["macos-arm64", "macos-x64", "linux-x64"]
```
Uses PyInstaller or Nuitka under the hood. Produces downloadable binaries in `dist/`.

### Desktop Applications

This is the biggest gap and the most interesting opportunity.

**Today**: Prototypes run as `python3 server.py` + open browser. Developer-friendly, user-hostile.

**Tomorrow**:
```toml
[desktop]
runtime = "tauri"
name = "Vault Manager"
icon = "assets/icon.png"
bundle_id = "com.orchestrate.vault-manager"
```

```bash
cup ship
# → Detects [desktop] → "desktop application"
# → Builds the Python backend into a self-contained server
# → Wraps in Tauri/webview shell (native window, no Electron bloat)
# → Code-signs (if certificate configured)
# → Outputs: dist/VaultManager.dmg, dist/VaultManager.msi
```

**Why Tauri over Electron**: Tauri uses the system webview (WebKit on macOS, WebView2 on Windows, WebKitGTK on Linux). Binary is ~5MB vs Electron's ~150MB. Written in Rust, so the shell is fast and tiny. Our Python backend runs as a subprocess, Tauri wraps the UI.

**Architecture**:
```
┌─────────────────────────┐
│   Tauri Native Window   │  ← system webview, ~5MB
├─────────────────────────┤
│    Static HTML/JS/CSS   │  ← our existing SPA (static/)
├─────────────────────────┤
│  Python Backend (bundled)│  ← PyInstaller-frozen server.py
│    └── codeupipe runtime │  ← pipelines, filters, vault, etc.
└─────────────────────────┘
```

**Implementation path**:
1. New adapter: `TauriAdapter` — generates `tauri.conf.json`, Cargo project, sidecar config
2. Sidecar pattern: Tauri launches the Python binary as a sidecar process
3. Frontend: copies `static/` into Tauri's `dist` directory
4. Build: `cargo tauri build` produces `.dmg` / `.msi` / `.AppImage`
5. Auto-update: Tauri's built-in updater with GitHub Releases as the update source

**Alternative — System Webview (lighter)**:
For simpler tools that don't need native menus or notifications, we could use `pywebview` — pure Python, opens a native window with a webview, embeds the server in-process. No Rust toolchain needed.

```bash
pip install pywebview
cup ship --desktop webview
# → Bundles server + static into a PyInstaller binary
# → pywebview opens a native window pointing at the embedded server
# → Single executable, ~30MB, works on all platforms
```

### Serverless Functions

**Today**: `cup deploy vercel cup.toml` generates handler files. Manual push + dashboard connection.

**Tomorrow**:
```bash
cup ship
# → Detects [deploy.target] = "vercel" with no [frontend] → "serverless function"
# → Generates handler
# → vercel deploy --prod (shells out to Vercel CLI)
# → Prints: ✅ Live at https://my-func.vercel.app
```

---

## The `cup ship` Implementation Plan

### Phase 1: GitHub Pages Adapter (days, not weeks)

The static shell is the quickest win. Most of our prototypes already have a `static/` directory that works as-is.

**`PagesAdapter`** — new adapter, ~100 lines:
1. Create (or use existing) public GitHub repo via `gh repo create`
2. Copy `static/` or `dist/` into the repo
3. Optionally minify/obfuscate JS (stdlib + simple regex, or shell out to `terser` if available)
4. `git push` → GitHub Pages auto-deploys
5. Return the live URL: `https://<org>.github.io/<repo>`

```bash
cup ship --frontend-only
# ✅ Pushed static/ to github.com/orchestrate-apps/social-login (public)
# ✅ Live at https://orchestrate-apps.github.io/social-login
# Cost: $0
```

### Phase 2: OCI Compute Adapter (the other half)

**`OCIAdapter`** — new adapter, ~150 lines:
1. `ssh` to the OCI instance (key-based auth, no password)
2. `rsync` the backend code (server.py, requirements.txt, codeupipe, etc.)
3. `pip install -r requirements.txt` on the instance (in a virtualenv)
4. Generate + install a `systemd` service unit for the app
5. Reload Caddy config to add subdomain → port routing
6. `systemctl restart my-app`
7. Health check: `GET https://api.my-app.orchestrate.dev/health`

```bash
cup ship --backend-only
# ✅ Deployed backend to oci-instance-1 (port 8421)
# ✅ Caddy routing: api.social-login.orchestrate.dev → :8421
# ✅ Health check: 200 OK (47ms)
# Cost: $0
```

The Caddy reverse proxy is the key enabler. One Caddyfile, multiple subdomains, automatic HTTPS via Let's Encrypt:

```
api.social-login.orchestrate.dev {
    reverse_proxy localhost:8421
}

api.vault-manager.orchestrate.dev {
    reverse_proxy localhost:8420
}

api.google-auth.orchestrate.dev {
    reverse_proxy localhost:8422
}
```

### Phase 3: Full `cup ship` (Phases 1 + 2 combined)

```bash
cup ship
# → Reads cup.toml
# → Detects [frontend] → ships static to GitHub Pages
# → Detects [deploy] → ships backend to OCI
# → Configures CORS (API allows requests from the Pages domain)
# → Health checks both endpoints
# → Prints summary
```

### Phase 4: Secret Forwarding to OCI

Instead of SSH-ing in and manually creating `.env`:

```bash
cup ship --secrets
# Reads local .env
# scp .env to /opt/apps/my-app/.env on OCI instance
# systemctl restart my-app
```

Or for platform adapters (Render, Fly, etc.):
```bash
cup ship --target render --secrets
# Reads .env, sends to Render API
# Render: PUT /services/{id}/env-groups
```

### Phase 5: Desktop + CLI Publishing

Desktop (pywebview → single executable):
```toml
[desktop]
runtime = "webview"
name = "My App"
```

CLI publishing (PyPI):
```toml
[publish]
target = "pypi"
```

These are the 10% that don't fit the two-tier model. They get their own specialized adapters later.

---

## The End User Experience

### For the Developer (Orchestrate's customer)

```bash
# Start a project
cup init saas my-startup --frontend vanilla --deploy pages+oci

# Write business logic (filters, pipelines)
# ...

# Ship it
cup ship
# ✅ Tests passed (23/23)
# ✅ Static minified (static/ — 127KB)
# ✅ Pushed to github.com/orchestrate-apps/my-startup (public)
# ✅ Frontend live: https://orchestrate-apps.github.io/my-startup
# ✅ Backend deployed to oci-instance-1 (port 8430)
# ✅ Caddy routing: api.my-startup.orchestrate.dev → :8430
# ✅ Secrets synced (.env → /opt/apps/my-startup/.env)
# ✅ Health check: 200 OK (47ms)
# Cost: $0/month
```

### For the End User (developer's customer)

They never see codeupipe. They see:
- A URL that works
- A desktop app that opens
- A CLI tool they `pip install`
- An API they call with an API key

The framework is invisible. That's the goal.

---

## Decision Points

### 1. Should `cup ship` be one command or two?

**Option A**: `cup ship` does everything (validate + build + deploy + verify)  
**Option B**: `cup build` generates artifacts, `cup ship` deploys them

Recommendation: **Option A** with `--dry-run` for safety. One command. The whole point is reducing cognitive overhead.

### 2. Public repo for static shells — is that really okay?

**Yes.** Consider what's in the public repo:
- Minified HTML/JS/CSS — no readable source code
- API endpoint URLs — already visible in browser devtools
- No secrets, tokens, or keys — those live on the compute layer
- No business logic — all server-side

The marketplace SPA is already a public repo on GitHub Pages. The docs site is public. The framework itself is open-source. Static shells are just another public artifact.

For clients who insist on private repos, GitHub Pro/Enterprise works with Pages. But for Orchestrate's own apps, public is the pragmatic default.

### 3. One OCI instance or multiple?

**Start with one.** A 4-core ARM instance with 24GB RAM running Caddy + multiple Python processes is more than enough for dozens of low-traffic apps. When an app outgrows shared hosting, graduate it to its own instance or a paid platform (Render, Fly, etc.).

The Caddy + systemd pattern makes it trivial to add/remove apps:
- Add app: `rsync` code, create `.service` file, add Caddyfile entry, reload
- Remove app: `systemctl stop`, delete files, remove Caddyfile entry, reload

### 4. Which desktop runtime?

| Runtime | Size | Toolchain | Complexity |
|---|---|---|---|
| `pywebview` | ~30MB | Python only | Low — start here |
| Tauri | ~5MB (+ Python sidecar) | Rust + Node | Medium — upgrade path |
| Electron | ~150MB | Node | High — avoid |

Recommendation: **pywebview first**, **Tauri later**. Pywebview is pure Python, works on all platforms, and aligns with our zero-external-dep philosophy. Tauri is the production upgrade when we need native menus, auto-update, and code signing.

### 5. How do we handle secrets?

**Never store secrets in `cup ship` state.** Read from `.env` at ship time, `scp` to the OCI instance's app directory, then forget them. The `.env` file stays local (gitignored). On OCI, the `.env` lives in `/opt/apps/<name>/.env`, readable only by the app's systemd service.

Secrets flow:
```
.env (local, gitignored) → cup ship → scp → /opt/apps/myapp/.env (on OCI) → systemd reads at start
```

For platform adapters (Render, Fly, etc.):
```
.env (local) → cup ship → Platform API (encrypted) → runtime env vars
```

### 6. What about obfuscation?

For the static shell:
- **Minification** (remove whitespace, shorten variable names) — `terser` for JS, inline tool for CSS
- **Path obfuscation** — rename API paths in production (optional, security through obscurity is not real security but does raise the bar)
- **Source maps** — never ship them. Generate for debugging, keep local.

The real security is on the compute layer: proper CORS headers, rate limiting, auth tokens, and never exposing raw business logic client-side.

---

## What This Means for Our Product Surface

Today codeupipe is a **framework**. With `cup ship`, it becomes a **platform CLI** — comparable to `vercel`, `fly`, `railway`, but with a crucial difference: **the default path costs $0**.

The competitive positioning shifts:

| Before | After |
|---|---|
| "A Python pipeline framework" | "Zero to production for Python apps — free" |
| Competes with: Prefect, Dagster | Competes with: Vercel, Railway, Render CLI |
| Deploy: "generate artifacts, figure out the rest" | Deploy: "`cup ship` — live in 30 seconds" |
| Cost: depends on platform | Cost: $0 (GitHub Pages + OCI free tier) |

The framework is the engine. GitHub Pages is the storefront. OCI is the workshop. `cup ship` is the ignition key.

### The 90/10 Split

- **90% of apps**: Static shell (GitHub Pages) + lightweight API (OCI free tier) = $0/month
- **10% of apps**: Heavy compute, real-time, high traffic → graduate to Render/Fly/Railway via `cup ship --target render`

We build for the 90% first. The 10% already works via the existing 12 adapters.

---

## Next Steps

1. **Set up OCI free-tier instance** — install Python 3.9+, Caddy, create `/opt/apps/` directory structure
2. **Build `PagesAdapter`** — `gh repo create` + `git push` to ship static shells
3. **Build `OCIAdapter`** — `ssh` + `rsync` + `systemctl` to ship backends
4. **Add `cup ship` CLI command** — new entry in `deploy_cmds.py`
5. **Ship `social-login` as proof of concept** — static shell on Pages, backend on OCI
6. **Write tests** — mock `ssh`, `gh`, and `rsync` calls; test the full pipeline
7. **Ship it** (yes, use `cup ship` to ship `cup ship`)

---

## Summary

The insight is simple: **most apps are static shells + API calls**. The shell is free (GitHub Pages). The compute is free (OCI). The code being public doesn't matter — the value is in the data and the secrets, which live server-side.

Stop treating every app like it needs its own managed platform. Start treating the static shell as a commodity and the compute as a utility. GitHub Pages + OCI free tier covers 90% of our use cases at $0/month. The other 10% can use paid platforms when they outgrow the free tier.

`cup ship` should make this the path of least resistance.

---

*This document is a living exploration. It will evolve as we build.*
