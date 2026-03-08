"""Tests for the cup CLI scaffolding tool."""

import os
import shutil
import tempfile
from pathlib import Path

import pytest

from codeupipe.cli import main
from codeupipe.cli._scaffold import (
    COMPONENT_TYPES,
    _to_pascal,
    _to_snake,
    scaffold,
)
from codeupipe.cli._bundle import _extract_exports, bundle


# ── Name conversion ─────────────────────────────────────────────────


class TestToSnake:
    def test_pascal_case(self):
        assert _to_snake("ValidateEmail") == "validate_email"

    def test_already_snake(self):
        assert _to_snake("validate_email") == "validate_email"

    def test_mixed_case(self):
        assert _to_snake("HTTPResponseParser") == "http_response_parser"

    def test_single_word(self):
        assert _to_snake("Filter") == "filter"

    def test_with_hyphens(self):
        assert _to_snake("my-cool-filter") == "my_cool_filter"

    def test_all_lowercase(self):
        assert _to_snake("fetch") == "fetch"


class TestToPascal:
    def test_snake_case(self):
        assert _to_pascal("validate_email") == "ValidateEmail"

    def test_single_word(self):
        assert _to_pascal("filter") == "Filter"

    def test_many_segments(self):
        assert _to_pascal("a_b_c_d") == "ABCD"


# ── Scaffold function ───────────────────────────────────────────────


class TestScaffold:
    """Test file generation for each component type."""

    def setup_method(self):
        self._orig_dir = os.getcwd()
        self._tmpdir = tempfile.mkdtemp()
        os.chdir(self._tmpdir)

    def teardown_method(self):
        os.chdir(self._orig_dir)
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    # ── parametrised across every component type ──

    @pytest.mark.parametrize("component_type", COMPONENT_TYPES)
    def test_creates_files(self, component_type):
        result = scaffold(component_type, "do_stuff", "src/filters")
        assert os.path.isfile(result["component_file"])
        assert os.path.isfile(result["test_file"])

    @pytest.mark.parametrize("component_type", COMPONENT_TYPES)
    def test_component_file_is_valid_python(self, component_type):
        result = scaffold(component_type, "my_thing", "src")
        with open(result["component_file"]) as f:
            compile(f.read(), result["component_file"], "exec")

    @pytest.mark.parametrize("component_type", COMPONENT_TYPES)
    def test_test_file_is_valid_python(self, component_type):
        result = scaffold(component_type, "my_thing", "src")
        with open(result["test_file"]) as f:
            compile(f.read(), result["test_file"], "exec")

    @pytest.mark.parametrize("component_type", COMPONENT_TYPES)
    def test_generates_correct_class_name(self, component_type):
        result = scaffold(component_type, "validate_email", "src")
        with open(result["component_file"]) as f:
            content = f.read()
        assert "ValidateEmail" in content

    @pytest.mark.parametrize("component_type", COMPONENT_TYPES)
    def test_generates_correct_filename(self, component_type):
        result = scaffold(component_type, "ValidateEmail", "src")
        assert result["component_file"].endswith("validate_email.py")

    @pytest.mark.parametrize("component_type", COMPONENT_TYPES)
    def test_creates_init_py(self, component_type):
        scaffold(component_type, "thing", "src/components")
        assert os.path.isfile("src/components/__init__.py")

    @pytest.mark.parametrize("component_type", COMPONENT_TYPES)
    def test_no_overwrite(self, component_type):
        scaffold(component_type, "thing", "src")
        with pytest.raises(FileExistsError):
            scaffold(component_type, "thing", "src")

    # ── Specific template content checks ──

    def test_filter_has_call_method(self):
        result = scaffold("filter", "my_filter", "src")
        with open(result["component_file"]) as f:
            assert "def call(self, payload" in f.read()

    def test_async_filter_has_async_call(self):
        result = scaffold("async-filter", "my_filter", "src")
        with open(result["component_file"]) as f:
            assert "async def call(self, payload" in f.read()

    def test_stream_filter_has_stream_method(self):
        result = scaffold("stream-filter", "my_stream", "src")
        with open(result["component_file"]) as f:
            assert "async def stream(self, chunk" in f.read()

    def test_tap_has_observe_method(self):
        result = scaffold("tap", "my_tap", "src")
        with open(result["component_file"]) as f:
            assert "def observe(self, payload" in f.read()

    def test_async_tap_has_async_observe(self):
        result = scaffold("async-tap", "my_tap", "src")
        with open(result["component_file"]) as f:
            assert "async def observe(self, payload" in f.read()

    def test_hook_extends_hook_abc(self):
        result = scaffold("hook", "my_hook", "src")
        with open(result["component_file"]) as f:
            content = f.read()
        assert "class MyHook(Hook):" in content
        assert "async def before" in content
        assert "async def after" in content
        assert "async def on_error" in content

    def test_valve_has_builder_function(self):
        result = scaffold("valve", "rate_limiter", "src")
        with open(result["component_file"]) as f:
            content = f.read()
        assert "def build_rate_limiter()" in content
        assert "Valve(" in content

    def test_pipeline_has_builder_function(self):
        result = scaffold("pipeline", "checkout_flow", "src")
        with open(result["component_file"]) as f:
            content = f.read()
        assert "def build_checkout_flow()" in content
        assert "Pipeline()" in content

    def test_retry_filter_has_builder(self):
        result = scaffold("retry-filter", "api_call", "src")
        with open(result["component_file"]) as f:
            content = f.read()
        assert "def build_api_call(" in content
        assert "RetryFilter(" in content

    # ── Test file content checks ──

    def test_test_file_imports_component(self):
        result = scaffold("filter", "validate_email", "src")
        with open(result["test_file"]) as f:
            content = f.read()
        assert "from src.validate_email import ValidateEmail" in content

    def test_test_file_has_test_class(self):
        result = scaffold("filter", "validate_email", "src")
        with open(result["test_file"]) as f:
            content = f.read()
        assert "class TestValidateEmail:" in content

    # ── Edge cases ──

    def test_unknown_component_type(self):
        with pytest.raises(ValueError, match="Unknown component type"):
            scaffold("nonexistent", "thing", "src")

    def test_default_path_is_current_dir(self):
        result = scaffold("filter", "thing", ".")
        assert os.path.isfile("thing.py")


