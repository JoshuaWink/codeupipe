"""
Scaffold engine — ``cup new`` code generation.

Contains name conversion utilities, the composed pipeline builder,
and the ``scaffold()`` function that writes component + test files.
"""

import os
import re
from pathlib import Path

from ._templates import _TEMPLATES


# ── Name Utilities ──────────────────────────────────────────────────

def _to_snake(name: str) -> str:
    """Convert any casing to snake_case."""
    s = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", name)
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s)
    s = re.sub(r"[-\s]+", "_", s)
    return s.lower()


def _to_pascal(snake: str) -> str:
    """Convert snake_case to PascalCase."""
    return "".join(word.capitalize() for word in snake.split("_"))


# ── Composed Pipeline Builder ───────────────────────────────────────

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

    step_descs = []
    for i, (snake, pascal, stype) in enumerate(steps, 1):
        label = stype.replace("-", " ").title()
        step_descs.append(f"        {i}. {pascal} ({label})")

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
    """Generate component and test files.

    Returns dict with 'component_file' and 'test_file' paths created.
    """
    if component_type not in _TEMPLATES:
        raise ValueError(
            f"Unknown component type '{component_type}'. "
            f"Choose from: {', '.join(COMPONENT_TYPES)}"
        )

    snake = _to_snake(name)
    pascal = _to_pascal(snake)

    component_dir = Path(path)
    component_file = component_dir / f"{snake}.py"

    try:
        rel = component_file.relative_to(Path.cwd())
    except ValueError:
        rel = component_file
    import_path = str(rel.with_suffix("")).replace(os.sep, ".")

    test_dir = Path("tests")
    test_file = test_dir / f"test_{snake}.py"

    if component_type == "pipeline" and steps:
        parsed_steps = _parse_steps(steps)
        component_content = _build_composed_pipeline(
            snake, pascal, parsed_steps, import_path
        )
        test_content = _build_composed_test(
            snake, pascal, parsed_steps, import_path
        )
    else:
        file_tpl, test_tpl = _TEMPLATES[component_type]
        inner_pascal = pascal + "Inner"
        fmt = {
            "class_name": pascal,
            "snake_name": snake,
            "import_path": import_path,
            "inner_class_name": inner_pascal,
        }
        component_content = file_tpl.format(**fmt)
        test_content = test_tpl.format(**fmt)

    component_dir.mkdir(parents=True, exist_ok=True)
    test_dir.mkdir(parents=True, exist_ok=True)

    if component_file.exists():
        raise FileExistsError(f"File already exists: {component_file}")
    if test_file.exists():
        raise FileExistsError(f"Test file already exists: {test_file}")

    component_file.write_text(component_content)
    test_file.write_text(test_content)

    init_file = component_dir / "__init__.py"
    if not init_file.exists():
        init_file.write_text("")

    return {
        "component_file": str(component_file),
        "test_file": str(test_file),
    }
