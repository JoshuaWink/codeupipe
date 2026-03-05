"""
Unit tests for converter filters — each filter tested in isolation.
"""

import json
import pytest
import asyncio
from pathlib import Path
from codeupipe import Payload, Pipeline, Valve

from codeupipe.converter.config import load_config, DEFAULT_CONFIG, PATTERN_DEFAULTS
from codeupipe.converter.filters.parse_config import ParseConfigFilter
from codeupipe.converter.filters.analyze import AnalyzePipelineFilter
from codeupipe.converter.filters.classify import ClassifyStepsFilter, _match_role
from codeupipe.converter.filters.classify_files import ClassifyFilesFilter, _match_dir_to_role
from codeupipe.converter.filters.generate_export import GenerateExportFilter
from codeupipe.converter.filters.scan_project import ScanProjectFilter
from codeupipe.converter.filters.generate_import import GenerateImportFilter, _extract_functions
from codeupipe.converter.taps.conversion_log import ConversionLogTap


# ──────────────────────────────────────────────
# Config
# ──────────────────────────────────────────────

class TestConfig:
    def test_default_config_is_flat(self):
        config = load_config()
        assert config["pattern"] == "flat"
        assert "step" in config["roles"]

    def test_load_mvc_pattern(self):
        config = load_config(pattern="mvc")
        assert config["pattern"] == "mvc"
        assert "model" in config["roles"]
        assert "view" in config["roles"]
        assert "controller" in config["roles"]
        assert "middleware" in config["roles"]

    def test_load_clean_pattern(self):
        config = load_config(pattern="clean")
        assert config["pattern"] == "clean"
        assert "use_case" in config["roles"]
        assert "entity" in config["roles"]

    def test_load_hexagonal_pattern(self):
        config = load_config(pattern="hexagonal")
        assert config["pattern"] == "hexagonal"
        assert "domain" in config["roles"]
        assert "adapter_inbound" in config["roles"]
        assert "adapter_outbound" in config["roles"]

    def test_load_from_json_file(self, tmp_path):
        config_data = {
            "pattern": "mvc",
            "roles": {"model": ["db_*"], "view": ["render_*"]},
        }
        config_file = tmp_path / ".cup.json"
        config_file.write_text(json.dumps(config_data))

        config = load_config(config_path=str(config_file))
        assert config["pattern"] == "mvc"
        assert config["roles"]["model"] == ["db_*"]
        assert config["roles"]["view"] == ["render_*"]

    def test_unknown_pattern_falls_back_to_flat(self):
        config = load_config(pattern="nonexistent")
        assert config["pattern"] == "flat"

    def test_output_base_defaults_to_src(self):
        config = load_config(pattern="mvc")
        assert config["output"]["base"] == "src/"

    def test_pattern_defaults_all_have_roles_and_output(self):
        for name, defaults in PATTERN_DEFAULTS.items():
            assert "roles" in defaults, f"{name} missing roles"
            assert "output" in defaults, f"{name} missing output"


# ──────────────────────────────────────────────
# ParseConfigFilter
# ──────────────────────────────────────────────

class TestParseConfigFilter:
    def test_parse_with_pattern(self):
        f = ParseConfigFilter()
        result = f.call(Payload({"pattern": "mvc"}))
        config = result.get("config")
        assert config["pattern"] == "mvc"
        assert "model" in config["roles"]

    def test_parse_with_json_file(self, tmp_path):
        config_file = tmp_path / ".cup.json"
        config_file.write_text(json.dumps({"pattern": "clean"}))

        f = ParseConfigFilter()
        result = f.call(Payload({"config_path": str(config_file)}))
        assert result.get("config")["pattern"] == "clean"

    def test_parse_defaults_when_empty(self):
        f = ParseConfigFilter()
        result = f.call(Payload({}))
        assert result.get("config")["pattern"] == "flat"


# ──────────────────────────────────────────────
# AnalyzePipelineFilter
# ──────────────────────────────────────────────