# ── Spec compliance: generated files match codeupipe protocol ────────


class TestSpecCompliance:
    """Verify generated templates match actual codeupipe protocol signatures."""

    def setup_method(self):
        self._orig_dir = os.getcwd()
        self._tmpdir = tempfile.mkdtemp()
        os.chdir(self._tmpdir)

    def teardown_method(self):
        os.chdir(self._orig_dir)
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def _content(self, component_type, name="spec_check"):
        r = scaffold(component_type, name, "out")
        with open(r["component_file"]) as f:
            comp = f.read()
        with open(r["test_file"]) as f:
            test = f.read()
        return comp, test

    # ── filter (sync) ──

    def test_filter_sync_call_signature(self):
        comp, _ = self._content("filter")
        # Must have sync def call as the actual method
        assert "    def call(self, payload: Payload) -> Payload:" in comp
        # The actual method line must NOT be async (docstring mentions async as a note)
        for line in comp.splitlines():
            stripped = line.strip()
            if stripped.startswith("def call(") or stripped.startswith("async def call("):
                assert stripped.startswith("def call("), f"Expected sync def, got: {stripped}"

    def test_filter_mentions_async_option(self):
        comp, _ = self._content("filter")
        assert "async def call" in comp  # in a comment/docstring

    def test_filter_test_uses_pipeline_run(self):
        _, test = self._content("filter")
        # Test helper must be async and use Pipeline.run()
        assert "async def _run_filter" in test
        assert "await p.run(Payload(data))" in test

    def test_filter_test_no_broken_or_expression(self):
        _, test = self._content("filter")
        # Regression: old template had `Pipeline().tap(...) or _run_filter(..)`
        assert "Pipeline().tap" not in test

    # ── async-filter ──

    def test_async_filter_async_call_signature(self):
        comp, _ = self._content("async-filter")
        assert "    async def call(self, payload: Payload) -> Payload:" in comp

    def test_async_filter_mentions_sync_option(self):
        comp, _ = self._content("async-filter")
        assert "def call" in comp  # mentions sync variant in docstring

    def test_async_filter_test_uses_pipeline_run(self):
        _, test = self._content("async-filter")
        assert "async def _run_filter" in test
        assert "await p.run(Payload(data))" in test

    # ── stream-filter ──

    def test_stream_filter_async_generator(self):
        comp, _ = self._content("stream-filter")
        assert "    async def stream(self, chunk: Payload) -> AsyncIterator[Payload]:" in comp

    def test_stream_filter_yields(self):
        comp, _ = self._content("stream-filter")
        assert "yield chunk" in comp

    def test_stream_filter_imports_async_iterator(self):
        comp, _ = self._content("stream-filter")
        assert "from typing import AsyncIterator" in comp

    def test_stream_filter_docstring_mentions_streaming(self):
        comp, _ = self._content("stream-filter")
        assert "Pipeline.stream()" in comp

    def test_stream_filter_test_uses_pipeline_stream(self):
        _, test = self._content("stream-filter")
        assert "pipeline.stream(" in test

    # ── tap (sync) ──

    def test_tap_sync_observe_signature(self):
        comp, _ = self._content("tap")
        # Must have sync def observe as the actual method
        assert "    def observe(self, payload: Payload) -> None:" in comp
        # The actual method line must NOT be async (docstring mentions async as a note)
        for line in comp.splitlines():
            stripped = line.strip()
            if stripped.startswith("def observe(") or stripped.startswith("async def observe("):
                assert stripped.startswith("def observe("), f"Expected sync def, got: {stripped}"

    def test_tap_mentions_async_option(self):
        comp, _ = self._content("tap")
        assert "async def observe" in comp  # in docstring comment

    def test_tap_test_uses_add_tap(self):
        _, test = self._content("tap")
        assert "pipeline.add_tap(" in test

    # ── async-tap ──

    def test_async_tap_async_observe_signature(self):
        comp, _ = self._content("async-tap")
        assert "    async def observe(self, payload: Payload) -> None:" in comp

    def test_async_tap_mentions_sync_option(self):
        comp, _ = self._content("async-tap")
        assert "def observe" in comp  # mentions sync variant in docstring

    # ── hook ──

    def test_hook_extends_hook_abc(self):
        comp, _ = self._content("hook")
        assert "from codeupipe import Hook, Payload" in comp
        assert "class SpecCheck(Hook):" in comp

    def test_hook_all_three_methods(self):
        comp, _ = self._content("hook")
        assert "async def before(self, filter, payload: Payload) -> None:" in comp
        assert "async def after(self, filter, payload: Payload) -> None:" in comp
        assert "async def on_error(self, filter, error: Exception, payload: Payload) -> None:" in comp

    def test_hook_test_uses_use_hook(self):
        _, test = self._content("hook")
        assert "pipeline.use_hook(" in test

    # ── valve ──

    def test_valve_imports_valve(self):
        comp, _ = self._content("valve")
        assert "from codeupipe import Payload, Valve" in comp

    def test_valve_builder_returns_valve(self):
        comp, _ = self._content("valve")
        assert "def build_spec_check() -> Valve:" in comp
        assert "Valve(" in comp
        assert 'name="spec_check"' in comp
        assert "predicate=" in comp

    def test_valve_inner_has_call(self):
        comp, _ = self._content("valve")
        assert "class SpecCheckInner:" in comp
        assert "def call(self, payload: Payload) -> Payload:" in comp

    def test_valve_inner_mentions_async_option(self):
        comp, _ = self._content("valve")
        assert "async def call" in comp  # in docstring/comment

    # ── pipeline ──

    def test_pipeline_imports(self):
        comp, _ = self._content("pipeline")
        assert "from codeupipe import Pipeline, Payload" in comp

    def test_pipeline_builder_returns_pipeline(self):
        comp, _ = self._content("pipeline")
        assert "def build_spec_check() -> Pipeline:" in comp
        assert "pipeline = Pipeline()" in comp
        assert "return pipeline" in comp

    def test_pipeline_shows_all_api_methods(self):
        comp, _ = self._content("pipeline")
        assert "add_filter(" in comp
        assert "add_tap(" in comp
        assert "use_hook(" in comp

    def test_pipeline_mentions_run_and_stream(self):
        comp, _ = self._content("pipeline")
        assert ".run()" in comp
        assert ".stream()" in comp

    # ── retry-filter ──

    def test_retry_imports(self):
        comp, _ = self._content("retry-filter")
        assert "from codeupipe import Payload, RetryFilter" in comp

    def test_retry_builder_returns_retry_filter(self):
        comp, _ = self._content("retry-filter")
        assert "def build_spec_check(max_retries: int = 3) -> RetryFilter:" in comp
        assert "RetryFilter(SpecCheckInner(), max_retries=max_retries)" in comp

    def test_retry_inner_is_async(self):
        comp, _ = self._content("retry-filter")
        # RetryFilter inner should be async since RetryFilter wraps awaitable calls
        assert "async def call(self, payload: Payload) -> Payload:" in comp

    # ── Cross-component: all test files are valid Python ──

    @pytest.mark.parametrize("component_type", COMPONENT_TYPES)
    def test_every_test_has_run_helper(self, component_type):
        """Every generated test file should have an asyncio.run helper."""
        r = scaffold(component_type, f"cross_{component_type.replace('-', '_')}", "out")
        with open(r["test_file"]) as f:
            test = f.read()
        assert "def run(coro):" in test
        assert "asyncio.run(coro)" in test

    @pytest.mark.parametrize("component_type", COMPONENT_TYPES)
    def test_every_component_imports_from_codeupipe(self, component_type):
        """Every generated component should import from codeupipe."""
        r = scaffold(component_type, f"imp_{component_type.replace('-', '_')}", "out")
        with open(r["component_file"]) as f:
            comp = f.read()
        assert "from codeupipe import" in comp


