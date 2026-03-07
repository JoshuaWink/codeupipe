"""
codeupipe CLI — scaffold components with zero boilerplate.

Usage:
    cup new <component> <name> [path]
    cup new pipeline <name> [path] --steps step1 step2:type ...
    cup bundle <path>
    cup lint <path>
    cup coverage <path> [--tests-dir DIR]
    cup report <path> [--tests-dir DIR] [--json] [--detail] [--verbose]
    cup doc-check [path] [--json]
    cup run <config> [--discover DIR] [--input JSON] [--json]

Components:
    filter          Filter (sync def call) — Pipeline handles awaiting
    async-filter    Filter (async def call) — native coroutine
    stream-filter   StreamFilter (async def stream → yields 0..N chunks)
    tap             Tap (sync def observe) — Pipeline handles awaiting
    async-tap       Tap (async def observe) — native coroutine
    hook            Lifecycle hook (before/after/on_error)
    valve           Conditional flow control (filter + predicate)
    pipeline        Pipeline orchestrator
    retry-filter    RetryFilter wrapper

Step Types (for --steps):
    name            Defaults to 'filter'
    name:filter     Explicit filter
    name:tap        Observation point
    name:hook       Lifecycle hook
    name:valve      Conditional gate
    name:stream-filter  Streaming (0..N output)

Bundle:
    Scans a directory for codeupipe components and generates
    __init__.py with re-exports for clean imports.

Examples:
    cup new filter validate_email
    cup new filter validate_email src/filters
    cup new pipeline checkout_flow src/pipelines
    cup new pipeline checkout_flow src/pipelines --steps validate_cart calc_total charge_payment
    cup new pipeline data_etl src/pipelines --steps parse:filter fan_out:stream-filter audit:tap
    cup new hook audit_logger src/hooks
    cup new stream-filter log_parser src/streams
    cup bundle src/signup
"""

import argparse
import ast
import os
import re
import sys
from pathlib import Path
from typing import Optional

from codeupipe import Payload


# ── Name Utilities ──────────────────────────────────────────────────

def _to_snake(name: str) -> str:
    """Convert any casing to snake_case."""
    # Insert _ before uppercase runs: 'ValidateEmail' → 'Validate_Email'
    s = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", name)
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s)
    # Replace hyphens/spaces with underscores
    s = re.sub(r"[-\s]+", "_", s)
    return s.lower()


def _to_pascal(snake: str) -> str:
    """Convert snake_case to PascalCase."""
    return "".join(word.capitalize() for word in snake.split("_"))


# ── Templates ───────────────────────────────────────────────────────

_TEMPLATES = {}


def _register(component_type: str, file_template: str, test_template: str):
    _TEMPLATES[component_type] = (file_template, test_template)


# ── Filter (sync) ──

_register("filter", file_template='''\
"""
{class_name}: [describe what this filter does]
"""

from codeupipe import Payload


class {class_name}:
    """
    Filter (sync): [one-line purpose]

    Pipeline._invoke() transparently awaits sync returns,
    so a plain def call() works seamlessly.
    For async I/O (db, http, etc.) use: async def call(...)

    Input keys:
        - [key]: [description]

    Output keys (added):
        - [key]: [description]
    """

    def call(self, payload: Payload) -> Payload:
        # TODO: implement transformation logic
        return payload
''', test_template='''\
"""Tests for {class_name}."""

import asyncio

import pytest

from codeupipe import Payload, Pipeline
from {import_path} import {class_name}


def run(coro):
    return asyncio.run(coro)


class Test{class_name}:
    """Unit tests for {class_name}."""

    def test_happy_path(self):
        result = run(_run_filter({class_name}(), {{}}))
        # TODO: assert expected output keys

    def test_missing_input_key(self):
        result = run(_run_filter({class_name}(), {{}}))
        # TODO: define expected behavior for missing keys


async def _run_filter(f, data):
    p = Pipeline()
    p.add_filter(f, "{snake_name}")
    return await p.run(Payload(data))
''')


# ── Filter (async) ──

_register("async-filter", file_template='''\
"""
{class_name}: [describe what this async filter does]
"""

from codeupipe import Payload


class {class_name}:
    """
    Filter (async): [one-line purpose]

    Native coroutine — use when call() needs await
    (database queries, HTTP calls, file I/O, etc.).
    For pure computation use: def call(...) (sync)

    Input keys:
        - [key]: [description]

    Output keys (added):
        - [key]: [description]
    """

    async def call(self, payload: Payload) -> Payload:
        # TODO: implement async transformation logic
        return payload
''', test_template='''\
"""Tests for {class_name}."""

import asyncio

import pytest

from codeupipe import Payload, Pipeline
from {import_path} import {class_name}


def run(coro):
    return asyncio.run(coro)


class Test{class_name}:
    """Unit tests for {class_name}."""

    def test_happy_path(self):
        f = {class_name}()
        result = run(_run_filter(f, {{}}))
        # TODO: assert expected output keys

    def test_missing_input_key(self):
        f = {class_name}()
        # TODO: define expected behavior for missing keys


async def _run_filter(f, data):
    p = Pipeline()
    p.add_filter(f, "{snake_name}")
    return await p.run(Payload(data))
''')