class TestAnalyzePipelineFilter:
    def _make_sample_pipeline(self):
        class FetchUser:
            def call(self, payload):
                return payload.insert("user", "alice")

        class AuditTap:
            def observe(self, payload):
                pass

        class AdminFilter:
            def call(self, payload):
                return payload.insert("admin", True)

        p = Pipeline()
        p.add_filter(FetchUser(), name="fetch_user")
        p.add_tap(AuditTap(), name="audit_tap")
        p.add_filter(
            Valve("admin_check", AdminFilter(), lambda p: p.get("role") == "admin"),
            name="admin_check",
        )
        return p

    def test_extracts_all_steps(self):
        pipeline = self._make_sample_pipeline()
        f = AnalyzePipelineFilter()
        result = f.call(Payload({"pipeline": pipeline}))

        steps = result.get("steps")
        assert len(steps) == 3
        assert steps[0]["name"] == "fetch_user"
        assert steps[0]["type"] == "filter"
        assert steps[1]["name"] == "audit_tap"
        assert steps[1]["type"] == "tap"
        assert steps[2]["name"] == "admin_check"
        assert steps[2]["type"] == "valve"
        assert steps[2]["is_valve"] is True

    def test_extracts_hooks(self):
        from codeupipe import Hook

        class TimingHook(Hook):
            pass

        pipeline = Pipeline()
        pipeline.use_hook(TimingHook())

        f = AnalyzePipelineFilter()
        result = f.call(Payload({"pipeline": pipeline}))

        hooks = result.get("hooks")
        assert len(hooks) == 1
        assert hooks[0]["class_name"] == "TimingHook"
        assert hooks[0]["type"] == "hook"

    def test_raises_without_pipeline(self):
        f = AnalyzePipelineFilter()
        with pytest.raises(ValueError, match="pipeline"):
            f.call(Payload({}))


# ──────────────────────────────────────────────
# ClassifyStepsFilter
# ──────────────────────────────────────────────

class TestClassifyStepsFilter:
    def test_classify_by_name_glob(self):
        roles = {"model": ["fetch_*", "save_*"], "controller": ["validate_*"]}
        assert _match_role("fetch_user", "filter", roles) == "model"
        assert _match_role("save_order", "filter", roles) == "model"
        assert _match_role("validate_input", "filter", roles) == "controller"

    def test_classify_by_type_token(self):
        roles = {"middleware": ["_tap", "_hook", "_valve"]}
        assert _match_role("audit_log", "tap", roles) == "middleware"
        assert _match_role("timing", "hook", roles) == "middleware"
        assert _match_role("premium_gate", "valve", roles) == "middleware"

    def test_uncategorized_fallback(self):
        roles = {"model": ["fetch_*"]}
        assert _match_role("unknown_step", "filter", roles) == "uncategorized"

    def test_full_classify_filter(self):
        steps = [
            {"name": "fetch_order", "type": "filter", "class_name": "FetchOrder"},
            {"name": "validate_input", "type": "filter", "class_name": "ValidateInput"},
            {"name": "audit_tap", "type": "tap", "class_name": "AuditTap"},
        ]
        hooks = [{"class_name": "TimingHook", "type": "hook"}]
        config = load_config(pattern="mvc")

        f = ClassifyStepsFilter()
        result = f.call(Payload({
            "steps": steps,
            "hooks": hooks,
            "config": config,
        }))

        classified = result.get("classified")
        assert "model" in classified
        assert any(s["name"] == "fetch_order" for s in classified["model"])
        assert "controller" in classified
        assert any(s["name"] == "validate_input" for s in classified["controller"])
        assert "middleware" in classified


# ──────────────────────────────────────────────
# ClassifyFilesFilter
# ──────────────────────────────────────────────