# ── CLI main() ───────────────────────────────────────────────────────


class TestCLI:
    """Test the argparse-based CLI entry point."""

    def setup_method(self):
        self._orig_dir = os.getcwd()
        self._tmpdir = tempfile.mkdtemp()
        os.chdir(self._tmpdir)

    def teardown_method(self):
        os.chdir(self._orig_dir)
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def test_new_filter(self):
        rc = main(["new", "filter", "my_filter", "src"])
        assert rc == 0
        assert os.path.isfile("src/my_filter.py")
        assert os.path.isfile("tests/test_my_filter.py")

    def test_new_without_path_defaults_to_cwd(self):
        rc = main(["new", "filter", "thing"])
        assert rc == 0
        assert os.path.isfile("thing.py")

    def test_list_returns_zero(self, capsys):
        rc = main(["list"])
        assert rc == 0
        out = capsys.readouterr().out
        for ct in COMPONENT_TYPES:
            assert ct in out

    def test_no_command_returns_one(self):
        rc = main([])
        assert rc == 1

    def test_duplicate_returns_one(self):
        main(["new", "filter", "thing", "src"])
        rc = main(["new", "filter", "thing", "src"])
        assert rc == 1

    @pytest.mark.parametrize("component_type", COMPONENT_TYPES)
    def test_all_types_via_cli(self, component_type):
        rc = main(["new", component_type, f"test_{component_type.replace('-', '_')}", "out"])
        assert rc == 0


