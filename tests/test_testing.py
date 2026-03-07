"""Tests for codeupipe.testing — the CUP test wrapper. RED phase first."""

import asyncio

import pytest

from codeupipe import Payload, Pipeline
from codeupipe.testing import (
    run_filter,
    run_pipeline,
    assert_pipeline_streaming,
    assert_payload,
    assert_keys,
    assert_keys_absent,
    assert_state,
    mock_filter,
    mock_tap,
    mock_hook,
    mock_sdk_modules,
    cup_component,
    RecordingTap,
    RecordingHook,
)


# ── run_filter ──────────────────────────────────────────────────────

class TestRunFilter:
    """run_filter: invoke a filter with minimal boilerplate."""

    def test_sync_filter_with_dict(self):
        """Pass a dict, get a Payload back — no Pipeline or asyncio needed."""
        class Upper:
            def call(self, p):
                return p.insert("name", p.get("name", "").upper())

        result = run_filter(Upper(), {"name": "alice"})
        assert isinstance(result, Payload)
        assert result.get("name") == "ALICE"

    def test_async_filter_with_dict(self):
        """Async filters work transparently."""
        class Async:
            async def call(self, p):
                return p.insert("done", True)

        result = run_filter(Async(), {"x": 1})
        assert result.get("done") is True
        assert result.get("x") == 1

    def test_with_payload_input(self):
        """Also accepts a Payload directly."""
        class Noop:
            def call(self, p):
                return p

        payload = Payload({"a": 1})
        result = run_filter(Noop(), payload)
        assert result.get("a") == 1

    def test_filter_exception_propagates(self):
        """Errors are not swallowed."""
        class Boom:
            def call(self, p):
                raise ValueError("bad input")

        with pytest.raises(ValueError, match="bad input"):
            run_filter(Boom(), {})

    def test_empty_dict(self):
        class Noop:
            def call(self, p):
                return p
        result = run_filter(Noop(), {})
        assert isinstance(result, Payload)


# ── run_pipeline ────────────────────────────────────────────────────

class TestRunPipeline:
    """run_pipeline: run a wired pipeline with minimal boilerplate."""

    def test_runs_pipeline_with_dict(self):
        class Step:
            def call(self, p):
                return p.insert("ran", True)

        pipeline = Pipeline()
        pipeline.add_filter(Step(), "step")
        result = run_pipeline(pipeline, {"input": 1})
        assert result.get("ran") is True
        assert result.get("input") == 1

    def test_runs_pipeline_with_payload(self):
        class Step:
            def call(self, p):
                return p.insert("ok", True)

        pipeline = Pipeline()
        pipeline.add_filter(Step(), "step")
        result = run_pipeline(pipeline, Payload({"x": 1}))
        assert result.get("ok") is True

    def test_returns_state_when_requested(self):
        class Step:
            def call(self, p):
                return p

        pipeline = Pipeline()
        pipeline.add_filter(Step(), "my_step")
        result, state = run_pipeline(pipeline, {}, return_state=True)
        assert "my_step" in state.executed


# ── assert_pipeline_streaming ──────────────────────────────────────────────────

class TestAssertPipelineStreaming:
    """assert_pipeline_streaming: run pipeline in streaming mode and collect output."""

    def test_collects_stream_output(self):
        class FanOut:
            async def stream(self, chunk):
                for i in range(3):
                    yield chunk.insert("index", i)

        pipeline = Pipeline()
        pipeline.add_filter(FanOut(), "fan")
        results = assert_pipeline_streaming(pipeline, [{"seed": True}])
        assert len(results) == 3
        assert results[0].get("index") == 0
        assert results[2].get("index") == 2

    def test_stream_with_multiple_chunks(self):
        class PassThrough:
            async def stream(self, chunk):
                yield chunk

        pipeline = Pipeline()
        pipeline.add_filter(PassThrough(), "pass")
        results = assert_pipeline_streaming(pipeline, [{"a": 1}, {"a": 2}])
        assert len(results) == 2


# ── assert_payload ──────────────────────────────────────────────────

class TestAssertPayload:
    """assert_payload: fluent assertions on payload contents."""

    def test_passes_on_match(self):
        p = Payload({"x": 1, "y": "hello"})
        assert_payload(p, x=1, y="hello")  # should not raise

    def test_fails_on_mismatch(self):
        p = Payload({"x": 1})
        with pytest.raises(AssertionError):
            assert_payload(p, x=999)

    def test_fails_on_missing_key(self):
        p = Payload({"x": 1})
        with pytest.raises(AssertionError):
            assert_payload(p, missing_key="oops")


# ── assert_keys ─────────────────────────────────────────────────────

class TestAssertKeys:
    """assert_keys: check that payload has specific keys."""

    def test_passes_when_all_present(self):
        p = Payload({"a": 1, "b": 2, "c": 3})
        assert_keys(p, "a", "b", "c")

    def test_fails_when_key_missing(self):
        p = Payload({"a": 1})
        with pytest.raises(AssertionError):
            assert_keys(p, "a", "missing")