# ── StreamFilter ──

_register("stream-filter", file_template='''\
"""
{class_name}: [describe what this stream filter does]
"""

from typing import AsyncIterator

from codeupipe import Payload


class {class_name}:
    """
    StreamFilter (async generator): [one-line purpose]

    Yields 0, 1, or N output chunks per input chunk.
    Always async — streaming requires async generators.
    Used with Pipeline.stream() instead of Pipeline.run().

    Input keys:
        - [key]: [description]

    Output keys (yielded):
        - [key]: [description]
    """

    async def stream(self, chunk: Payload) -> AsyncIterator[Payload]:
        # TODO: implement streaming logic
        # yield chunk                  # pass-through (1→1)
        # yield nothing                # drop (1→0)
        # yield chunk1; yield chunk2   # fan-out (1→N)
        yield chunk
''', test_template='''\
"""Tests for {class_name}."""

import asyncio

import pytest

from codeupipe import Payload, Pipeline
from {import_path} import {class_name}


def run(coro):
    return asyncio.run(coro)


async def collect(aiter):
    results = []
    async for item in aiter:
        results.append(item)
    return results


async def make_source(*dicts):
    for d in dicts:
        yield Payload(d)


class Test{class_name}:
    """Unit tests for {class_name}."""

    def test_pass_through(self):
        pipeline = Pipeline()
        pipeline.add_filter({class_name}(), "{snake_name}")

        async def go():
            return await collect(pipeline.stream(make_source({{"key": "value"}})))

        results = run(go())
        assert len(results) == 1
        # TODO: assert output chunk contents

    def test_empty_source(self):
        pipeline = Pipeline()
        pipeline.add_filter({class_name}(), "{snake_name}")

        async def go():
            return await collect(pipeline.stream(make_source()))

        assert run(go()) == []
''')


# ── Tap (sync) ──

_register("tap", file_template='''\
"""
{class_name}: [describe what this tap observes]
"""

from codeupipe import Payload


class {class_name}:
    """
    Tap (sync): [one-line purpose]

    Observes the payload without modifying it.
    Pipeline._invoke() transparently handles sync returns.
    For async I/O (external metrics, HTTP logging) use: async def observe(...)

    Use for logging, metrics, auditing, debugging.
    """

    def __init__(self):
        self.observations = []

    def observe(self, payload: Payload) -> None:
        # TODO: implement observation logic
        self.observations.append(payload.to_dict())
''', test_template='''\
"""Tests for {class_name}."""

import asyncio

import pytest

from codeupipe import Payload, Pipeline
from {import_path} import {class_name}


def run(coro):
    return asyncio.run(coro)


class Test{class_name}:
    """Unit tests for {class_name}."""

    def test_captures_observation(self):
        tap = {class_name}()
        pipeline = Pipeline()
        pipeline.add_tap(tap, "{snake_name}")

        run(pipeline.run(Payload({{"key": "value"}})))
        assert len(tap.observations) == 1
        assert tap.observations[0]["key"] == "value"

    def test_does_not_modify_payload(self):
        tap = {class_name}()
        pipeline = Pipeline()
        pipeline.add_tap(tap, "{snake_name}")

        result = run(pipeline.run(Payload({{"x": 1}})))
        assert result.get("x") == 1
''')


# ── Tap (async) ──

_register("async-tap", file_template='''\
"""
{class_name}: [describe what this async tap observes]
"""

from codeupipe import Payload


class {class_name}:
    """
    Tap (async): [one-line purpose]

    Native coroutine — use when observe() needs await
    (external metrics APIs, async logging, etc.).
    For pure in-memory observation use: def observe(...) (sync)

    Observes the payload without modifying it.
    """

    def __init__(self):
        self.observations = []

    async def observe(self, payload: Payload) -> None:
        # TODO: implement async observation logic
        self.observations.append(payload.to_dict())
''', test_template='''\
"""Tests for {class_name}."""

import asyncio

import pytest

from codeupipe import Payload, Pipeline
from {import_path} import {class_name}


def run(coro):
    return asyncio.run(coro)


class Test{class_name}:
    """Unit tests for {class_name}."""

    def test_captures_observation(self):
        tap = {class_name}()
        pipeline = Pipeline()
        pipeline.add_tap(tap, "{snake_name}")

        run(pipeline.run(Payload({{"key": "value"}})))
        assert len(tap.observations) == 1

    def test_does_not_modify_payload(self):
        tap = {class_name}()
        pipeline = Pipeline()
        pipeline.add_tap(tap, "{snake_name}")

        result = run(pipeline.run(Payload({{"x": 1}})))
        assert result.get("x") == 1
''')


# ── Hook ──

