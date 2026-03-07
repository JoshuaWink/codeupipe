"""
codeupipe.testing — Test utilities optimized for CUP projects.

Provides zero-boilerplate helpers for testing filters, pipelines, taps,
hooks, and stream filters. One import, no asyncio or Pipeline wiring needed.

Usage:
    from codeupipe.testing import run_filter, assert_payload, mock_filter

    def test_my_filter():
        result = run_filter(MyFilter(), {"input": "data"})
        assert_payload(result, output="expected")
"""

import asyncio
import inspect
import sys
from pathlib import Path
from types import ModuleType
from typing import Any, Dict, List, Optional, Sequence, Union
from unittest.mock import MagicMock

from codeupipe import Payload, Pipeline
from codeupipe.core.hook import Hook
from codeupipe.core.state import State


__all__ = [
    "run_filter",
    "run_pipeline",
    "assert_pipeline_streaming",
    "assert_payload",
    "assert_keys",
    "assert_keys_absent",
    "assert_state",
    "mock_filter",
    "mock_tap",
    "mock_hook",
    "mock_sdk_modules",
    "cup_component",
    "RecordingTap",
    "RecordingHook",
]


# ── Runners ─────────────────────────────────────────────────────────

def _to_payload(data: Union[dict, Payload]) -> Payload:
    """Coerce dict or Payload to Payload."""
    if isinstance(data, Payload):
        return data
    return Payload(data)


def run_filter(filter_instance, data: Union[dict, Payload]) -> Payload:
    """Run a single filter with minimal boilerplate.

    Handles sync/async transparently. Accepts dict or Payload.
    Returns the output Payload.
    """
    payload = _to_payload(data)
    result = filter_instance.call(payload)
    if inspect.isawaitable(result):
        result = asyncio.run(result)
    return result


def run_pipeline(
    pipeline: Pipeline,
    data: Union[dict, Payload],
    return_state: bool = False,
) -> Union[Payload, tuple]:
    """Run a pipeline with minimal boilerplate.

    Args:
        pipeline: Wired Pipeline instance.
        data: Input dict or Payload.
        return_state: If True, returns (result, state) tuple.

    Returns:
        Payload, or (Payload, State) if return_state=True.
    """
    payload = _to_payload(data)
    result = asyncio.run(pipeline.run(payload))
    if return_state:
        return result, pipeline.state
    return result


def assert_pipeline_streaming(
    pipeline: Pipeline,
    chunks: Sequence[Union[dict, Payload]],
) -> List[Payload]:
    """Run a pipeline in stream mode and collect all output chunks.

    Name reflects both dimensions: it runs a *pipeline* through its *stream*
    path, collecting results for assertion.

    Args:
        pipeline: Pipeline with stream-capable filters.
        chunks: Input chunks (dicts or Payloads).

    Returns:
        List of output Payloads.
    """
    payloads = [_to_payload(c) for c in chunks]

    async def _source():
        for p in payloads:
            yield p

    async def _collect():
        results = []
        async for chunk in pipeline.stream(_source()):
            results.append(chunk)
        return results

    return asyncio.run(_collect())


# ── Assertions ──────────────────────────────────────────────────────

def assert_payload(payload: Payload, **expected: Any) -> None:
    """Assert payload contains all expected key=value pairs.

    Usage:
        assert_payload(result, status="ok", count=3)
    """
    for key, expected_value in expected.items():
        actual = payload.get(key)
        assert actual == expected_value, (
            f"Payload key '{key}': expected {expected_value!r}, got {actual!r}"
        )


def assert_keys(payload: Payload, *keys: str) -> None:
    """Assert payload contains all specified keys.

    Usage:
        assert_keys(result, "user_id", "name", "email")
    """
    data = payload.to_dict()
    for key in keys:
        assert key in data, f"Payload missing expected key '{key}'. Keys present: {list(data.keys())}"


def assert_keys_absent(payload: Payload, *keys: str) -> None:
    """Assert payload does NOT contain any of the specified keys.

    Usage:
        assert_keys_absent(result, "password", "secret_token")
    """
    data = payload.to_dict()
    for key in keys:
        assert key not in data, (
            f"Payload unexpectedly contains key '{key}'. Keys present: {list(data.keys())}"
        )


def assert_state(state: State, executed: Optional[List[str]] = None) -> None:
    """Assert pipeline state after execution.

    Usage:
        _, state = run_pipeline(pipeline, data, return_state=True)
        assert_state(state, executed=["step_a", "step_b"])
    """
    if executed is not None:
        for step in executed:
            assert step in state.executed, (
                f"Step '{step}' not in state.executed. "
                f"Executed: {list(state.executed)}"
            )


