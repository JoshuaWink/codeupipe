---
applyTo: 'codeupipe/cli/**'
description: 'Pattern for adding new cup CLI subcommands — wrapper function, argparse setup, handler block'
---

# Adding a `cup` Subcommand

## Architecture

The CLI is a registry-routed package under `codeupipe/cli/`:

```
cli/
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

## Three-Step Pattern

### 1. Pick the Right Command Module

Choose (or create) a file in `codeupipe/cli/commands/` by domain. If a new file, add it to `commands/__init__.py`'s `_ALL_MODULES` list.

### 2. Add Parser + Handler + Register

Inside the module's `setup(sub, registry)` function, add the subparser and register the handler:

```python
def setup(sub, registry):
    # ... existing parsers ...

    # cup my-command <path> [--json]
    my_parser = sub.add_parser(
        "my-command",
        help="Short description for --help",
    )
    my_parser.add_argument("path", help="Directory to analyze")
    my_parser.add_argument("--json", action="store_true", dest="json_output")
    registry.register("my-command", _handle_my_command)


def _handle_my_command(args):
    try:
        rpt = my_command(args.path)
        # Format and print output
        # return 0 for success, 1 for issues found
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
```

### 3. (Optional) Wrapper Function for Programmatic API

If the command should be callable without the CLI, add a wrapper function and re-export from `cli/__init__.py`:

```python
def my_command(directory: str) -> dict:
    """One-sentence description.

    Internally delegates to the CUP pipeline (dogfooding).
    """
    import asyncio
    from codeupipe.linter.my_pipeline import build_my_pipeline

    pipeline = build_my_pipeline()
    payload = Payload({"directory": directory})
    result = asyncio.run(pipeline.run(payload))
    return result.get("my_report", {})
```

## Conventions

- **CLI name**: kebab-case (`doc-check`, not `doc_check`)
- **Wrapper function**: snake_case (`doc_check`)
- **Exit codes**: 0 = clean/success, 1 = issues found or error
- **JSON flag**: `--json` with `dest="json_output"` for CI piping
- **Auto-fix flag**: `--auto-fix` for non-interactive batch fixes (AI-agent / CI friendly)
- **Registry**: Always call `registry.register(name, handler)` — no cascading if/elif in `main()`

## Existing Commands

| Command | Module | Wrapper | Pipeline |
|---------|--------|---------|----------|
| `cup lint <path>` | analysis_cmds | `lint()` | `build_lint_pipeline()` |
| `cup coverage <path>` | analysis_cmds | `coverage()` | `build_coverage_pipeline()` |
| `cup report <path>` | analysis_cmds | `report()` | `build_report_pipeline()` |
| `cup doc-check [path]` | analysis_cmds | `doc_check()` | `build_doc_check_pipeline()` |