_register("hook", file_template='''\
"""
{class_name}: [describe what this hook does]
"""

from typing import Optional

from codeupipe import Hook, Payload


class {class_name}(Hook):
    """
    Lifecycle Hook: [one-line purpose]

    Override any combination of before(), after(), on_error().
    """

    async def before(self, filter, payload: Payload) -> None:
        # Called before each filter (filter=None for pipeline start)
        pass

    async def after(self, filter, payload: Payload) -> None:
        # Called after each filter (filter=None for pipeline end)
        pass

    async def on_error(self, filter, error: Exception, payload: Payload) -> None:
        # Called when a filter raises an exception
        pass
''', test_template='''\
"""Tests for {class_name}."""

import asyncio

import pytest

from codeupipe import Hook, Payload, Pipeline
from {import_path} import {class_name}


def run(coro):
    return asyncio.run(coro)


class Test{class_name}:
    """Unit tests for {class_name}."""

    def test_before_fires(self):
        hook = {class_name}()
        pipeline = Pipeline()
        pipeline.use_hook(hook)
        pipeline.add_filter(
            type("Noop", (), {{"call": lambda self, p: p}})(),
            "noop",
        )
        run(pipeline.run(Payload({{}})))
        # TODO: assert hook.before was called

    def test_on_error_fires(self):
        hook = {class_name}()
        pipeline = Pipeline()
        pipeline.use_hook(hook)
        pipeline.add_filter(
            type("Bomb", (), {{"call": lambda self, p: (_ for _ in ()).throw(RuntimeError("boom"))}})(),
            "bomb",
        )
        with pytest.raises(RuntimeError):
            run(pipeline.run(Payload({{}})))
        # TODO: assert hook.on_error was called
''')


# ── Valve ──

_register("valve", file_template='''\
"""
{class_name}: [describe what this valve gates]
"""

from codeupipe import Payload, Valve


class {inner_class_name}:
    """Inner filter that runs when the valve predicate is True.

    Can be sync (def call) or async (async def call) —
    Valve uses Pipeline._invoke() which handles both.
    """

    def call(self, payload: Payload) -> Payload:
        # TODO: implement gated logic
        # For async I/O, change to: async def call(...)
        return payload


def build_{snake_name}() -> Valve:
    """
    Construct the {class_name} valve.

    Returns a Valve that gates {inner_class_name} behind a predicate.
    """
    return Valve(
        name="{snake_name}",
        inner={inner_class_name}(),
        predicate=lambda p: True,  # TODO: define your gate condition
    )
''', test_template='''\
"""Tests for {class_name} valve."""

import asyncio

import pytest

from codeupipe import Payload, Pipeline
from {import_path} import build_{snake_name}


def run(coro):
    return asyncio.run(coro)


class Test{class_name}:
    """Unit tests for {class_name} valve."""

    def test_predicate_true_runs_inner(self):
        pipeline = Pipeline()
        pipeline.add_filter(build_{snake_name}(), "{snake_name}")
        result = run(pipeline.run(Payload({{}})))
        # TODO: assert inner filter effect

    def test_predicate_false_skips(self):
        # TODO: build a valve with a predicate that returns False
        #       and verify the inner filter was skipped
        pass
''')


# ── Pipeline ──

_register("pipeline", file_template='''\
"""
{class_name}: [describe what this pipeline does]
"""

from codeupipe import Pipeline, Payload


def build_{snake_name}() -> Pipeline:
    """
    Construct the {class_name} pipeline.

    Steps:
        1. [step description]
        2. [step description]

    Returns a configured Pipeline ready for .run() or .stream().
    """
    pipeline = Pipeline()

    # TODO: add your filters, taps, hooks
    # pipeline.add_filter(MyFilter(), "my_filter")
    # pipeline.add_tap(MyTap(), "my_tap")
    # pipeline.use_hook(MyHook())

    return pipeline
''', test_template='''\
"""Tests for {class_name} pipeline."""

import asyncio

import pytest

from codeupipe import Payload
from {import_path} import build_{snake_name}


def run(coro):
    return asyncio.run(coro)


class Test{class_name}:
    """Integration tests for {class_name} pipeline."""

    def test_happy_path(self):
        pipeline = build_{snake_name}()
        result = run(pipeline.run(Payload({{}})))
        # TODO: assert final output

    def test_state_tracks_all_steps(self):
        pipeline = build_{snake_name}()
        run(pipeline.run(Payload({{}})))
        # TODO: assert pipeline.state.executed contains expected steps
''')


# ── RetryFilter ──

_register("retry-filter", file_template='''\
"""
{class_name}: [describe what this retry filter wraps]
"""

from codeupipe import Payload, RetryFilter


class {inner_class_name}:
    """Inner filter that may fail transiently."""

    async def call(self, payload: Payload) -> Payload:
        # TODO: implement logic that might fail
        return payload


def build_{snake_name}(max_retries: int = 3) -> RetryFilter:
    """
    Construct {class_name} with retry logic.

    Wraps {inner_class_name} with up to max_retries attempts.
    """
    return RetryFilter({inner_class_name}(), max_retries=max_retries)
''', test_template='''\
"""Tests for {class_name} retry filter."""

import asyncio

import pytest

from codeupipe import Payload, Pipeline
from {import_path} import build_{snake_name}


def run(coro):
    return asyncio.run(coro)


class Test{class_name}:
    """Unit tests for {class_name} retry filter."""

    def test_succeeds_on_first_try(self):
        pipeline = Pipeline()
        pipeline.add_filter(build_{snake_name}(), "{snake_name}")
        result = run(pipeline.run(Payload({{}})))
        assert result.get("error") is None

    def test_retries_on_failure(self):
        # TODO: mock inner to fail N times then succeed
        pass
''')