# ── Composed Pipelines (--steps) ─────────────────────────────────────

from codeupipe.cli._scaffold import _parse_steps, _build_composed_pipeline, _build_composed_test


class TestParseSteps:
    """Test step spec parsing."""

    def test_default_type_is_filter(self):
        result = _parse_steps(["validate_cart"])
        assert result == [("validate_cart", "ValidateCart", "filter")]

    def test_explicit_filter(self):
        result = _parse_steps(["validate_cart:filter"])
        assert result == [("validate_cart", "ValidateCart", "filter")]

    def test_explicit_tap(self):
        result = _parse_steps(["audit_log:tap"])
        assert result == [("audit_log", "AuditLog", "tap")]

    def test_explicit_hook(self):
        result = _parse_steps(["error_hook:hook"])
        assert result == [("error_hook", "ErrorHook", "hook")]

    def test_explicit_stream_filter(self):
        result = _parse_steps(["fan_out:stream-filter"])
        assert result == [("fan_out", "FanOut", "stream-filter")]

    def test_explicit_async_filter(self):
        result = _parse_steps(["enrich:async-filter"])
        assert result == [("enrich", "Enrich", "async-filter")]

    def test_explicit_async_tap(self):
        result = _parse_steps(["metrics:async-tap"])
        assert result == [("metrics", "Metrics", "async-tap")]

    def test_explicit_valve(self):
        result = _parse_steps(["rate_limit:valve"])
        assert result == [("rate_limit", "RateLimit", "valve")]

    def test_explicit_retry_filter(self):
        result = _parse_steps(["api_call:retry-filter"])
        assert result == [("api_call", "ApiCall", "retry-filter")]

    def test_multiple_steps(self):
        result = _parse_steps(["a", "b:tap", "c:hook"])
        assert len(result) == 3
        assert result[0] == ("a", "A", "filter")
        assert result[1] == ("b", "B", "tap")
        assert result[2] == ("c", "C", "hook")

    def test_invalid_type_raises(self):
        with pytest.raises(ValueError, match="Unknown step type"):
            _parse_steps(["foo:bogus"])

    def test_pascal_case_input(self):
        result = _parse_steps(["ValidateEmail"])
        assert result == [("validate_email", "ValidateEmail", "filter")]

    def test_pascal_case_with_type(self):
        result = _parse_steps(["AuditLog:tap"])
        assert result == [("audit_log", "AuditLog", "tap")]


