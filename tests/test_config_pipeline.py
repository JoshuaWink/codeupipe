"""Tests for Pipeline.from_config — config-driven pipeline assembly."""

import json
import pytest

from codeupipe import Payload, Pipeline
from codeupipe.registry import Registry


# ── Helpers ──────────────────────────────────────────────────

class AddTenFilter:
    def call(self, payload: Payload) -> Payload:
        return payload.insert("value", payload.get("value", 0) + 10)


class MultiplyFilter:
    def call(self, payload: Payload) -> Payload:
        return payload.insert("value", payload.get("value", 0) * 2)


class LogTap:
    def __init__(self):
        self.seen = []

    def observe(self, payload: Payload) -> None:
        self.seen.append(payload.get("value"))


# ── TOML Config ──────────────────────────────────────────────

class TestFromTOML:
    """Pipeline.from_config with TOML files."""

    def test_load_toml_basic(self, tmp_path):
        reg = Registry()
        reg.register(AddTenFilter)
        reg.register(MultiplyFilter)

        config_file = tmp_path / "pipeline.toml"
        config_file.write_text(
            '[pipeline]\n'
            'name = "math"\n'
            '\n'
            '[[pipeline.steps]]\n'
            'name = "AddTenFilter"\n'
            'type = "filter"\n'
            '\n'
            '[[pipeline.steps]]\n'
            'name = "MultiplyFilter"\n'
            'type = "filter"\n'
        )

        pipe = Pipeline.from_config(str(config_file), registry=reg)
        assert pipe is not None

    @pytest.mark.asyncio
    async def test_toml_pipeline_runs(self, tmp_path):
        reg = Registry()
        reg.register(AddTenFilter)
        reg.register(MultiplyFilter)

        config_file = tmp_path / "pipeline.toml"
        config_file.write_text(
            '[pipeline]\n'
            'name = "math"\n'
            '\n'
            '[[pipeline.steps]]\n'
            'name = "AddTenFilter"\n'
            'type = "filter"\n'
            '\n'
            '[[pipeline.steps]]\n'
            'name = "MultiplyFilter"\n'
            'type = "filter"\n'
        )

        pipe = Pipeline.from_config(str(config_file), registry=reg)
        result = await pipe.run(Payload({"value": 5}))
        assert result.get("value") == 30  # (5 + 10) * 2

    def test_toml_with_tap(self, tmp_path):
        reg = Registry()
        reg.register(AddTenFilter)
        reg.register(LogTap)

        config_file = tmp_path / "pipeline.toml"
        config_file.write_text(
            '[pipeline]\n'
            'name = "with-tap"\n'
            '\n'
            '[[pipeline.steps]]\n'
            'name = "AddTenFilter"\n'
            'type = "filter"\n'
            '\n'
            '[[pipeline.steps]]\n'
            'name = "LogTap"\n'
            'type = "tap"\n'
        )

        pipe = Pipeline.from_config(str(config_file), registry=reg)
        assert pipe is not None


# ── JSON Config ──────────────────────────────────────────────

class TestFromJSON:
    """Pipeline.from_config with JSON files (universal fallback)."""

    def test_load_json_basic(self, tmp_path):
        reg = Registry()
        reg.register(AddTenFilter)

        config_file = tmp_path / "pipeline.json"
        config_file.write_text(json.dumps({
            "pipeline": {
                "name": "simple",
                "steps": [
                    {"name": "AddTenFilter", "type": "filter"},
                ],
            }
        }))

        pipe = Pipeline.from_config(str(config_file), registry=reg)
        assert pipe is not None

    @pytest.mark.asyncio
    async def test_json_pipeline_runs(self, tmp_path):
        reg = Registry()
        reg.register(AddTenFilter)
        reg.register(MultiplyFilter)

        config_file = tmp_path / "pipeline.json"
        config_file.write_text(json.dumps({
            "pipeline": {
                "name": "math",
                "steps": [
                    {"name": "AddTenFilter", "type": "filter"},
                    {"name": "MultiplyFilter", "type": "filter"},
                ],
            }
        }))

        pipe = Pipeline.from_config(str(config_file), registry=reg)
        result = await pipe.run(Payload({"value": 5}))
        assert result.get("value") == 30

    def test_json_with_step_config(self, tmp_path):
        """Steps can pass config kwargs to the registry."""
        reg = Registry()

        def make_adder(**kwargs):
            class Adder:
                def call(self, payload):
                    n = kwargs.get("amount", 1)
                    return payload.insert("value", payload.get("value", 0) + n)
            return Adder()

        reg.register("add", make_adder)

        config_file = tmp_path / "pipeline.json"
        config_file.write_text(json.dumps({
            "pipeline": {
                "name": "configured",
                "steps": [
                    {"name": "add", "type": "filter", "config": {"amount": 42}},
                ],
            }
        }))

        pipe = Pipeline.from_config(str(config_file), registry=reg)
        assert pipe is not None


# ── Error Handling ───────────────────────────────────────────

class TestConfigErrors:
    """Edge cases and error reporting."""

    def test_unknown_component_raises(self, tmp_path):
        reg = Registry()
        config_file = tmp_path / "pipeline.json"
        config_file.write_text(json.dumps({
            "pipeline": {
                "name": "broken",
                "steps": [{"name": "DoesNotExist", "type": "filter"}],
            }
        }))

        with pytest.raises(KeyError, match="DoesNotExist"):
            Pipeline.from_config(str(config_file), registry=reg)

    def test_missing_pipeline_key_raises(self, tmp_path):
        reg = Registry()
        config_file = tmp_path / "pipeline.json"
        config_file.write_text(json.dumps({"not_pipeline": {}}))

        with pytest.raises(ValueError, match="pipeline"):
            Pipeline.from_config(str(config_file), registry=reg)

    def test_missing_steps_raises(self, tmp_path):
        reg = Registry()
        config_file = tmp_path / "pipeline.json"
        config_file.write_text(json.dumps({
            "pipeline": {"name": "empty"}
        }))

        with pytest.raises(ValueError, match="steps"):
            Pipeline.from_config(str(config_file), registry=reg)

    def test_unsupported_format_raises(self, tmp_path):
        reg = Registry()
        config_file = tmp_path / "pipeline.xml"
        config_file.write_text("<pipeline/>")

        with pytest.raises(ValueError, match="Unsupported"):
            Pipeline.from_config(str(config_file), registry=reg)

    def test_nonexistent_file_raises(self):
        reg = Registry()
        with pytest.raises(FileNotFoundError):
            Pipeline.from_config("/no/such/file.json", registry=reg)

    def test_unknown_step_type_raises(self, tmp_path):
        reg = Registry()
        reg.register(AddTenFilter)
        config_file = tmp_path / "pipeline.json"
        config_file.write_text(json.dumps({
            "pipeline": {
                "name": "bad-type",
                "steps": [{"name": "AddTenFilter", "type": "quantum-filter"}],
            }
        }))

        with pytest.raises(ValueError, match="quantum-filter"):
            Pipeline.from_config(str(config_file), registry=reg)