# ── Composed Pipeline Builder ───────────────────────────────────────

# Maps step types to the Pipeline wiring method
_STEP_WIRING = {
    "filter":        "add_filter",
    "async-filter":  "add_filter",
    "stream-filter": "add_filter",
    "valve":         "add_filter",
    "retry-filter":  "add_filter",
    "tap":           "add_tap",
    "async-tap":     "add_tap",
    "hook":          "use_hook",
}

_VALID_STEP_TYPES = set(_STEP_WIRING.keys())


def _parse_steps(raw_steps):
    """Parse step specs like 'validate_cart' or 'audit_log:tap'.

    Returns list of (snake_name, pascal_name, step_type) tuples.
    Defaults to 'filter' when no type is specified.
    """
    parsed = []
    for spec in raw_steps:
        if ":" in spec:
            name, stype = spec.rsplit(":", 1)
            if stype not in _VALID_STEP_TYPES:
                raise ValueError(
                    f"Unknown step type '{stype}' in '{spec}'. "
                    f"Choose from: {', '.join(sorted(_VALID_STEP_TYPES))}"
                )
        else:
            name = spec
            stype = "filter"
        snake = _to_snake(name)
        pascal = _to_pascal(snake)
        parsed.append((snake, pascal, stype))
    return parsed


def _build_composed_pipeline(pipeline_snake, pipeline_pascal, steps, import_path_prefix):
    """Build a composed pipeline file from a list of step specs."""
    has_stream = any(st == "stream-filter" for _, _, st in steps)

    # ── Imports ──
    imports = ["from codeupipe import Pipeline, Payload"]
    if any(st == "hook" for _, _, st in steps):
        imports[0] = "from codeupipe import Hook, Pipeline, Payload"
    if any(st == "valve" for _, _, st in steps):
        imports[0] = imports[0].replace("Pipeline,", "Pipeline, Valve,")

    import_lines = []
    for snake, pascal, stype in steps:
        if stype in ("valve", "retry-filter"):
            import_lines.append(f"from .{snake} import build_{snake}")
        else:
            import_lines.append(f"from .{snake} import {pascal}")

    # ── Pipeline build function body ──
    wiring_lines = []
    for snake, pascal, stype in steps:
        method = _STEP_WIRING[stype]
        if stype in ("valve", "retry-filter"):
            inst = f"build_{snake}()"
        else:
            inst = f"{pascal}()"

        if stype == "hook":
            wiring_lines.append(f"    pipeline.{method}({inst})")
        else:
            wiring_lines.append(f'    pipeline.{method}({inst}, "{snake}")')

    # ── Step descriptions ──
    step_descs = []
    for i, (snake, pascal, stype) in enumerate(steps, 1):
        label = stype.replace("-", " ").title()
        step_descs.append(f"        {i}. {pascal} ({label})")

    # ── Run hint ──
    if has_stream:
        run_hint = (
            "    Use pipeline.stream(source) — this pipeline contains StreamFilter(s).\n"
            "    Example:\n"
            "        async for result in pipeline.stream(async_generator):\n"
            "            process(result)"
        )
    else:
        run_hint = (
            "    Use pipeline.run(payload) for single-payload execution.\n"
            "    Use pipeline.stream(source) for streaming execution."
        )

    file_content = f'''\
"""
{pipeline_pascal}: [describe what this pipeline does]
"""

{imports[0]}

# TODO: update import paths to match your project layout
{chr(10).join(import_lines)}


def build_{pipeline_snake}() -> Pipeline:
    """
    Construct the {pipeline_pascal} pipeline.

    Steps:
{chr(10).join(step_descs)}

{run_hint}
    """
    pipeline = Pipeline()

{chr(10).join(wiring_lines)}

    return pipeline
'''
    return file_content


def _build_composed_test(pipeline_snake, pipeline_pascal, steps, import_path):
    """Build a test file for a composed pipeline."""
    has_stream = any(st == "stream-filter" for _, _, st in steps)

    # Collect expected step names (non-hook steps tracked in state)
    tracked = [snake for snake, _, stype in steps if stype != "hook"]

    if has_stream:
        stream_helpers = '''\


async def collect(aiter):
    results = []
    async for item in aiter:
        results.append(item)
    return results


async def make_source(*dicts):
    for d in dicts:
        yield Payload(d)'''

        happy_path_body = '''\
        pipeline = build_{snake}()

        async def go():
            return await collect(pipeline.stream(make_source({{"input": "test"}})))

        results = run(go())
        assert len(results) >= 1
        # TODO: assert output content'''.format(snake=pipeline_snake)

        state_body = '''\
        pipeline = build_{snake}()

        async def go():
            results = await collect(pipeline.stream(make_source({{"input": "test"}})))
            return pipeline

        pipeline = run(go())
        executed = pipeline.state.executed'''.format(snake=pipeline_snake)
    else:
        stream_helpers = ''
        happy_path_body = '''\
        pipeline = build_{snake}()
        result = run(pipeline.run(Payload({{"input": "test"}})))
        # TODO: assert final output'''.format(snake=pipeline_snake)

        state_body = '''\
        pipeline = build_{snake}()
        run(pipeline.run(Payload({{"input": "test"}})))
        executed = pipeline.state.executed'''.format(snake=pipeline_snake)

    # State assertions for tracked steps
    state_asserts = "\n".join(
        f'        assert "{s}" in executed' for s in tracked
    )

    test_content = f'''\
"""Tests for {pipeline_pascal} pipeline."""

import asyncio

import pytest

from codeupipe import Payload
from {import_path} import build_{pipeline_snake}


def run(coro):
    return asyncio.run(coro)
{stream_helpers}


class Test{pipeline_pascal}:
    """Integration tests for {pipeline_pascal} pipeline."""

    def test_happy_path(self):
{happy_path_body}

    def test_state_tracks_all_steps(self):
{state_body}
{state_asserts}
'''
    return test_content