# ── Mocks ───────────────────────────────────────────────────────────

class _MockFilter:
    """Filter mock that inserts predefined data and records calls."""

    def __init__(self, **data: Any):
        self._data = data
        self.call_count = 0
        self.last_payload: Optional[Payload] = None

    def call(self, payload: Payload) -> Payload:
        self.call_count += 1
        self.last_payload = payload
        result = payload
        for key, value in self._data.items():
            result = result.insert(key, value)
        return result


def mock_filter(**data: Any) -> _MockFilter:
    """Create a mock filter that inserts the given key-value pairs.

    Usage:
        f = mock_filter(status="ok", processed=True)
        result = run_filter(f, {"input": 1})
    """
    return _MockFilter(**data)


class RecordingTap:
    """Tap that records every payload it observes."""

    def __init__(self):
        self.payloads: List[Payload] = []
        self.call_count = 0

    def observe(self, payload: Payload) -> None:
        self.call_count += 1
        self.payloads.append(payload)


def mock_tap() -> RecordingTap:
    """Create a recording tap for testing.

    Usage:
        tap = mock_tap()
        pipeline.add_tap(tap, "spy")
        run_pipeline(pipeline, data)
        assert tap.call_count == 1
    """
    return RecordingTap()


class RecordingHook(Hook):
    """Hook that records all lifecycle events."""

    def __init__(self):
        self.before_count = 0
        self.after_count = 0
        self.error_count = 0
        self.before_payloads: List[Payload] = []
        self.after_payloads: List[Payload] = []
        self.errors: List[Exception] = []

    async def before(self, filter, payload):
        self.before_count += 1
        self.before_payloads.append(payload)

    async def after(self, filter, payload):
        self.after_count += 1
        self.after_payloads.append(payload)

    async def on_error(self, filter, error, payload):
        self.error_count += 1
        self.errors.append(error)


def mock_hook() -> RecordingHook:
    """Create a recording hook for testing.

    Usage:
        hook = mock_hook()
        pipeline.use_hook(hook)
        run_pipeline(pipeline, data)
        assert hook.before_count > 0
    """
    return RecordingHook()


# ── SDK Module Mocking ──────────────────────────────────────────────

class _SDKModuleContext:
    """Context manager that injects mock modules into sys.modules.

    Saves originals, injects mocks, and restores on exit.
    Also cleans up any connector modules that imported the mocks.
    """

    def __init__(
        self,
        modules: Dict[str, Any],
        connector_prefix: Optional[str] = None,
    ):
        self._modules = modules
        self._connector_prefix = connector_prefix
        self._originals: Dict[str, Any] = {}

    def __enter__(self) -> Dict[str, Any]:
        for name, mock_mod in self._modules.items():
            self._originals[name] = sys.modules.get(name)
            sys.modules[name] = mock_mod
        return self._modules

    def __exit__(self, *exc):
        for name, orig in self._originals.items():
            if orig is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = orig
        if self._connector_prefix:
            for key in list(sys.modules):
                if key.startswith(self._connector_prefix):
                    del sys.modules[key]
        return False


def mock_sdk_modules(
    module_names: Union[str, List[str]],
    *,
    connector_prefix: Optional[str] = None,
) -> _SDKModuleContext:
    """Create mock SDK modules for connector testing.

    Injects MagicMock modules into sys.modules so connector code can
    ``import sdk_name`` without the SDK being pip-installed.
    Use as a context manager or in a pytest fixture.

    Args:
        module_names: Single module name or list of dotted names.
            Example: ``"stripe"`` or ``["google", "google.genai", "google.genai.types"]``
        connector_prefix: If set, cleans up all sys.modules entries
            starting with this prefix on exit (e.g. ``"codeupipe_stripe"``).

    Returns:
        Context manager. ``__enter__`` returns dict of {name: mock_module}.

    Usage (pytest fixture)::

        @pytest.fixture(autouse=True)
        def mock_stripe():
            with mock_sdk_modules("stripe", connector_prefix="codeupipe_stripe") as mods:
                yield mods["stripe"]

    Usage (nested modules)::

        @pytest.fixture(autouse=True)
        def mock_google():
            names = ["google", "google.genai", "google.genai.types"]
            with mock_sdk_modules(names, connector_prefix="codeupipe_google_ai") as mods:
                yield mods
    """
    if isinstance(module_names, str):
        module_names = [module_names]

    modules: Dict[str, Any] = {}
    for name in module_names:
        mock_mod = MagicMock(spec=ModuleType)
        mock_mod.__name__ = name
        mock_mod.__spec__ = None
        modules[name] = mock_mod

    # Wire parent→child relationships for dotted names
    for name, mock_mod in modules.items():
        parts = name.rsplit(".", 1)
        if len(parts) == 2:
            parent_name, child_attr = parts
            if parent_name in modules:
                setattr(modules[parent_name], child_attr, mock_mod)

    return _SDKModuleContext(modules, connector_prefix)