class TestComposedPipeline:
    """Test composed pipeline generation."""

    def setup_method(self):
        self._orig_dir = os.getcwd()
        self._tmpdir = tempfile.mkdtemp()
        os.chdir(self._tmpdir)

    def teardown_method(self):
        os.chdir(self._orig_dir)
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    # ── scaffold() integration ──

    def test_scaffold_with_steps_creates_files(self):
        result = scaffold("pipeline", "checkout", "src/p", steps=["a", "b:tap"])
        assert os.path.isfile(result["component_file"])
        assert os.path.isfile(result["test_file"])

    def test_scaffold_with_steps_valid_python(self):
        result = scaffold("pipeline", "checkout", "src/p", steps=["a", "b:tap", "c:hook"])
        with open(result["component_file"]) as f:
            compile(f.read(), result["component_file"], "exec")
        with open(result["test_file"]) as f:
            compile(f.read(), result["test_file"], "exec")

    # ── Pipeline file content ──

    def test_composed_has_imports(self):
        result = scaffold("pipeline", "flow", "src", steps=["validate", "enrich"])
        with open(result["component_file"]) as f:
            content = f.read()
        assert "from .validate import Validate" in content
        assert "from .enrich import Enrich" in content

    def test_composed_has_add_filter_calls(self):
        result = scaffold("pipeline", "flow", "src", steps=["validate", "enrich"])
        with open(result["component_file"]) as f:
            content = f.read()
        assert 'pipeline.add_filter(Validate(), "validate")' in content
        assert 'pipeline.add_filter(Enrich(), "enrich")' in content

    def test_composed_has_add_tap_call(self):
        result = scaffold("pipeline", "flow", "src", steps=["a", "b:tap"])
        with open(result["component_file"]) as f:
            content = f.read()
        assert 'pipeline.add_tap(B(), "b")' in content

    def test_composed_has_use_hook_call(self):
        result = scaffold("pipeline", "flow", "src", steps=["a", "h:hook"])
        with open(result["component_file"]) as f:
            content = f.read()
        assert "pipeline.use_hook(H())" in content

    def test_composed_valve_uses_builder(self):
        result = scaffold("pipeline", "flow", "src", steps=["gate:valve"])
        with open(result["component_file"]) as f:
            content = f.read()
        assert "from .gate import build_gate" in content
        assert 'pipeline.add_filter(build_gate(), "gate")' in content

    def test_composed_retry_filter_uses_builder(self):
        result = scaffold("pipeline", "flow", "src", steps=["api:retry-filter"])
        with open(result["component_file"]) as f:
            content = f.read()
        assert "from .api import build_api" in content
        assert 'pipeline.add_filter(build_api(), "api")' in content

    def test_composed_hook_import_added(self):
        result = scaffold("pipeline", "flow", "src", steps=["a", "h:hook"])
        with open(result["component_file"]) as f:
            content = f.read()
        assert "from codeupipe import Hook, Pipeline, Payload" in content

    def test_composed_step_descriptions(self):
        result = scaffold("pipeline", "flow", "src", steps=["a", "b:tap", "c:hook"])
        with open(result["component_file"]) as f:
            content = f.read()
        assert "1. A (Filter)" in content
        assert "2. B (Tap)" in content
        assert "3. C (Hook)" in content

    def test_composed_builder_function(self):
        result = scaffold("pipeline", "checkout_flow", "src", steps=["a"])
        with open(result["component_file"]) as f:
            content = f.read()
        assert "def build_checkout_flow() -> Pipeline:" in content
        assert "return pipeline" in content

    # ── Streaming detection ──

    def test_no_stream_filter_uses_run_in_docstring(self):
        result = scaffold("pipeline", "flow", "src", steps=["a", "b"])
        with open(result["component_file"]) as f:
            content = f.read()
        assert "pipeline.run(payload)" in content

    def test_stream_filter_uses_stream_in_docstring(self):
        result = scaffold("pipeline", "flow", "src", steps=["a", "fan:stream-filter"])
        with open(result["component_file"]) as f:
            content = f.read()
        assert "pipeline.stream(source)" in content
        assert "StreamFilter" in content

    # ── Test file content ──

    def test_non_streaming_test_uses_run(self):
        result = scaffold("pipeline", "flow", "src", steps=["a", "b:tap"])
        with open(result["test_file"]) as f:
            content = f.read()
        assert "pipeline.run(" in content
        assert "collect(" not in content  # no streaming helpers

    def test_streaming_test_uses_stream(self):
        result = scaffold("pipeline", "flow", "src", steps=["a", "fan:stream-filter"])
        with open(result["test_file"]) as f:
            content = f.read()
        assert "pipeline.stream(" in content
        assert "collect(" in content
        assert "make_source(" in content

    def test_test_tracks_all_non_hook_steps(self):
        result = scaffold("pipeline", "flow", "src", steps=["a", "b:tap", "c:hook"])
        with open(result["test_file"]) as f:
            content = f.read()
        assert '"a" in executed' in content
        assert '"b" in executed' in content
        # Hooks aren't tracked in state.executed
        assert '"c" in executed' not in content

    def test_test_has_test_class(self):
        result = scaffold("pipeline", "checkout", "src", steps=["a"])
        with open(result["test_file"]) as f:
            content = f.read()
        assert "class TestCheckout:" in content

    def test_test_imports_builder(self):
        result = scaffold("pipeline", "checkout", "src", steps=["a"])
        with open(result["test_file"]) as f:
            content = f.read()
        assert "from src.checkout import build_checkout" in content

    # ── All step types in one pipeline ──

    def test_kitchen_sink_valid_python(self):
        """All step types in one pipeline should produce valid Python."""
        all_steps = [
            "validate:filter",
            "fetch:async-filter",
            "fan_out:stream-filter",
            "audit:tap",
            "metrics:async-tap",
            "error_hook:hook",
            "gate:valve",
            "retry:retry-filter",
        ]
        result = scaffold("pipeline", "mega_flow", "src", steps=all_steps)
        with open(result["component_file"]) as f:
            compile(f.read(), result["component_file"], "exec")
        with open(result["test_file"]) as f:
            compile(f.read(), result["test_file"], "exec")

    def test_kitchen_sink_has_all_wiring(self):
        all_steps = [
            "validate:filter",
            "fetch:async-filter",
            "fan_out:stream-filter",
            "audit:tap",
            "metrics:async-tap",
            "error_hook:hook",
            "gate:valve",
            "retry:retry-filter",
        ]
        result = scaffold("pipeline", "mega_flow", "src", steps=all_steps)
        with open(result["component_file"]) as f:
            content = f.read()
        assert 'add_filter(Validate(), "validate")' in content
        assert 'add_filter(Fetch(), "fetch")' in content
        assert 'add_filter(FanOut(), "fan_out")' in content
        assert 'add_tap(Audit(), "audit")' in content
        assert 'add_tap(Metrics(), "metrics")' in content
        assert "use_hook(ErrorHook())" in content
        assert 'add_filter(build_gate(), "gate")' in content
        assert 'add_filter(build_retry(), "retry")' in content

    # ── CLI main() integration ──

    def test_cli_pipeline_with_steps(self):
        rc = main(["new", "pipeline", "checkout", "src", "--steps", "a", "b:tap"])
        assert rc == 0
        assert os.path.isfile("src/checkout.py")
        assert os.path.isfile("tests/test_checkout.py")

    def test_cli_steps_on_non_pipeline_returns_error(self):
        rc = main(["new", "filter", "foo", "src", "--steps", "bar"])
        assert rc == 1

    def test_cli_pipeline_without_steps_still_works(self):
        rc = main(["new", "pipeline", "bare", "src"])
        assert rc == 0
        with open("src/bare.py") as f:
            content = f.read()
        # Bare pipeline should have TODO comments, not wired steps
        assert "# TODO:" in content