# ── Scaffolding Engine ──────────────────────────────────────────────

COMPONENT_TYPES = list(_TEMPLATES.keys())


def scaffold(component_type: str, name: str, path: str, steps=None) -> dict:
    """
    Generate component and test files.

    Returns dict with 'component_file' and 'test_file' paths created.
    """
    if component_type not in _TEMPLATES:
        raise ValueError(
            f"Unknown component type '{component_type}'. "
            f"Choose from: {', '.join(COMPONENT_TYPES)}"
        )

    snake = _to_snake(name)
    pascal = _to_pascal(snake)

    # Resolve paths
    component_dir = Path(path)
    component_file = component_dir / f"{snake}.py"

    # Build import path from component file (relative to cwd)
    try:
        rel = component_file.relative_to(Path.cwd())
    except ValueError:
        rel = component_file
    import_path = str(rel.with_suffix("")).replace(os.sep, ".")

    # Test file: mirror structure under tests/
    test_dir = Path("tests")
    test_file = test_dir / f"test_{snake}.py"

    # ── Composed pipeline (with --steps) ──
    if component_type == "pipeline" and steps:
        parsed_steps = _parse_steps(steps)
        # Import prefix for step imports (sibling modules in same dir)
        component_content = _build_composed_pipeline(
            snake, pascal, parsed_steps, import_path
        )
        test_content = _build_composed_test(
            snake, pascal, parsed_steps, import_path
        )
    else:
        # ── Standard template ──
        file_tpl, test_tpl = _TEMPLATES[component_type]

        # Determine inner class name for valve/retry-filter
        inner_pascal = pascal + "Inner"

        fmt = {
            "class_name": pascal,
            "snake_name": snake,
            "import_path": import_path,
            "inner_class_name": inner_pascal,
        }

        component_content = file_tpl.format(**fmt)
        test_content = test_tpl.format(**fmt)

    # Create directories
    component_dir.mkdir(parents=True, exist_ok=True)
    test_dir.mkdir(parents=True, exist_ok=True)

    # Write files (never overwrite)
    if component_file.exists():
        raise FileExistsError(f"File already exists: {component_file}")
    if test_file.exists():
        raise FileExistsError(f"Test file already exists: {test_file}")

    component_file.write_text(component_content)
    test_file.write_text(test_content)

    # Ensure __init__.py exists in component directory
    init_file = component_dir / "__init__.py"
    if not init_file.exists():
        init_file.write_text("")

    return {
        "component_file": str(component_file),
        "test_file": str(test_file),
    }


# ── Bundle Engine ────────────────────────────────────────────────────

def _extract_exports(filepath: Path) -> list:
    """Extract public classes and builder functions from a Python file using AST.

    Returns list of (symbol_name, kind) tuples where kind is 'class' or 'function'.
    """
    try:
        source = filepath.read_text()
        tree = ast.parse(source, filename=str(filepath))
    except (SyntaxError, OSError):
        return []

    exports = []
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.ClassDef) and not node.name.startswith("_"):
            exports.append((node.name, "class"))
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if not node.name.startswith("_"):
                exports.append((node.name, "function"))
    return exports


def bundle(directory: str) -> dict:
    """Scan a directory and generate __init__.py with re-exports.

    Returns dict with 'init_file' path and 'exports' list.
    """
    dir_path = Path(directory)
    if not dir_path.is_dir():
        raise FileNotFoundError(f"Directory not found: {directory}")

    # Collect exports from all .py files (skip __init__.py)
    all_exports = []  # (module_name, symbol, kind)
    for py_file in sorted(dir_path.glob("*.py")):
        if py_file.name == "__init__.py":
            continue
        module = py_file.stem
        symbols = _extract_exports(py_file)
        for symbol, kind in symbols:
            all_exports.append((module, symbol, kind))

    if not all_exports:
        raise ValueError(f"No exportable symbols found in {directory}")

    # Group by module for clean import lines
    modules = {}
    for module, symbol, kind in all_exports:
        modules.setdefault(module, []).append(symbol)

    # Build __init__.py content
    lines = ['"""', f"Public API for {dir_path.name} package.", "", "Auto-generated by: cup bundle", '"""', ""]
    for module in sorted(modules.keys()):
        symbols = sorted(modules[module])
        symbols_str = ", ".join(symbols)
        lines.append(f"from .{module} import {symbols_str}")

    # __all__ for explicit public API
    all_symbols = sorted(sym for _, sym, _ in all_exports)
    lines.append("")
    lines.append("__all__ = [")
    for sym in all_symbols:
        lines.append(f'    "{sym}",')
    lines.append("]")
    lines.append("")

    init_content = "\n".join(lines)

    # Write __init__.py
    init_file = dir_path / "__init__.py"
    init_file.write_text(init_content)

    return {
        "init_file": str(init_file),
        "exports": [(m, s) for m, s, _ in all_exports],
    }


