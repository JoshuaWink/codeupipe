"""
Component templates for ``cup new`` scaffolding.

Each template is a (file_template, test_template) pair registered
by component type.  The scaffold engine formats them with class
name, snake name, and import path variables.
"""

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

