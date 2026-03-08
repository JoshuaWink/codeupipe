---
applyTo: '**/*.md'
description: 'cup:ref documentation markers — format, placement, and freshness verification via cup doc-check'
---

# cup:ref Documentation Markers

## Purpose

Keep docs in sync with code. Markers are invisible HTML comments in markdown that declare which source file (and optionally which symbols/hash) a doc section references. `cup doc-check` verifies them.

## Marker Format

```html
<!-- cup:ref file=path/to/module.py symbols=ClassName,function_name hash=abc1234 -->
Documentation that references the above source code...
<!-- /cup:ref -->
```

### Attributes

| Attribute | Required | Description |
|-----------|----------|-------------|
| `file=` | **Yes** | Relative path from project root to source file |
| `symbols=` | No | Comma-separated names to verify via AST. Supports dotted: `State.executed` |
| `hash=` | No | First 7 chars of SHA256 of file contents at last sync |

## Examples

### Symbol-only (verify names exist, no drift detection)
```html
<!-- cup:ref file=codeupipe/core/state.py symbols=State -->
The `State` class tracks execution metadata...
<!-- /cup:ref -->
```

### Hash-only (detect file changes, no symbol check)
```html
<!-- cup:ref file=codeupipe/cli.py hash=001e289 -->
The CLI supports `cup new`, `cup lint`, and `cup doc-check`...
<!-- /cup:ref -->
```

### Full (both checks)
```html
<!-- cup:ref file=codeupipe/testing.py symbols=run_filter,assert_payload hash=7f2a1bc -->
Use `run_filter` and `assert_payload` from `codeupipe.testing`...
<!-- /cup:ref -->
```

## Getting the Hash

```bash
python3 -c "import hashlib, pathlib; print(hashlib.sha256(pathlib.Path('codeupipe/testing.py').read_bytes()).hexdigest()[:7])"
```

## Verification

```bash
cup doc-check .          # Human-readable output
cup doc-check . --json   # Machine-readable for CI
```

Exit code 0 = all refs current. Exit code 1 = stale refs found.

## What Gets Checked

1. **File exists** — does the referenced `file=` path resolve?
2. **Symbols exist** — AST-parsed; top-level names + `Class.member` dotted paths
3. **Hash matches** — SHA256[:7] of current file vs stored hash; mismatch = drift

## When to Add Markers

- Code examples in docs that reference real source
- Architecture docs describing specific modules
- API reference sections tied to particular classes/functions
- Any doc section that would go stale when the referenced code changes