# ── Linter Engine ───────────────────────────────────────────────────

# Component detection heuristics (AST-based)
def lint(directory: str) -> list:
    """Lint a codeupipe component directory for standards violations.

    Returns list of (rule_id, severity, filepath, message) tuples.

    Internally delegates to the CUP linter pipeline (dogfooding).
    """
    import asyncio
    from .linter import build_lint_pipeline

    pipeline = build_lint_pipeline()
    payload = Payload({"directory": directory})
    result = asyncio.run(pipeline.run(payload))
    return result.get("issues", [])


# ── Coverage Engine ─────────────────────────────────────────────────

def coverage(directory: str, tests_dir: str = "tests") -> dict:
    """Map test coverage for a codeupipe component directory.

    Returns dict with 'coverage', 'summary', and 'gaps' keys.

    Internally delegates to the CUP coverage pipeline (dogfooding).
    """
    import asyncio
    from .linter.coverage_pipeline import build_coverage_pipeline

    pipeline = build_coverage_pipeline()
    payload = Payload({"directory": directory, "tests_dir": tests_dir})
    result = asyncio.run(pipeline.run(payload))
    return {
        "coverage": result.get("coverage", []),
        "summary": result.get("summary", {}),
        "gaps": result.get("gaps", []),
    }


# ── Report Engine ───────────────────────────────────────────────────

def report(directory: str, tests_dir: str = "tests") -> dict:
    """Generate a full codebase health report.

    Returns the report dict with components, orphans, git history,
    stale files, and health score.

    Internally delegates to the CUP report pipeline (dogfooding).
    """
    import asyncio
    from .linter.report_pipeline import build_report_pipeline

    pipeline = build_report_pipeline()
    payload = Payload({"directory": directory, "tests_dir": tests_dir})
    result = asyncio.run(pipeline.run(payload))
    return result.get("report", {})


# ── Doc-Check Engine ────────────────────────────────────────────────

def doc_check(directory: str) -> dict:
    """Check documentation freshness against source code.

    Scans markdown files for cup:ref markers, verifies referenced
    source files exist, checks symbol presence via AST, and detects
    content drift via SHA256 hashes.

    Returns dict with 'total_refs', 'drifted', 'missing_symbols',
    'missing_files', 'status', and 'details' keys.

    Internally delegates to the CUP doc-check pipeline (dogfooding).
    """
    import asyncio
    from .linter.doc_check_pipeline import build_doc_check_pipeline

    pipeline = build_doc_check_pipeline()
    payload = Payload({"directory": directory})
    result = asyncio.run(pipeline.run(payload))
    return result.get("doc_report", {})


# ── CLI Entry Point ─────────────────────────────────────────────────