# ── Scaffolding ─────────────────────────────────────────────────────

def _to_class_name(snake: str) -> str:
    """Convert snake_case to PascalCase."""
    return "".join(word.capitalize() for word in snake.split("_"))


_TEMPLATES = {
    "filter": (
        "class {cls}:\n"
        "{methods}\n"
    ),
    "async-filter": (
        "class {cls}:\n"
        "    async def call(self, payload):\n"
        "        return payload\n"
    ),
    "tap": (
        "class {cls}:\n"
        "    def observe(self, payload):\n"
        "        pass\n"
    ),
    "async-tap": (
        "class {cls}:\n"
        "    async def observe(self, payload):\n"
        "        pass\n"
    ),
    "hook": (
        "from codeupipe import Hook\n\n\n"
        "class {cls}(Hook):\n"
        "    async def before(self, filter, payload):\n"
        "        pass\n\n"
        "    async def after(self, filter, payload):\n"
        "        pass\n\n"
        "    async def on_error(self, filter, error, payload):\n"
        "        pass\n"
    ),
    "stream-filter": (
        "class {cls}:\n"
        "    async def stream(self, chunk):\n"
        "        yield chunk\n"
    ),
    "builder": (
        "def build_{snake}():\n"
        "    pass\n"
    ),
    "valve": (
        "from codeupipe import Valve\n\n\n"
        "class {cls}Inner:\n"
        "    def call(self, payload):\n"
        "        return payload\n\n\n"
        "def build_{snake}():\n"
        "    return Valve(name='{snake}', inner={cls}Inner(), "
        "predicate=lambda p: True)\n"
    ),
    "pipeline": (
        "from codeupipe import Pipeline\n\n\n"
        "def build_{snake}():\n"
        "    pipeline = Pipeline()\n"
        "    return pipeline\n"
    ),
    "retry-filter": (
        "from codeupipe import RetryFilter\n\n\n"
        "class {cls}Inner:\n"
        "    async def call(self, payload):\n"
        "        return payload\n\n\n"
        "def build_{snake}(max_retries=3):\n"
        "    return RetryFilter({cls}Inner(), max_retries=max_retries)\n"
    ),
}

_TEST_TEMPLATE = (
    "from codeupipe.testing import run_filter\n"
    "from {module} import {symbol}\n\n\n"
    "class Test{cls}:\n"
    "    def test_placeholder(self):\n"
    "        pass\n"
)


def cup_component(
    directory: Path,
    name: str,
    kind: str,
    *,
    with_test: bool = False,
    methods: Optional[List[str]] = None,
) -> Path:
    """Scaffold a CUP component file on disk for analysis tests.

    Args:
        directory: Where to create the .py file.
        name: snake_case component name.
        kind: filter, async-filter, tap, async-tap, hook, stream-filter,
              valve, pipeline, retry-filter, builder.
        with_test: Also create tests/test_{name}.py.
        methods: Custom method list (filter kind only).

    Returns:
        Path to the created component file.
    """
    if kind not in _TEMPLATES:
        raise ValueError(
            f"Unknown kind '{kind}'. "
            f"Valid kinds: {', '.join(sorted(_TEMPLATES.keys()))}"
        )

    cls = _to_class_name(name)
    filepath = directory / f"{name}.py"

    # Kinds that use {snake} in their template
    _BUILDER_KINDS = {"builder", "valve", "pipeline", "retry-filter"}

    if kind == "filter":
        if methods:
            method_lines = []
            for m in methods:
                method_lines.append(f"    def {m}(self, payload):\n        pass\n")
            methods_str = "\n".join(method_lines)
        else:
            methods_str = "    def call(self, payload):\n        return payload\n"
        source = _TEMPLATES["filter"].format(cls=cls, methods=methods_str)
    elif kind in _BUILDER_KINDS:
        source = _TEMPLATES[kind].format(cls=cls, snake=name)
    else:
        source = _TEMPLATES[kind].format(cls=cls)

    filepath.write_text(source)

    if with_test:
        tests_dir = directory / "tests"
        tests_dir.mkdir(exist_ok=True)
        if kind in _BUILDER_KINDS:
            symbol = f"build_{name}"
        else:
            symbol = cls
        test_source = _TEST_TEMPLATE.format(
            module=name, symbol=symbol, cls=cls,
        )
        (tests_dir / f"test_{name}.py").write_text(test_source)

    return filepath
