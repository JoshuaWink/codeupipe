"""
Integration tests — full export and import pipelines with real CUP Pipelines.
"""

import asyncio
import pytest
import pytest_asyncio
from codeupipe import Payload, Pipeline, Valve, Hook

from codeupipe.converter.pipelines.export_pipeline import build_export_pipeline
from codeupipe.converter.pipelines.import_pipeline import build_import_pipeline
from codeupipe.converter.taps.conversion_log import ConversionLogTap


# ──────────────────────────────────────────────
# Sample CUP components for testing
# ──────────────────────────────────────────────

class FetchOrderFilter:
    def call(self, payload):
        return payload.insert("order", {"id": 1, "items": ["widget"]})


class ValidateOrderFilter:
    def call(self, payload):
        order = payload.get("order")
        if not order:
            raise ValueError("No order")
        return payload.insert("validated", True)


class CalcTotalFilter:
    def call(self, payload):
        return payload.insert("total", 42.0)


class FormatReceiptFilter:
    def call(self, payload):
        return payload.insert("receipt", f"Total: ${payload.get('total', 0)}")


class SaveOrderFilter:
    def call(self, payload):
        return payload.insert("saved", True)


class AuditTap:
    def observe(self, payload):
        pass


class PremiumDiscountFilter:
    def call(self, payload):
        total = payload.get("total", 0)
        return payload.insert("total", total * 0.9)


class TimingHook(Hook):
    pass


def _build_sample_pipeline():
    """Build a realistic CUP pipeline for testing."""
    p = Pipeline()
    p.add_filter(FetchOrderFilter(), name="fetch_order")
    p.add_filter(ValidateOrderFilter(), name="validate_order")
    p.add_filter(CalcTotalFilter(), name="calc_total")
    p.add_filter(
        Valve("premium_discount", PremiumDiscountFilter(), lambda p: p.get("tier") == "premium"),
        name="premium_discount",
    )
    p.add_tap(AuditTap(), name="audit_tap")
    p.add_filter(FormatReceiptFilter(), name="format_receipt")
    p.add_filter(SaveOrderFilter(), name="save_order")
    p.use_hook(TimingHook())
    return p


# ──────────────────────────────────────────────
# Export Pipeline Integration
# ──────────────────────────────────────────────

class TestExportPipeline:
    @pytest.mark.asyncio(loop_scope="function")
    async def test_export_mvc_generates_files(self):
        sample = _build_sample_pipeline()
        log_tap = ConversionLogTap()
        export = build_export_pipeline(log_tap=log_tap)

        result = await export.run(Payload({
            "pipeline": sample,
            "pattern": "mvc",
        }))

        files = result.get("files")
        assert files is not None
        assert len(files) > 0

        paths = [f["path"] for f in files]
        # Model: fetch_*, save_*
        assert any("models/" in p and "fetch_order" in p for p in paths)
        assert any("models/" in p and "save_order" in p for p in paths)
        # View: format_*
        assert any("views/" in p and "format_receipt" in p for p in paths)
        # Controller: validate_*, calc_*
        assert any("controllers/" in p and "validate_order" in p for p in paths)
        assert any("controllers/" in p and "calc_total" in p for p in paths)
        # Middleware: valve, tap
        assert any("middleware/" in p for p in paths)
        # Orchestrator
        assert any("pipeline.py" in p for p in paths)

    @pytest.mark.asyncio(loop_scope="function")
    async def test_export_clean_generates_files(self):
        sample = _build_sample_pipeline()
        export = build_export_pipeline()

        result = await export.run(Payload({
            "pipeline": sample,
            "pattern": "clean",
        }))

        files = result.get("files")
        paths = [f["path"] for f in files]
        # use_case: calc_*, process_*, validate_*
        assert any("use_cases/" in p for p in paths)
        # interface_adapter: fetch_*, save_*
        assert any("interface_adapters/" in p for p in paths)

    @pytest.mark.asyncio(loop_scope="function")
    async def test_export_flat_generates_files(self):
        sample = _build_sample_pipeline()
        export = build_export_pipeline()

        result = await export.run(Payload({
            "pipeline": sample,
            "pattern": "flat",
        }))

        files = result.get("files")
        paths = [f["path"] for f in files]
        # All in steps/
        assert all("steps/" in p or "pipeline.py" in p for p in paths)

    @pytest.mark.asyncio(loop_scope="function")
    async def test_export_tracks_state(self):
        sample = _build_sample_pipeline()
        export = build_export_pipeline()

        await export.run(Payload({
            "pipeline": sample,
            "pattern": "mvc",
        }))

        assert "parse_config" in export.state.executed
        assert "analyze_pipeline" in export.state.executed
        assert "classify_steps" in export.state.executed
        assert "generate_export" in export.state.executed

    @pytest.mark.asyncio(loop_scope="function")
    async def test_export_log_tap_captures_entries(self):
        sample = _build_sample_pipeline()
        log_tap = ConversionLogTap()
        export = build_export_pipeline(log_tap=log_tap)

        await export.run(Payload({
            "pipeline": sample,
            "pattern": "mvc",
        }))

        assert len(log_tap.entries) > 0

    @pytest.mark.asyncio(loop_scope="function")
    async def test_export_orchestrator_has_correct_sequence(self):
        sample = _build_sample_pipeline()
        export = build_export_pipeline()

        result = await export.run(Payload({
            "pipeline": sample,
            "pattern": "mvc",
        }))

        files = result.get("files")
        orch = next(f for f in files if f["path"].endswith("pipeline.py"))
        content = orch["content"]

        # Valve should generate if-statement
        assert "premium_discount_predicate" in content or "if " in content

    @pytest.mark.asyncio(loop_scope="function")
    async def test_export_generated_code_is_valid_python(self):
        sample = _build_sample_pipeline()
        export = build_export_pipeline()

        result = await export.run(Payload({
            "pipeline": sample,
            "pattern": "mvc",
        }))

        files = result.get("files")
        for f in files:
            # Each file should be valid Python (compile without error)
            try:
                compile(f["content"], f["path"], "exec")
            except SyntaxError as e:
                pytest.fail(f"Invalid Python in {f['path']}: {e}")