def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="cup",
        description="codeupipe CLI — scaffold pipeline components instantly.",
    )
    sub = parser.add_subparsers(dest="command")

    # cup new <component> <name> [path]
    new_parser = sub.add_parser("new", help="Scaffold a new component")
    new_parser.add_argument(
        "component",
        choices=COMPONENT_TYPES,
        help="Component type to scaffold",
    )
    new_parser.add_argument(
        "name",
        help="Component name (snake_case or PascalCase)",
    )
    new_parser.add_argument(
        "path",
        nargs="?",
        default=".",
        help="Directory to create the component in (default: current dir)",
    )
    new_parser.add_argument(
        "--steps",
        nargs="+",
        metavar="NAME[:TYPE]",
        help=(
            "Compose a pipeline from steps (pipeline only). "
            "Format: name or name:type. Default type is 'filter'. "
            "Types: filter, async-filter, stream-filter, tap, async-tap, "
            "hook, valve, retry-filter. "
            "Example: --steps validate_cart calc_total audit_log:tap"
        ),
    )

    # cup list
    list_parser = sub.add_parser("list", help="List available component types")

    # cup bundle <path>
    bundle_parser = sub.add_parser(
        "bundle",
        help="Generate __init__.py re-exports for a component directory",
    )
    bundle_parser.add_argument(
        "path",
        help="Directory to scan and bundle",
    )

    # cup lint <path>
    lint_parser = sub.add_parser(
        "lint",
        help="Check a component directory for codeupipe standards violations",
    )
    lint_parser.add_argument(
        "path",
        help="Directory to lint",
    )

    # cup coverage <path> [--tests-dir]
    cov_parser = sub.add_parser(
        "coverage",
        help="Map test coverage for a component directory",
    )
    cov_parser.add_argument(
        "path",
        help="Directory to analyze",
    )
    cov_parser.add_argument(
        "--tests-dir",
        default="tests",
        help="Path to tests directory (default: tests)",
    )

    # cup report <path> [--tests-dir] [--json] [--detail] [--verbose]
    report_parser = sub.add_parser(
        "report",
        help="Generate a full codebase health report",
    )
    report_parser.add_argument(
        "path",
        help="Directory to analyze",
    )
    report_parser.add_argument(
        "--tests-dir",
        default="tests",
        help="Path to tests directory (default: tests)",
    )
    report_parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output raw JSON for piping to web/CI",
    )
    report_parser.add_argument(
        "--detail",
        action="store_true",
        help="Show per-component detail table",
    )
    report_parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show full detail with source info for flagged items",
    )

    # cup doc-check [path] [--json]
    doc_check_parser = sub.add_parser(
        "doc-check",
        help="Check documentation freshness against source code",
    )
    doc_check_parser.add_argument(
        "path",
        nargs="?",
        default=".",
        help="Directory to scan for markdown files (default: current dir)",
    )
    doc_check_parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output raw JSON for piping to CI",
    )

    # cup run <config> [--discover DIR] [--input JSON] [--json]
    run_parser = sub.add_parser(
        "run",
        help="Execute a pipeline from a config file",
    )
    run_parser.add_argument(
        "config",
        help="Path to pipeline config file (.toml or .json)",
    )
    run_parser.add_argument(
        "--discover",
        metavar="DIR",
        help="Directory to auto-discover components from",
    )
    run_parser.add_argument(
        "--input",
        metavar="JSON",
        dest="input_json",
        help="Initial payload data as a JSON string",
    )
    run_parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output result payload as JSON",
    )

    args = parser.parse_args(argv)

    if args.command == "list":
        print("Available component types:")
        for ct in COMPONENT_TYPES:
            print(f"  {ct}")
        return 0

    if args.command == "new":
        try:
            steps = getattr(args, "steps", None)
            if steps and args.component != "pipeline":
                print(
                    "Error: --steps can only be used with 'pipeline' component type.",
                    file=sys.stderr,
                )
                return 1
            result = scaffold(args.component, args.name, args.path, steps=steps)
            print(f"Created {args.component}:")
            print(f"  {result['component_file']}")
            print(f"  {result['test_file']}")
            return 0
        except FileExistsError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

    if args.command == "bundle":
        try:
            result = bundle(args.path)
            print(f"Bundled {result['init_file']}:")
            for module, symbol in result["exports"]:
                print(f"  {module} → {symbol}")
            return 0
        except (FileNotFoundError, ValueError) as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

    if args.command == "lint":
        try:
            issues = lint(args.path)
            if not issues:
                print(f"✓ {args.path}: all checks passed")
                return 0

            errors = [i for i in issues if i[1] == "error"]
            warnings = [i for i in issues if i[1] == "warning"]

            for rule_id, severity, filepath, message in issues:
                marker = "✗" if severity == "error" else "!"
                print(f"  {marker} {rule_id} [{severity}] {filepath}: {message}")

            print()
            summary_parts = []
            if errors:
                summary_parts.append(f"{len(errors)} error(s)")
            if warnings:
                summary_parts.append(f"{len(warnings)} warning(s)")
            print(f"  {', '.join(summary_parts)}")

            return 1 if errors else 0
        except FileNotFoundError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

    if args.command == "coverage":
        try:
            tests_dir = getattr(args, "tests_dir", "tests")
            result = coverage(args.path, tests_dir=tests_dir)
            summary = result["summary"]
            gaps = result["gaps"]
            cov_list = result["coverage"]

            if not cov_list:
                print(f"✓ {args.path}: no components found")
                return 0

            # Per-component table
            for entry in cov_list:
                pct = entry["coverage_pct"]
                icon = "✓" if pct == 100.0 else ("!" if pct > 0 else "✗")
                test_tag = f"{entry['test_count']} tests" if entry["has_test_file"] else "no tests"
                print(f"  {icon} {entry['name']} ({entry['kind']}) — {pct}% [{test_tag}]")
                if entry["untested_methods"]:
                    for m in entry["untested_methods"]:
                        print(f"      missing: {m}()")

            # Summary
            print()
            print(
                f"  {summary['overall_pct']}% method coverage "
                f"({summary['tested_methods']}/{summary['total_methods']} methods, "
                f"{summary['tested_components']}/{summary['total_components']} components tested)"
            )

            if gaps:
                print(f"  {len(gaps)} component(s) with gaps")

            return 0
        except FileNotFoundError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

    if args.command == "report":
        try:
            import json as json_mod

            tests_dir = getattr(args, "tests_dir", "tests")
            rpt = report(args.path, tests_dir=tests_dir)

            # JSON mode — dump and exit
            if getattr(args, "json_output", False):
                print(json_mod.dumps(rpt, indent=2))
                return 0

            summary = rpt.get("summary", {})
            components = rpt.get("components", [])
            orphaned_comps = rpt.get("orphaned_components", [])
            orphaned_tests = rpt.get("orphaned_tests", [])
            stale_files = rpt.get("stale_files", [])
            show_detail = getattr(args, "detail", False) or getattr(args, "verbose", False)
            show_verbose = getattr(args, "verbose", False)

            # Header
            score = summary.get("health_score", "?")
            score_icon = {"A": "✓", "B": "✓", "C": "!", "D": "✗", "F": "✗"}.get(score, "?")
            print(f"\n  {score_icon} Health Score: {score}")
            print(f"    generated: {rpt.get('generated_at', 'unknown')}")
            print(f"    directory: {rpt.get('directory', '')}")
            print()

            # Summary line
            cov_pct = summary.get("overall_pct", 0)
            total = summary.get("total_components", 0)
            tested = summary.get("tested_components", 0)
            print(f"  Coverage:  {cov_pct}% ({tested}/{total} components)")
            print(f"  Orphans:   {len(orphaned_comps)} component(s), {len(orphaned_tests)} test(s)")
            print(f"  Stale:     {len(stale_files)} file(s) (>90d)")

            if show_detail:
                print()
                print("  Components:")
                for comp in components:
                    pct = comp["coverage_pct"]
                    icon = "✓" if pct == 100.0 else ("!" if pct > 0 else "✗")
                    orphan_tag = " [ORPHAN]" if comp.get("orphaned") else ""
                    git = comp.get("git", {})
                    age = git.get("days_since_change")
                    age_tag = f" ({age}d ago)" if age is not None else ""
                    author = git.get("last_author", "")
                    author_tag = f" by {author}" if author else ""
                    print(f"    {icon} {comp['name']} ({comp['kind']}) — {pct}%{orphan_tag}{age_tag}{author_tag}")
                    if show_verbose and comp.get("untested_methods"):
                        for m in comp["untested_methods"]:
                            print(f"        missing: {m}()")
                    if show_verbose and comp.get("imported_by"):
                        print(f"        imported by: {', '.join(comp['imported_by'])}")

            if orphaned_comps:
                print()
                print("  Orphaned Components:")
                for o in orphaned_comps:
                    print(f"    ✗ {o['name']} ({o['kind']}) — {o['file']}")

            if orphaned_tests:
                print()
                print("  Orphaned Tests:")
                for o in orphaned_tests:
                    print(f"    ✗ {o['file']}")

            if stale_files:
                print()
                print("  Stale Files:")
                for s in stale_files:
                    print(f"    ! {s['file']} — {s['days_since_change']}d since change")

            print()
            return 0
        except FileNotFoundError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

    if args.command == "doc-check":
        try:
            import json as json_mod

            rpt = doc_check(args.path)

            if getattr(args, "json_output", False):
                print(json_mod.dumps(rpt, indent=2))
                return 0 if rpt.get("status") == "ok" else 1

            total = rpt.get("total_refs", 0)
            drifted = rpt.get("drifted", 0)
            missing_sym = rpt.get("missing_symbols", 0)
            missing_files = rpt.get("missing_files", 0)
            status = rpt.get("status", "ok")
            details = rpt.get("details", [])

            if status == "ok":
                print(f"✓ docs: {total} ref(s) checked, all current")
                return 0

            print(f"✗ docs: {total} ref(s) checked, issues found")
            print()

            if drifted:
                print(f"  Drifted: {drifted} ref(s)")
            if missing_sym:
                print(f"  Missing symbols: {missing_sym}")
            if missing_files:
                print(f"  Missing files: {missing_files}")

            if details:
                print()
                for d in details:
                    kind = d.get("type", "unknown")
                    icon = "!" if kind == "drift" else "✗"
                    doc = d.get("doc_file", "?")
                    src = d.get("source_file", d.get("file", "?"))
                    msg = d.get("message", d.get("symbol", ""))
                    print(f"  {icon} {doc} → {src}: {msg}")

            print()
            return 1
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

    if args.command == "run":
        try:
            import asyncio
            import json as json_mod

            from codeupipe.registry import Registry
            from codeupipe.core.pipeline import Pipeline

            reg = Registry()

            discover_dir = getattr(args, "discover", None)
            if discover_dir:
                count = reg.discover(discover_dir, recursive=True)

            config_path = args.config
            pipe = Pipeline.from_config(config_path, registry=reg)

            # Build initial payload
            input_data = {}
            input_json = getattr(args, "input_json", None)
            if input_json:
                input_data = json_mod.loads(input_json)

            result = asyncio.run(pipe.run(Payload(input_data)))

            if getattr(args, "json_output", False):
                print(json_mod.dumps(dict(result._data)))
            else:
                # Read pipeline name from config for display
                config_text = Path(config_path).read_text()
                if config_path.endswith(".json"):
                    cfg = json_mod.loads(config_text)
                else:
                    cfg = {}
                pipe_name = cfg.get("pipeline", {}).get("name", config_path)
                print(f"Pipeline '{pipe_name}' complete")
                for key, val in result._data.items():
                    print(f"  {key}: {val}")

            return 0
        except FileNotFoundError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
        except KeyError as e:
            print(f"Error: component not found — {e}", file=sys.stderr)
            return 1
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