class TestClassifyFilesFilter:
    def test_match_dir_exact(self):
        dir_map = {"models": "model", "views": "view"}
        assert _match_dir_to_role("models", dir_map) == "model"
        assert _match_dir_to_role("views", dir_map) == "view"

    def test_match_dir_nested(self):
        dir_map = {"adapters/inbound": "adapter_inbound"}
        assert _match_dir_to_role("adapters/inbound", dir_map) == "adapter_inbound"
        assert _match_dir_to_role("adapters/inbound/rest", dir_map) == "adapter_inbound"

    def test_uncategorized_unknown_dir(self):
        dir_map = {"models": "model"}
        assert _match_dir_to_role("unknown", dir_map) == "uncategorized"

    def test_full_filter(self):
        config = load_config(pattern="mvc")
        source_files = [
            {"name": "fetch_user", "dir": "models", "content": "def fetch_user(data): return data"},
            {"name": "render_page", "dir": "views", "content": "def render_page(data): pass"},
        ]
        f = ClassifyFilesFilter()
        result = f.call(Payload({"source_files": source_files, "config": config}))
        classified = result.get("classified_files")
        assert "model" in classified
        assert "view" in classified


# ──────────────────────────────────────────────
# GenerateExportFilter
# ──────────────────────────────────────────────

class TestGenerateExportFilter:
    def test_generates_files_for_each_step(self):
        classified = {
            "model": [{"name": "fetch_user", "type": "filter", "class_name": "FetchUser", "source": None}],
            "controller": [{"name": "validate_input", "type": "filter", "class_name": "ValidateInput", "source": None}],
        }
        config = load_config(pattern="mvc")
        steps = [
            {"name": "fetch_user", "type": "filter"},
            {"name": "validate_input", "type": "filter"},
        ]

        f = GenerateExportFilter()
        result = f.call(Payload({
            "classified": classified,
            "config": config,
            "steps": steps,
            "hooks": [],
        }))

        files = result.get("files")
        paths = [f["path"] for f in files]

        # Should have one file per step + orchestrator
        assert any("fetch_user.py" in p for p in paths)
        assert any("validate_input.py" in p for p in paths)
        assert any("pipeline.py" in p for p in paths)

    def test_generates_valve_with_predicate(self):
        classified = {
            "middleware": [{"name": "premium_check", "type": "valve", "class_name": "Valve", "source": None}],
        }
        config = load_config(pattern="mvc")
        steps = [{"name": "premium_check", "type": "valve"}]

        f = GenerateExportFilter()
        result = f.call(Payload({
            "classified": classified,
            "config": config,
            "steps": steps,
            "hooks": [],
        }))

        files = result.get("files")
        valve_file = next(f for f in files if "premium_check.py" in f["path"])
        assert "def premium_check_predicate" in valve_file["content"]

    def test_generates_tap_with_none_return(self):
        classified = {
            "middleware": [{"name": "audit_log", "type": "tap", "class_name": "AuditTap", "source": None}],
        }
        config = load_config(pattern="mvc")
        steps = [{"name": "audit_log", "type": "tap"}]

        f = GenerateExportFilter()
        result = f.call(Payload({
            "classified": classified,
            "config": config,
            "steps": steps,
            "hooks": [],
        }))

        files = result.get("files")
        tap_file = next(f for f in files if "audit_log.py" in f["path"])
        assert "-> None:" in tap_file["content"]

    def test_orchestrator_calls_in_order(self):
        classified = {
            "model": [{"name": "fetch_user", "type": "filter", "class_name": "FetchUser", "source": None}],
            "controller": [{"name": "validate_input", "type": "filter", "class_name": "ValidateInput", "source": None}],
        }
        config = load_config(pattern="mvc")
        steps = [
            {"name": "fetch_user", "type": "filter"},
            {"name": "validate_input", "type": "filter"},
        ]

        f = GenerateExportFilter()
        result = f.call(Payload({
            "classified": classified,
            "config": config,
            "steps": steps,
            "hooks": [],
        }))

        files = result.get("files")
        orch = next(f for f in files if f["path"].endswith("pipeline.py"))
        content = orch["content"]

        # Both steps should appear in order
        fetch_pos = content.index("fetch_user")
        validate_pos = content.index("validate_input")
        assert fetch_pos < validate_pos


# ──────────────────────────────────────────────
# ScanProjectFilter
# ──────────────────────────────────────────────