# ── Bundle ───────────────────────────────────────────────────────────


class TestExtractExports:
    """Test AST-based symbol extraction."""

    def setup_method(self):
        self._orig_dir = os.getcwd()
        self._tmpdir = tempfile.mkdtemp()
        os.chdir(self._tmpdir)

    def teardown_method(self):
        os.chdir(self._orig_dir)
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def test_extracts_class(self):
        Path("mod.py").write_text("class Foo:\n    pass\n")
        result = _extract_exports(Path("mod.py"))
        assert ("Foo", "class") in result

    def test_extracts_function(self):
        Path("mod.py").write_text("def build_thing():\n    pass\n")
        result = _extract_exports(Path("mod.py"))
        assert ("build_thing", "function") in result

    def test_extracts_async_function(self):
        Path("mod.py").write_text("async def do_stuff():\n    pass\n")
        result = _extract_exports(Path("mod.py"))
        assert ("do_stuff", "function") in result

    def test_skips_private_class(self):
        Path("mod.py").write_text("class _Internal:\n    pass\n")
        result = _extract_exports(Path("mod.py"))
        assert result == []

    def test_skips_private_function(self):
        Path("mod.py").write_text("def _helper():\n    pass\n")
        result = _extract_exports(Path("mod.py"))
        assert result == []

    def test_extracts_multiple_symbols(self):
        Path("mod.py").write_text(
            "class Foo:\n    pass\n\ndef build_bar():\n    pass\n"
        )
        result = _extract_exports(Path("mod.py"))
        assert len(result) == 2
        names = [name for name, _ in result]
        assert "Foo" in names
        assert "build_bar" in names

    def test_handles_syntax_error(self):
        Path("bad.py").write_text("def broken(\n")
        result = _extract_exports(Path("bad.py"))
        assert result == []

    def test_handles_missing_file(self):
        result = _extract_exports(Path("nonexistent.py"))
        assert result == []