# ──────────────────────────────────────────────
# Import Pipeline Integration
# ──────────────────────────────────────────────

class TestImportPipeline:
    def _create_mvc_project(self, tmp_path):
        """Create a minimal MVC project on disk."""
        (tmp_path / "models").mkdir()
        (tmp_path / "models" / "fetch_user.py").write_text(
            'def fetch_user(data: dict) -> dict:\n    data["user"] = "alice"\n    return data\n'
        )
        (tmp_path / "models" / "save_user.py").write_text(
            'def save_user(data: dict) -> dict:\n    data["saved"] = True\n    return data\n'
        )
        (tmp_path / "views").mkdir()
        (tmp_path / "views" / "format_response.py").write_text(
            'def format_response(data: dict) -> dict:\n    data["formatted"] = True\n    return data\n'
        )
        (tmp_path / "controllers").mkdir()
        (tmp_path / "controllers" / "validate_input.py").write_text(
            'def validate_input(data: dict) -> dict:\n    if not data.get("name"):\n        raise ValueError("Missing name")\n    return data\n'
        )
        (tmp_path / "middleware").mkdir()
        (tmp_path / "middleware" / "log_request.py").write_text(
            'def log_request(data: dict) -> None:\n    print(f"Request: {data}")\n'
        )

    @pytest.mark.asyncio(loop_scope="function")
    async def test_import_mvc_generates_cup_files(self, tmp_path):
        self._create_mvc_project(tmp_path)
        imp = build_import_pipeline()

        result = await imp.run(Payload({
            "project_path": str(tmp_path),
            "pattern": "mvc",
        }))

        cup_files = result.get("cup_files")
        assert cup_files is not None
        assert len(cup_files) > 0

        # Should generate Filter classes
        contents = [f["content"] for f in cup_files]
        assert any("FetchUserFilter" in c for c in contents)
        assert any("SaveUserFilter" in c for c in contents)

    @pytest.mark.asyncio(loop_scope="function")
    async def test_import_generates_pipeline_code(self, tmp_path):
        self._create_mvc_project(tmp_path)
        imp = build_import_pipeline()

        result = await imp.run(Payload({
            "project_path": str(tmp_path),
            "pattern": "mvc",
        }))

        pipeline_code = result.get("cup_pipeline")
        assert pipeline_code is not None
        assert "build_pipeline" in pipeline_code
        assert "Pipeline" in pipeline_code

    @pytest.mark.asyncio(loop_scope="function")
    async def test_import_tracks_state(self, tmp_path):
        self._create_mvc_project(tmp_path)
        imp = build_import_pipeline()

        await imp.run(Payload({
            "project_path": str(tmp_path),
            "pattern": "mvc",
        }))

        assert "parse_config" in imp.state.executed
        assert "scan_project" in imp.state.executed
        assert "classify_files" in imp.state.executed
        assert "generate_import" in imp.state.executed

    @pytest.mark.asyncio(loop_scope="function")
    async def test_import_log_tap_captures_entries(self, tmp_path):
        self._create_mvc_project(tmp_path)
        log_tap = ConversionLogTap()
        imp = build_import_pipeline(log_tap=log_tap)

        await imp.run(Payload({
            "project_path": str(tmp_path),
            "pattern": "mvc",
        }))

        assert len(log_tap.entries) > 0

    @pytest.mark.asyncio(loop_scope="function")
    async def test_import_generated_cup_code_is_valid_python(self, tmp_path):
        self._create_mvc_project(tmp_path)
        imp = build_import_pipeline()

        result = await imp.run(Payload({
            "project_path": str(tmp_path),
            "pattern": "mvc",
        }))

        for f in result.get("cup_files", []):
            try:
                compile(f["content"], f["path"], "exec")
            except SyntaxError as e:
                pytest.fail(f"Invalid Python in {f['path']}: {e}")

        pipeline_code = result.get("cup_pipeline", "")
        try:
            compile(pipeline_code, "pipeline.py", "exec")
        except SyntaxError as e:
            pytest.fail(f"Invalid pipeline code: {e}")
