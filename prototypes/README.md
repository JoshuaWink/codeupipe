# Prototypes

Rapid prototyping space with full access to codeupipe internals.

> **This directory is release-safe.** All prototype project folders are
> git-ignored and excluded from packaging. Only this README and the
> `_template/` scaffold are tracked by the CUP repo.

## Quick Start

```bash
# 1. Create a new prototype from the template
cp -r prototypes/_template prototypes/acme-dashboard

# 2. Work inside it — codeupipe is importable because you're in the monorepo
cd prototypes/acme-dashboard
python pipeline.py

# 3. When ready, ship to the customer's GitHub repo
./ship.sh customer-org/acme-dashboard          # private (default)
./ship.sh customer-org/acme-dashboard --public  # or public
```

## Why This Exists

| Goal | How |
|------|-----|
| **Short CUP patch loop** | Prototypes import codeupipe from source — edit a filter, re-run, done |
| **Release isolation** | `.gitignore` + `pyproject.toml` exclude ensure nothing leaks |
| **Customer delivery** | Each prototype is its own git repo, pushed via `gh` CLI |
| **Clean monorepo** | Customer code never appears in CUP's git history |

## Rules

1. **Never force-add** a prototype folder (`git add -f prototypes/foo` = bad)
2. **One folder per customer/project** — keeps things clean
3. **Secrets stay in `.env`** — the template includes `.env` in its own `.gitignore`
4. **Delete when delivered** — once pushed to customer repo, remove the local copy

## Template Contents

```
_template/
  cup.toml          # Project manifest (name, deploy target)
  pipeline.py       # Starter pipeline using codeupipe
  ship.sh           # One-command delivery → customer GitHub repo
  .env.example      # Environment variable template
  .gitignore        # Ignores .env, __pycache__, credentials
  requirements.txt  # Customer-facing deps (codeupipe + extras)
```