# ── assert_state ────────────────────────────────────────────────────

class TestAssertState:
    """assert_state: assert pipeline state after execution."""

    def test_passes_when_steps_executed(self):
        class Step:
            def call(self, p):
                return p

        pipeline = Pipeline()
        pipeline.add_filter(Step(), "a")
        pipeline.add_filter(Step(), "b")
        result, state = run_pipeline(pipeline, {}, return_state=True)
        assert_state(state, executed=["a", "b"])

    def test_fails_when_step_missing(self):
        class Step:
            def call(self, p):
                return p

        pipeline = Pipeline()
        pipeline.add_filter(Step(), "a")
        _, state = run_pipeline(pipeline, {}, return_state=True)
        with pytest.raises(AssertionError):
            assert_state(state, executed=["a", "nonexistent"])


# ── mock_filter ─────────────────────────────────────────────────────

class TestMockFilter:
    """mock_filter: create filters that insert predefined data."""

    def test_basic_mock(self):
        f = mock_filter(status="ok", value=42)
        result = run_filter(f, {"input": 1})
        assert result.get("status") == "ok"
        assert result.get("value") == 42
        assert result.get("input") == 1

    def test_mock_records_calls(self):
        f = mock_filter(x=1)
        run_filter(f, {"a": 1})
        run_filter(f, {"b": 2})
        assert f.call_count == 2
        assert f.last_payload.get("b") == 2

    def test_empty_mock(self):
        f = mock_filter()
        result = run_filter(f, {"keep": True})
        assert result.get("keep") is True


# ── mock_tap ────────────────────────────────────────────────────────

class TestMockTap:
    """mock_tap: create taps that record observations."""

    def test_records_observations(self):
        tap = mock_tap()
        pipeline = Pipeline()
        pipeline.add_filter(mock_filter(x=1), "step")
        pipeline.add_tap(tap, "spy")
        result = run_pipeline(pipeline, {"input": True})
        assert tap.call_count >= 1
        assert isinstance(tap.payloads[0], Payload)

    def test_tap_does_not_modify_payload(self):
        tap = mock_tap()
        pipeline = Pipeline()
        pipeline.add_filter(mock_filter(added=True), "step")
        pipeline.add_tap(tap, "spy")
        result = run_pipeline(pipeline, {"original": True})
        assert result.get("original") is True
        assert result.get("added") is True


# ── mock_hook ───────────────────────────────────────────────────────

class TestMockHook:
    """mock_hook: create hooks that record lifecycle events."""

    def test_records_before_and_after(self):
        hook = mock_hook()
        pipeline = Pipeline()
        pipeline.use_hook(hook)
        pipeline.add_filter(mock_filter(), "step")
        run_pipeline(pipeline, {})
        assert hook.before_count > 0
        assert hook.after_count > 0

    def test_records_on_error(self):
        class Boom:
            def call(self, p):
                raise RuntimeError("oops")

        hook = mock_hook()
        pipeline = Pipeline()
        pipeline.use_hook(hook)
        pipeline.add_filter(Boom(), "boom")
        with pytest.raises(RuntimeError):
            run_pipeline(pipeline, {})
        assert hook.error_count > 0


# ── cup_component ───────────────────────────────────────────────────

class TestCupComponent:
    """cup_component: scaffold CUP component files for analysis tests."""

    def test_creates_filter_file(self, tmp_path):
        path = cup_component(tmp_path, "validate_email", "filter")
        assert path.exists()
        source = path.read_text()
        assert "class ValidateEmail" in source
        assert "def call" in source

    def test_creates_tap_file(self, tmp_path):
        path = cup_component(tmp_path, "audit_log", "tap")
        source = path.read_text()
        assert "class AuditLog" in source
        assert "def observe" in source

    def test_creates_hook_file(self, tmp_path):
        path = cup_component(tmp_path, "timing", "hook")
        source = path.read_text()
        assert "class Timing" in source
        assert "def before" in source
        assert "def after" in source

    def test_creates_stream_filter_file(self, tmp_path):
        path = cup_component(tmp_path, "line_parser", "stream-filter")
        source = path.read_text()
        assert "class LineParser" in source
        assert "def stream" in source

    def test_creates_builder_file(self, tmp_path):
        path = cup_component(tmp_path, "auth_pipeline", "builder")
        source = path.read_text()
        assert "def build_auth_pipeline" in source

    def test_creates_test_file_when_requested(self, tmp_path):
        cup_component(tmp_path, "validate", "filter", with_test=True)
        test_file = tmp_path / "tests" / "test_validate.py"
        assert test_file.exists()
        source = test_file.read_text()
        assert "test_" in source

    def test_custom_methods(self, tmp_path):
        path = cup_component(tmp_path, "auth", "filter", methods=["call", "validate", "refresh"])
        source = path.read_text()
        assert "def call" in source
        assert "def validate" in source
        assert "def refresh" in source


# ── RecordingTap / RecordingHook class usage ────────────────────────

