"""Tests for runtime module — TapSwitch and HotSwap.

Covers:
- TapSwitch: disable/enable taps, disable_all, enable_all, status
- Pipeline._disabled_taps gate in run() and stream()
- HotSwap: run, reload, version tracking, safe rollback on bad config
"""

import asyncio
import json
import tempfile
from pathlib import Path

import pytest
from codeupipe.core.payload import Payload
from codeupipe.core.pipeline import Pipeline
from codeupipe.core.filter import Filter
from codeupipe.core.tap import Tap
from codeupipe.runtime import TapSwitch, HotSwap


# ── Helpers ──────────────────────────────────────────────────

class DoubleFilter(Filter):
    async def call(self, payload: Payload) -> Payload:
        return payload.insert("value", payload.get("value", 0) * 2)


class RecordTap(Tap):
    """Tap that records observed payloads."""
    def __init__(self):
        self.observed = []

    async def observe(self, payload: Payload) -> None:
        self.observed.append(payload.to_dict())


class AddTenFilter(Filter):
    async def call(self, payload: Payload) -> Payload:
        return payload.insert("value", payload.get("value", 0) + 10)


# ── TapSwitch Tests ──────────────────────────────────────────


class TestTapSwitch:
    """TapSwitch controls which taps are active at runtime."""

    def test_disable_tap_skips_observation(self):
        """Disabled taps are skipped during pipeline.run()."""
        tap = RecordTap()
        pipeline = Pipeline()
        pipeline.add_filter(DoubleFilter(), "double")
        pipeline.add_tap(tap, "recorder")

        switch = TapSwitch(pipeline)
        switch.disable("recorder")

        result = asyncio.run(pipeline.run(Payload({"value": 5})))
        assert result.get("value") == 10
        assert len(tap.observed) == 0  # tap was skipped

    def test_enable_tap_resumes_observation(self):
        """Re-enabled taps observe again."""
        tap = RecordTap()
        pipeline = Pipeline()
        pipeline.add_filter(DoubleFilter(), "double")
        pipeline.add_tap(tap, "recorder")

        switch = TapSwitch(pipeline)
        switch.disable("recorder")
        switch.enable("recorder")

        result = asyncio.run(pipeline.run(Payload({"value": 5})))
        assert result.get("value") == 10
        assert len(tap.observed) == 1

    def test_disable_all_silences_every_tap(self):
        """disable_all() disables every tap on the pipeline."""
        tap1 = RecordTap()
        tap2 = RecordTap()
        pipeline = Pipeline()
        pipeline.add_tap(tap1, "tap_a")
        pipeline.add_filter(DoubleFilter(), "double")
        pipeline.add_tap(tap2, "tap_b")

        switch = TapSwitch(pipeline)
        switch.disable_all()

        asyncio.run(pipeline.run(Payload({"value": 3})))
        assert len(tap1.observed) == 0
        assert len(tap2.observed) == 0

    def test_enable_all_restores_all_taps(self):
        """enable_all() after disable_all() restores observation."""
        tap1 = RecordTap()
        pipeline = Pipeline()
        pipeline.add_tap(tap1, "tap_a")
        pipeline.add_filter(DoubleFilter(), "double")

        switch = TapSwitch(pipeline)
        switch.disable_all()
        switch.enable_all()

        asyncio.run(pipeline.run(Payload({"value": 3})))
        assert len(tap1.observed) == 1

    def test_status_returns_tap_states(self):
        """status() shows enabled/disabled for each tap."""
        pipeline = Pipeline()
        pipeline.add_tap(RecordTap(), "tap_a")
        pipeline.add_tap(RecordTap(), "tap_b")
        pipeline.add_filter(DoubleFilter(), "double")

        switch = TapSwitch(pipeline)
        switch.disable("tap_a")

        status = switch.status()
        assert status == {"tap_a": False, "tap_b": True}

    def test_is_disabled(self):
        """is_disabled() checks individual tap state."""
        pipeline = Pipeline()
        pipeline.add_tap(RecordTap(), "tap_a")

        switch = TapSwitch(pipeline)
        assert not switch.is_disabled("tap_a")
        switch.disable("tap_a")
        assert switch.is_disabled("tap_a")

    def test_disabled_property(self):
        """disabled property returns a copy of disabled names."""
        pipeline = Pipeline()
        pipeline.add_tap(RecordTap(), "tap_a")
        pipeline.add_tap(RecordTap(), "tap_b")

        switch = TapSwitch(pipeline)
        switch.disable("tap_b")
        assert switch.disabled == {"tap_b"}

    def test_disabled_taps_marked_skipped_in_state(self):
        """Disabled taps are marked as skipped in pipeline state."""
        tap = RecordTap()
        pipeline = Pipeline()
        pipeline.add_filter(DoubleFilter(), "double")
        pipeline.add_tap(tap, "recorder")

        switch = TapSwitch(pipeline)
        switch.disable("recorder")

        asyncio.run(pipeline.run(Payload({"value": 5})))
        assert "recorder" in pipeline.state.skipped

    def test_filters_unaffected_by_tap_toggle(self):
        """Disabling a tap doesn't affect filter execution."""
        tap = RecordTap()
        pipeline = Pipeline()
        pipeline.add_filter(DoubleFilter(), "double")
        pipeline.add_filter(AddTenFilter(), "add_ten")
        pipeline.add_tap(tap, "recorder")

        switch = TapSwitch(pipeline)
        switch.disable("recorder")

        result = asyncio.run(pipeline.run(Payload({"value": 5})))
        # 5 * 2 = 10, 10 + 10 = 20
        assert result.get("value") == 20