class TestScanProjectFilter:
    def test_scans_python_files(self, tmp_path):
        (tmp_path / "models").mkdir()
        (tmp_path / "models" / "user.py").write_text("def fetch_user(data): return data\n")
        (tmp_path / "views").mkdir()
        (tmp_path / "views" / "page.py").write_text("def render(data): pass\n")
        (tmp_path / "models" / "__init__.py").write_text("")  # should be skipped

        f = ScanProjectFilter()
        result = f.call(Payload({"project_path": str(tmp_path)}))

        source_files = result.get("source_files")
        names = [sf["name"] for sf in source_files]
        assert "user" in names
        assert "page" in names
        assert "__init__" not in names

    def test_captures_directory(self, tmp_path):
        (tmp_path / "models").mkdir()
        (tmp_path / "models" / "user.py").write_text("pass\n")

        f = ScanProjectFilter()
        result = f.call(Payload({"project_path": str(tmp_path)}))

        source_files = result.get("source_files")
        assert source_files[0]["dir"] == "models"

    def test_raises_without_project_path(self):
        f = ScanProjectFilter()
        with pytest.raises(ValueError, match="project_path"):
            f.call(Payload({}))

    def test_raises_for_nonexistent_dir(self):
        f = ScanProjectFilter()
        with pytest.raises(ValueError, match="Not a directory"):
            f.call(Payload({"project_path": "/tmp/nonexistent_dir_abc123"}))


# ──────────────────────────────────────────────
# GenerateImportFilter
# ──────────────────────────────────────────────

class TestGenerateImportFilter:
    def test_extract_functions_finds_defs(self):
        source = '''
def fetch_user(data: dict) -> dict:
    data["user"] = "alice"
    return data

def log_step(data: dict) -> None:
    print(data)
'''
        fns = _extract_functions(source)
        assert len(fns) == 2
        assert fns[0][0] == "fetch_user"
        assert fns[1][0] == "log_step"

    def test_generates_filter_for_data_function(self):
        classified_files = {
            "model": [{
                "name": "fetch_user",
                "content": 'def fetch_user(data: dict) -> dict:\n    data["user"] = "alice"\n    return data\n',
            }],
        }
        config = load_config(pattern="mvc")

        f = GenerateImportFilter()
        result = f.call(Payload({
            "classified_files": classified_files,
            "config": config,
        }))

        cup_files = result.get("cup_files")
        assert len(cup_files) >= 1
        assert "FetchUserFilter" in cup_files[0]["content"]
        assert "def call(self, payload)" in cup_files[0]["content"]

    def test_generates_pipeline_code(self):
        classified_files = {
            "model": [{
                "name": "fetch_user",
                "content": 'def fetch_user(data: dict) -> dict:\n    data["user"] = "a"\n    return data\n',
            }],
            "middleware": [{
                "name": "log_step",
                "content": "def log_step(data: dict) -> None:\n    print(data)\n",
            }],
        }
        config = load_config(pattern="mvc")

        f = GenerateImportFilter()
        result = f.call(Payload({
            "classified_files": classified_files,
            "config": config,
        }))

        pipeline_code = result.get("cup_pipeline")
        assert "build_pipeline" in pipeline_code
        assert "Pipeline" in pipeline_code


# ──────────────────────────────────────────────
# ConversionLogTap
# ──────────────────────────────────────────────

class TestConversionLogTap:
    def test_logs_config(self):
        tap = ConversionLogTap()
        tap.observe(Payload({"config": {"pattern": "mvc"}}))
        assert any("mvc" in e for e in tap.entries)

    def test_logs_steps(self):
        tap = ConversionLogTap()
        tap.observe(Payload({"steps": [1, 2, 3], "config": {"pattern": "mvc"}}))
        assert any("3 steps" in e for e in tap.entries)

    def test_logs_classified(self):
        tap = ConversionLogTap()
        tap.observe(Payload({"classified": {"model": [], "view": []}, "config": {"pattern": "mvc"}}))
        assert any("roles" in e for e in tap.entries)
