# codeupipe — Best Practices

Practical guidance for structuring, naming, and organizing CUP projects.
These are recommendations, not hard rules — adapt them to your team's needs.

---

## Table of Contents

1. [Project Structure](#project-structure)
2. [Naming Conventions](#naming-conventions)
3. [File Organization](#file-organization)
4. [Pipeline Composition](#pipeline-composition)
5. [Testing Strategy](#testing-strategy)
6. [CLI Workflow](#cli-workflow)
7. [Linter Rules](#linter-rules)

---

## Project Structure

### Feature-Folder Layout (Recommended)

Group components by domain feature. Each feature folder contains its filters, taps, hooks, and a pipeline that wires them:

```
src/
  signup/
    validate_email.py        # Filter
    hash_password.py         # Filter
    save_user.py             # AsyncFilter
    send_welcome.py          # AsyncFilter
    audit_log.py             # Tap
    error_handler.py         # Hook
    signup_pipeline.py       # Pipeline (wires everything)
    __init__.py              # cup bundle → re-exports
  checkout/
    validate_cart.py
    calc_total.py
    charge_payment.py
    checkout_pipeline.py
    __init__.py
tests/
  test_validate_email.py
  test_hash_password.py
  test_signup_pipeline.py
  ...
```

**Why:** Feature folders keep related components together. When you work on "signup", everything is in one place. The pipeline file acts as the wiring diagram for the feature.

### Type-Folder Layout (Alternative)

Group by component type. Works well for small projects or shared utility libraries:

```
src/
  filters/
    validate_email.py
    hash_password.py
    calc_total.py
    __init__.py
  taps/
    audit_log.py
    __init__.py
  hooks/
    error_handler.py
    __init__.py
  pipelines/
    signup_pipeline.py
    checkout_pipeline.py
    __init__.py
```

**Why:** Familiar pattern for developers coming from MVC/layered architectures. Easy to find "all filters" at a glance.

**Tradeoff:** When folders already convey the type, you don't need suffixes in filenames (`filters/validate_email.py` is clearly a filter). But cross-referencing across folders requires more navigation.

### Flat Layout (Small Projects)

For scripts, prototypes, or projects with <10 components, a flat layout with type suffixes is the clearest:

```
src/
  validate_email_filter.py
  hash_password_filter.py
  audit_log_tap.py
  error_handler_hook.py
  signup_pipeline.py
  __init__.py
```

**Why:** No folder overhead. The suffix tells you what each file does instantly. Works great for tutorials, demos, and quick experiments.

---

## Naming Conventions

### Files: `snake_case.py`

Always use `snake_case` for file names. The linter enforces this as **CUP007**.

```
✓ validate_email.py
✓ hash_password.py
✓ signup_pipeline.py
✗ ValidateEmail.py
✗ hashPassword.py
```

### Classes: `PascalCase`

Class names match the file name converted to PascalCase:

```python
# validate_email.py
class ValidateEmail:
    def call(self, payload): ...

# signup_pipeline.py
def build_signup_pipeline() -> Pipeline: ...
```

### Pipeline Step Names: `snake_case`

When adding components to a pipeline, the step name should match the file name:

```python
pipeline.add_filter(ValidateEmail(), "validate_email")
pipeline.add_filter(HashPassword(), "hash_password")
pipeline.add_tap(AuditLog(), "audit_log")
```

### Type Suffixes: Optional but Strategic

Type suffixes in file names (`_filter`, `_tap`, `_hook`, `_pipeline`) are **not required** but are recommended in these situations:

| Situation | Recommendation | Example |
|---|---|---|
| Feature folder | **Skip** suffixes — the pipeline file is the exception | `signup/validate_email.py` |
| Type folder | **Skip** suffixes — the folder is the type | `filters/validate_email.py` |
| Flat layout | **Use** suffixes — they're your only type signal | `validate_email_filter.py` |
| Pipelines (always) | **Use** `_pipeline` suffix | `signup_pipeline.py` |
| Ambiguous names | **Use** suffix for clarity | `audit_log_tap.py` vs `audit_log_filter.py` |

**Pipeline files should always have the `_pipeline` suffix** regardless of folder structure. This makes them instantly recognizable as the wiring diagram versus a single component.

### Payload Keys: `snake_case`

All data flowing through the pipeline uses `snake_case` keys:

```python
payload.insert("user_email", "test@test.com")
payload.get("hashed_password")
```

### Builder Functions: `build_<name>_pipeline()`

Pipeline factory functions follow the `build_` prefix convention:

```python
def build_signup_pipeline() -> Pipeline: ...
def build_checkout_pipeline() -> Pipeline: ...
def build_lint_pipeline() -> Pipeline: ...
```

---

## File Organization

### One Component Per File

The linter enforces this as **CUP001**. Each file should contain exactly one CUP component (Filter, Tap, Hook, StreamFilter) or one pipeline builder function.

```
✓ validate_email.py    → class ValidateEmail (Filter)
✓ audit_log.py         → class AuditLog (Tap)
✓ signup_pipeline.py   → def build_signup_pipeline()

✗ helpers.py           → class ValidateEmail + class HashPassword  (CUP001 violation)
```

**Why:** One-per-file enables clean `cup bundle` re-exports, precise `cup lint` diagnostics, and atomic git blame.

### Use `cup bundle` for Clean Imports

After creating components in a directory, run `cup bundle <path>` to generate an `__init__.py` with re-exports:

```bash
cup bundle src/signup
```

This gives you clean imports:

```python
from src.signup import ValidateEmail, HashPassword, build_signup_pipeline
```

### Keep Test Files Paired

Every component file should have a corresponding test file. The linter checks this as **CUP002**.

```
src/signup/validate_email.py  →  tests/test_validate_email.py
src/signup/audit_log.py       →  tests/test_audit_log.py
```

---

## Pipeline Composition

### Use `--steps` for Composed Pipelines

When scaffolding a pipeline that wires together existing components:

```bash
cup new pipeline signup_flow src/signup \
  --steps validate_email hash_password save_user:async-filter \
         send_welcome:async-filter audit_log:tap error_handler:hook
```

This generates both the pipeline file and a test file with the correct wiring.

### Pipeline as Wiring, Not Logic

Pipelines should **only** wire components together. Business logic belongs in individual filters:

```python
# ✓ Good: pipeline is pure wiring
def build_signup_pipeline() -> Pipeline:
    pipeline = Pipeline()
    pipeline.add_filter(ValidateEmail(), "validate_email")
    pipeline.add_filter(HashPassword(), "hash_password")
    pipeline.add_tap(AuditLog(), "audit_log")
    return pipeline

# ✗ Bad: logic mixed into pipeline construction
def build_signup_pipeline() -> Pipeline:
    pipeline = Pipeline()
    pipeline.add_filter(ValidateEmail(min_length=5, require_tld=True), ...)  # config is OK
    # Don't put if/else branching or data manipulation here
    return pipeline
```

### Immutable Payload Flow

Payload is immutable. Each filter receives a payload, returns a **new** payload with additions:

```python
class HashPassword:
    def call(self, payload: Payload) -> Payload:
        raw = payload.get("password")
        hashed = hashlib.sha256(raw.encode()).hexdigest()
        return payload.insert("hashed_password", hashed)
```

Use `.with_mutation()` only when performance requires in-place edits (batch processing, large data).

---

## Testing Strategy

### Three Tiers

1. **Unit tests** — Test each filter in isolation with mock data
2. **Integration tests** — Test the composed pipeline with synthetic data
3. **End-to-end tests** — Test with real services and verify outcomes

<!-- cup:ref file=codeupipe/testing.py symbols=run_filter,run_pipeline,assert_payload,assert_state hash=65f0296 -->

### Unit Test Pattern

Use `codeupipe.testing` for zero-boilerplate tests:

```python
from codeupipe.testing import run_filter, assert_payload

class TestValidateEmail:
    def test_valid_email_passes(self):
        result = run_filter(ValidateEmail(), {"email": "user@example.com"})
        assert_payload(result, email_valid=True)

    def test_invalid_email_raises(self):
        with pytest.raises(ValueError):
            run_filter(ValidateEmail(), {"email": "not-an-email"})
```

### Integration Test Pattern

```python
from codeupipe.testing import run_pipeline, assert_state

class TestSignupPipeline:
    def test_full_flow(self):
        pipeline = build_signup_pipeline()
        result, state = run_pipeline(pipeline, {
            "email": "user@test.com",
            "password": "secret123",
        }, return_state=True)
        assert result.get("user_id") is not None
        assert_state(state, executed=["validate_email", "hash_password"])
```

<!-- /cup:ref -->

---

## CLI Workflow

### Typical Development Cycle

```bash
# 1. Scaffold components
cup new filter validate_email src/signup
cup new filter hash_password src/signup
cup new tap audit_log src/signup
cup new hook error_handler src/signup

# 2. Compose into a pipeline
cup new pipeline signup_flow src/signup \
  --steps validate_email hash_password audit_log:tap error_handler:hook

# 3. Bundle for clean imports
cup bundle src/signup

# 4. Lint to catch issues
cup lint src/signup

# 5. Check coverage
cup coverage src/signup

# 6. Health report
cup report src/signup

# 7. Run tests
pytest tests/ -v
```

### Available Commands

<!-- cup:ref file=codeupipe/cli.py symbols=main,scaffold,bundle,lint,coverage,report,doc_check hash=06e39dd -->

| Command | Purpose |
|---|---|
| `cup new <type> <name> [path]` | Scaffold a component with test |
| `cup new pipeline <name> [path] --steps ...` | Scaffold a composed pipeline |
| `cup list` | Show available component types |
| `cup bundle <path>` | Generate `__init__.py` re-exports |
| `cup lint <path>` | Check for standards violations |
| `cup coverage <path>` | Map test coverage for components |
| `cup report <path>` | Health report with scores, orphans, staleness |
| `cup doc-check [path]` | Verify doc freshness (cup:ref markers) |
| `cup run <config>` | Execute a pipeline from a TOML/JSON config |

<!-- /cup:ref -->

---

## Linter Rules

<!-- cup:ref file=codeupipe/linter/lint_pipeline.py symbols=build_lint_pipeline hash=ccff493 -->

## Summary of Linter Rules

| Rule | Severity | What it checks |
|---|---|---|
| **CUP000** | error | Syntax error in file |
| **CUP001** | error | Multiple components in one file |
| **CUP002** | warning | Missing test file |
| **CUP003** | error | Filter missing `call()` |
| **CUP004** | error | Tap missing `observe()` |
| **CUP005** | error | StreamFilter missing `stream()` |
| **CUP006** | error | Hook missing lifecycle methods |
| **CUP007** | warning | File name not `snake_case` |
| **CUP008** | warning | Stale `__init__.py` bundle |

<!-- /cup:ref -->