# ── Pipeline._disabled_taps gate in stream() ────────────────


class TestTapSwitchStreaming:
    """TapSwitch works with pipeline.stream() too."""

    def test_disabled_tap_skipped_in_stream(self):
        """Disabled taps are skipped during streaming."""
        tap = RecordTap()
        pipeline = Pipeline()
        pipeline.add_filter(DoubleFilter(), "double")
        pipeline.add_tap(tap, "recorder")

        switch = TapSwitch(pipeline)
        switch.disable("recorder")

        async def source():
            yield Payload({"value": 1})
            yield Payload({"value": 2})

        async def collect():
            results = []
            async for chunk in pipeline.stream(source()):
                results.append(chunk.get("value"))
            return results

        results = asyncio.run(collect())
        assert results == [2, 4]
        assert len(tap.observed) == 0  # tap was skipped


# ── HotSwap Tests ────────────────────────────────────────────


class TestHotSwap:
    """HotSwap atomically replaces the active pipeline."""

    def _write_config(self, tmpdir, steps):
        """Write a pipeline config JSON file."""
        config = {"pipeline": {"steps": steps}}
        path = str(tmpdir / "pipeline.json")
        Path(path).write_text(json.dumps(config))
        return path

    def test_initial_load_and_run(self, tmp_path):
        """HotSwap loads config and runs payloads."""
        config_path = self._write_config(tmp_path, [])
        from codeupipe.registry import Registry
        registry = Registry()
        swap = HotSwap(config_path, registry=registry)

        assert swap.version == 1
        assert swap.config_path == config_path

        result = asyncio.run(swap.run(Payload({"x": 1})))
        assert result.get("x") == 1  # empty pipeline passes through

    def test_reload_increments_version(self, tmp_path):
        """reload() bumps the version counter."""
        config_path = self._write_config(tmp_path, [])
        from codeupipe.registry import Registry
        registry = Registry()
        swap = HotSwap(config_path, registry=registry)

        assert swap.version == 1
        info = swap.reload()
        assert swap.version == 2
        assert info["version"] == 2

    def test_reload_different_config(self, tmp_path):
        """reload() can switch to a different config file."""
        config_a = self._write_config(tmp_path, [])
        config_b = str(tmp_path / "pipeline_b.json")
        Path(config_b).write_text(json.dumps({"pipeline": {"steps": []}}))

        from codeupipe.registry import Registry
        registry = Registry()
        swap = HotSwap(config_a, registry=registry)

        swap.reload(config_b)
        assert swap.config_path == config_b
        assert swap.version == 2

    def test_reload_bad_config_keeps_old_pipeline(self, tmp_path):
        """If reload fails, the old pipeline stays active (safe rollback)."""
        config_path = self._write_config(tmp_path, [])
        bad_path = str(tmp_path / "bad.json")
        Path(bad_path).write_text("not valid json {{{{")

        from codeupipe.registry import Registry
        registry = Registry()
        swap = HotSwap(config_path, registry=registry)

        with pytest.raises(Exception):
            swap.reload(bad_path)

        # Original pipeline still works
        assert swap.version == 1
        result = asyncio.run(swap.run(Payload({"x": 42})))
        assert result.get("x") == 42

    def test_run_sync(self, tmp_path):
        """run_sync() provides synchronous execution."""
        config_path = self._write_config(tmp_path, [])
        from codeupipe.registry import Registry
        registry = Registry()
        swap = HotSwap(config_path, registry=registry)

        result = swap.run_sync(Payload({"value": 99}))
        assert result.get("value") == 99

    def test_pipeline_property(self, tmp_path):
        """pipeline property exposes the current Pipeline instance."""
        config_path = self._write_config(tmp_path, [])
        from codeupipe.registry import Registry
        registry = Registry()
        swap = HotSwap(config_path, registry=registry)

        assert isinstance(swap.pipeline, Pipeline)