class TestRecordingTap:
    def test_is_instance_check(self):
        tap = RecordingTap()
        assert hasattr(tap, "observe")
        assert hasattr(tap, "payloads")
        assert hasattr(tap, "call_count")

class TestRecordingHook:
    def test_is_instance_check(self):
        hook = RecordingHook()
        assert hasattr(hook, "before")
        assert hasattr(hook, "after")
        assert hasattr(hook, "on_error")
        assert hasattr(hook, "before_count")
        assert hasattr(hook, "after_count")
        assert hasattr(hook, "error_count")


# ── assert_keys_absent ──────────────────────────────────────────────

class TestAssertKeysAbsent:
    """assert_keys_absent: verify payload does NOT contain specified keys."""

    def test_passes_when_keys_missing(self):
        p = Payload({"name": "alice"})
        assert_keys_absent(p, "password", "secret")

    def test_fails_when_key_present(self):
        p = Payload({"name": "alice", "password": "oops"})
        with pytest.raises(AssertionError, match="password"):
            assert_keys_absent(p, "password")

    def test_fails_on_first_present_key(self):
        p = Payload({"a": 1, "b": 2})
        with pytest.raises(AssertionError, match="a"):
            assert_keys_absent(p, "a", "c")

    def test_empty_payload_always_passes(self):
        p = Payload({})
        assert_keys_absent(p, "anything", "at_all")


# ── mock_sdk_modules ────────────────────────────────────────────────

class TestMockSdkModules:
    """mock_sdk_modules: context manager for SDK module injection."""

    def test_single_module_injection(self):
        import sys
        with mock_sdk_modules("fake_sdk_test_xyz") as mods:
            assert "fake_sdk_test_xyz" in sys.modules
            assert "fake_sdk_test_xyz" in mods
        assert "fake_sdk_test_xyz" not in sys.modules

    def test_dotted_module_wiring(self):
        names = ["fake_parent", "fake_parent.child"]
        with mock_sdk_modules(names) as mods:
            parent = mods["fake_parent"]
            child = mods["fake_parent.child"]
            assert parent.child is child
        import sys
        assert "fake_parent" not in sys.modules
        assert "fake_parent.child" not in sys.modules

    def test_connector_prefix_cleanup(self):
        import sys
        sys.modules["codeupipe_test_conn.links"] = "sentinel"
        try:
            with mock_sdk_modules("fake_conn_sdk", connector_prefix="codeupipe_test_conn"):
                pass
            assert "codeupipe_test_conn.links" not in sys.modules
        finally:
            sys.modules.pop("codeupipe_test_conn.links", None)

    def test_restores_original_module(self):
        import sys
        original = type(sys)("original_placeholder")
        sys.modules["_test_restore_target"] = original
        try:
            with mock_sdk_modules("_test_restore_target"):
                assert sys.modules["_test_restore_target"] is not original
            assert sys.modules["_test_restore_target"] is original
        finally:
            sys.modules.pop("_test_restore_target", None)

    def test_string_arg_accepts_single_name(self):
        with mock_sdk_modules("single_test_mod_xyz") as mods:
            assert "single_test_mod_xyz" in mods


# ── cup_component: new kinds ────────────────────────────────────────

class TestCupComponentNewKinds:
    """cup_component: verify scaffolding for async-filter, async-tap, valve, pipeline, retry-filter."""

    def test_creates_async_filter(self, tmp_path):
        path = cup_component(tmp_path, "async_transform", "async-filter")
        source = path.read_text()
        assert "class AsyncTransform" in source
        assert "async def call" in source

    def test_creates_async_tap(self, tmp_path):
        path = cup_component(tmp_path, "async_logger", "async-tap")
        source = path.read_text()
        assert "class AsyncLogger" in source
        assert "async def observe" in source

    def test_creates_valve(self, tmp_path):
        path = cup_component(tmp_path, "age_gate", "valve")
        source = path.read_text()
        assert "AgeGate" in source
        assert "Valve" in source
        assert "def build_age_gate" in source

    def test_creates_pipeline(self, tmp_path):
        path = cup_component(tmp_path, "order_pipeline", "pipeline")
        source = path.read_text()
        assert "def build_order_pipeline" in source

    def test_creates_retry_filter(self, tmp_path):
        path = cup_component(tmp_path, "flaky_call", "retry-filter")
        source = path.read_text()
        assert "def build_flaky_call" in source

    def test_valve_with_test(self, tmp_path):
        cup_component(tmp_path, "age_gate", "valve", with_test=True)
        test_file = tmp_path / "tests" / "test_age_gate.py"
        assert test_file.exists()

    def test_pipeline_with_test(self, tmp_path):
        cup_component(tmp_path, "order_pipeline", "pipeline", with_test=True)
        test_file = tmp_path / "tests" / "test_order_pipeline.py"
        assert test_file.exists()
        source = test_file.read_text()
        assert "build_order_pipeline" in source

    def test_unknown_kind_raises(self, tmp_path):
        with pytest.raises(ValueError, match="Unknown kind"):
            cup_component(tmp_path, "nope", "foobar")