class TestBundle:
    """Test bundle generation."""

    def setup_method(self):
        self._orig_dir = os.getcwd()
        self._tmpdir = tempfile.mkdtemp()
        os.chdir(self._tmpdir)

    def teardown_method(self):
        os.chdir(self._orig_dir)
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def _scaffold_project(self):
        """Scaffold a small project for bundle testing."""
        scaffold("filter", "validate", "pkg")
        scaffold("tap", "audit", "pkg")
        scaffold("hook", "error_hook", "pkg")

    def test_generates_init_py(self):
        self._scaffold_project()
        result = bundle("pkg")
        assert os.path.isfile(result["init_file"])
        assert result["init_file"].endswith("__init__.py")

    def test_exports_classes(self):
        self._scaffold_project()
        result = bundle("pkg")
        symbols = [sym for _, sym in result["exports"]]
        assert "Validate" in symbols
        assert "Audit" in symbols
        assert "ErrorHook" in symbols

    def test_init_contains_imports(self):
        self._scaffold_project()
        bundle("pkg")
        with open("pkg/__init__.py") as f:
            content = f.read()
        assert "from .validate import Validate" in content
        assert "from .audit import Audit" in content
        assert "from .error_hook import ErrorHook" in content

    def test_init_contains_all(self):
        self._scaffold_project()
        bundle("pkg")
        with open("pkg/__init__.py") as f:
            content = f.read()
        assert "__all__" in content
        assert '"Validate"' in content
        assert '"Audit"' in content
        assert '"ErrorHook"' in content

    def test_init_is_valid_python(self):
        self._scaffold_project()
        bundle("pkg")
        with open("pkg/__init__.py") as f:
            compile(f.read(), "pkg/__init__.py", "exec")

    def test_init_has_header(self):
        self._scaffold_project()
        bundle("pkg")
        with open("pkg/__init__.py") as f:
            content = f.read()
        assert "Auto-generated by: cup bundle" in content

    def test_skips_init_py_itself(self):
        self._scaffold_project()
        bundle("pkg")
        # Bundle again — should not import __init__
        bundle("pkg")
        with open("pkg/__init__.py") as f:
            content = f.read()
        assert "from .__init__" not in content

    def test_includes_builders(self):
        scaffold("valve", "rate_limit", "pkg")
        result = bundle("pkg")
        symbols = [sym for _, sym in result["exports"]]
        assert "build_rate_limit" in symbols
        assert "RateLimitInner" in symbols

    def test_includes_pipeline_builder(self):
        scaffold("pipeline", "checkout", "pkg",
                 steps=["validate", "charge:filter"])
        result = bundle("pkg")
        symbols = [sym for _, sym in result["exports"]]
        assert "build_checkout" in symbols

    def test_nonexistent_directory_raises(self):
        with pytest.raises(FileNotFoundError, match="Directory not found"):
            bundle("nonexistent")

    def test_empty_directory_raises(self):
        os.makedirs("empty_pkg", exist_ok=True)
        with pytest.raises(ValueError, match="No exportable symbols"):
            bundle("empty_pkg")

    def test_directory_with_only_init_raises(self):
        os.makedirs("init_only", exist_ok=True)
        Path("init_only/__init__.py").write_text("")
        with pytest.raises(ValueError, match="No exportable symbols"):
            bundle("init_only")

    def test_rebundle_overwrites_init(self):
        scaffold("filter", "a", "pkg")
        bundle("pkg")
        # Add another component, rebundle
        scaffold("filter", "b", "pkg")
        bundle("pkg")
        with open("pkg/__init__.py") as f:
            content = f.read()
        assert "from .a import A" in content
        assert "from .b import B" in content

    def test_sorted_output(self):
        scaffold("filter", "z_last", "pkg")
        scaffold("filter", "a_first", "pkg")
        bundle("pkg")
        with open("pkg/__init__.py") as f:
            content = f.read()
        # a_first should appear before z_last
        assert content.index("a_first") < content.index("z_last")


class TestBundleCLI:
    """Test cup bundle via main()."""

    def setup_method(self):
        self._orig_dir = os.getcwd()
        self._tmpdir = tempfile.mkdtemp()
        os.chdir(self._tmpdir)

    def teardown_method(self):
        os.chdir(self._orig_dir)
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def test_bundle_via_cli(self):
        scaffold("filter", "thing", "pkg")
        rc = main(["bundle", "pkg"])
        assert rc == 0
        assert os.path.isfile("pkg/__init__.py")

    def test_bundle_nonexistent_returns_one(self):
        rc = main(["bundle", "nope"])
        assert rc == 1

    def test_bundle_empty_returns_one(self):
        os.makedirs("empty")
        rc = main(["bundle", "empty"])
        assert rc == 1

    def test_bundle_output_lists_exports(self, capsys):
        scaffold("filter", "validate", "pkg")
        main(["bundle", "pkg"])
        out = capsys.readouterr().out
        assert "validate → Validate" in out
