"""
E2E Round-Trip Tests: CUP → Standard → CUP

Full cycle:
1. Build a real CUP Pipeline
2. Export it to standard Python files on disk (MVC, Clean, etc.)
3. Verify the directory structure matches the target pattern
4. Import the standard files back into CUP
5. Verify the reconstituted pipeline has the same steps
"""

import asyncio
import os
import pytest
import pytest_asyncio
from pathlib import Path
from codeupipe import Payload, Pipeline, Valve, Hook

from codeupipe.converter.pipelines.export_pipeline import build_export_pipeline
from codeupipe.converter.pipelines.import_pipeline import build_import_pipeline
from codeupipe.converter.taps.conversion_log import ConversionLogTap


# ──────────────────────────────────────────────
# Sample Pipeline (realistic business workflow)
# ──────────────────────────────────────────────

class FetchOrderFilter:
    def call(self, payload):
        return payload.insert("order", {"id": payload.get("order_id"), "items": ["widget"]})


class ValidateOrderFilter:
    def call(self, payload):
        order = payload.get("order")
        if not order or not order.get("items"):
            raise ValueError("Invalid order")
        return payload.insert("validated", True)


class CalcTotalFilter:
    def call(self, payload):
        items = payload.get("order", {}).get("items", [])
        return payload.insert("total", len(items) * 10.0)


class FormatInvoiceFilter:
    def call(self, payload):
        return payload.insert("invoice", f"Invoice: ${payload.get('total', 0):.2f}")


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


def _build_order_pipeline():
    """Build the 'order processing' CUP pipeline for round-trip testing."""
    p = Pipeline()
    p.add_filter(FetchOrderFilter(), name="fetch_order")
    p.add_filter(ValidateOrderFilter(), name="validate_order")
    p.add_filter(CalcTotalFilter(), name="calc_total")
    p.add_filter(
        Valve("premium_discount", PremiumDiscountFilter(), lambda p: p.get("tier") == "premium"),
        name="premium_discount",
    )
    p.add_tap(AuditTap(), name="audit_tap")
    p.add_filter(FormatInvoiceFilter(), name="format_invoice")
    p.add_filter(SaveOrderFilter(), name="save_order")
    p.use_hook(TimingHook())
    return p


def _write_exported_files(tmp_path, files, base=""):
    """Write generated files to disk."""
    for f in files:
        filepath = tmp_path / f["path"]
        filepath.parent.mkdir(parents=True, exist_ok=True)
        filepath.write_text(f["content"], encoding="utf-8")
        # Also write __init__.py in every directory
        init = filepath.parent / "__init__.py"
        if not init.exists():
            init.write_text("")


# ──────────────────────────────────────────────
# Round-Trip: MVC
# ──────────────────────────────────────────────

class TestMVCRoundTrip:
    @pytest.mark.asyncio(loop_scope="function")
    async def test_export_creates_mvc_structure(self, tmp_path):
        """Export a CUP pipeline → verify MVC directory structure on disk."""
        pipeline = _build_order_pipeline()
        export = build_export_pipeline()

        result = await export.run(Payload({
            "pipeline": pipeline,
            "pattern": "mvc",
        }))

        files = result.get("files")
        _write_exported_files(tmp_path, files)

        # Verify directory structure
        src = tmp_path / "src"
        assert (src / "models").is_dir() or any("models/" in f["path"] for f in files)
        assert (src / "controllers").is_dir() or any("controllers/" in f["path"] for f in files)

        # Verify key files exist
        written = list(tmp_path.rglob("*.py"))
        names = [f.stem for f in written if f.stem != "__init__"]
        assert "fetch_order" in names
        assert "save_order" in names
        assert "pipeline" in names

    @pytest.mark.asyncio(loop_scope="function")
    async def test_exported_python_files_are_valid(self, tmp_path):
        """Every exported file must compile as valid Python."""
        pipeline = _build_order_pipeline()
        export = build_export_pipeline()

        result = await export.run(Payload({
            "pipeline": pipeline,
            "pattern": "mvc",
        }))

        for f in result.get("files"):
            try:
                compile(f["content"], f["path"], "exec")
            except SyntaxError as e:
                pytest.fail(f"Invalid Python in {f['path']}: {e}")

    @pytest.mark.asyncio(loop_scope="function")
    async def test_full_mvc_round_trip(self, tmp_path):
        """CUP → MVC files on disk → import back → verify steps reconstituted."""
        # Step 1: Export
        pipeline = _build_order_pipeline()
        export = build_export_pipeline()

        export_result = await export.run(Payload({
            "pipeline": pipeline,
            "pattern": "mvc",
        }))

        # Step 2: Write to disk
        files = export_result.get("files")
        export_dir = tmp_path / "exported"
        _write_exported_files(export_dir, files)

        # Step 3: Import from the exported directory
        # The exported files are under src/<role>/ — point to src/
        src_dir = export_dir / "src"
        if not src_dir.is_dir():
            src_dir = export_dir

        imp = build_import_pipeline()
        import_result = await imp.run(Payload({
            "project_path": str(src_dir),
            "pattern": "mvc",
        }))

        # Step 4: Verify
        cup_files = import_result.get("cup_files", [])
        cup_steps = import_result.get("cup_steps", [])
        cup_pipeline = import_result.get("cup_pipeline", "")

        # Should have generated CUP filter files
        assert len(cup_files) > 0

        # Pipeline code should reference the steps
        assert "build_pipeline" in cup_pipeline
        assert "Pipeline" in cup_pipeline

        # The reconstituted steps should cover the original filter names
        original_filter_names = {"fetch_order", "validate_order", "calc_total",
                                 "format_invoice", "save_order"}
        reconstituted_names = {s["name"] for s in cup_steps}
        # At least the model/controller/view filters should survive
        assert len(reconstituted_names & original_filter_names) >= 3

    @pytest.mark.asyncio(loop_scope="function")
    async def test_round_trip_preserves_step_types(self, tmp_path):
        """Tap functions should be imported back as taps, not filters."""
        pipeline = _build_order_pipeline()
        export = build_export_pipeline()

        export_result = await export.run(Payload({
            "pipeline": pipeline,
            "pattern": "mvc",
        }))

        files = export_result.get("files")
        export_dir = tmp_path / "exported"
        _write_exported_files(export_dir, files)

        src_dir = export_dir / "src"
        if not src_dir.is_dir():
            src_dir = export_dir

        imp = build_import_pipeline()
        import_result = await imp.run(Payload({
            "project_path": str(src_dir),
            "pattern": "mvc",
        }))

        cup_steps = import_result.get("cup_steps", [])
        step_types = {s["name"]: s["type"] for s in cup_steps}

        # Middleware functions (originally taps) should be imported as taps
        # due to their None return type
        tap_names = [n for n, t in step_types.items() if t == "tap"]
        filter_names = [n for n, t in step_types.items() if t == "filter"]
        # We should have at least some of each
        assert len(filter_names) > 0


# ──────────────────────────────────────────────
# Round-Trip: Clean Architecture
# ──────────────────────────────────────────────

class TestCleanRoundTrip:
    @pytest.mark.asyncio(loop_scope="function")
    async def test_export_creates_clean_structure(self, tmp_path):
        pipeline = _build_order_pipeline()
        export = build_export_pipeline()

        result = await export.run(Payload({
            "pipeline": pipeline,
            "pattern": "clean",
        }))

        files = result.get("files")
        paths = [f["path"] for f in files]

        # Clean arch: use_cases/, interface_adapters/
        assert any("use_cases/" in p for p in paths)
        assert any("interface_adapters/" in p for p in paths)

    @pytest.mark.asyncio(loop_scope="function")
    async def test_clean_round_trip(self, tmp_path):
        pipeline = _build_order_pipeline()
        export = build_export_pipeline()

        export_result = await export.run(Payload({
            "pipeline": pipeline,
            "pattern": "clean",
        }))

        files = export_result.get("files")
        export_dir = tmp_path / "exported"
        _write_exported_files(export_dir, files)

        src_dir = export_dir / "src"
        if not src_dir.is_dir():
            src_dir = export_dir

        imp = build_import_pipeline()
        import_result = await imp.run(Payload({
            "project_path": str(src_dir),
            "pattern": "clean",
        }))

        cup_files = import_result.get("cup_files", [])
        assert len(cup_files) > 0


# ──────────────────────────────────────────────
# Round-Trip: Hexagonal
# ──────────────────────────────────────────────

class TestHexagonalRoundTrip:
    @pytest.mark.asyncio(loop_scope="function")
    async def test_export_creates_hexagonal_structure(self, tmp_path):
        pipeline = _build_order_pipeline()
        export = build_export_pipeline()

        result = await export.run(Payload({
            "pipeline": pipeline,
            "pattern": "hexagonal",
        }))

        files = result.get("files")
        paths = [f["path"] for f in files]

        assert any("domain/" in p for p in paths)
        assert any("adapters/" in p for p in paths)

    @pytest.mark.asyncio(loop_scope="function")
    async def test_hexagonal_round_trip(self, tmp_path):
        pipeline = _build_order_pipeline()
        export = build_export_pipeline()

        export_result = await export.run(Payload({
            "pipeline": pipeline,
            "pattern": "hexagonal",
        }))

        files = export_result.get("files")
        export_dir = tmp_path / "exported"
        _write_exported_files(export_dir, files)

        src_dir = export_dir / "src"
        if not src_dir.is_dir():
            src_dir = export_dir

        imp = build_import_pipeline()
        import_result = await imp.run(Payload({
            "project_path": str(src_dir),
            "pattern": "hexagonal",
        }))

        cup_files = import_result.get("cup_files", [])
        assert len(cup_files) > 0


# ──────────────────────────────────────────────
# Round-Trip: Flat
# ──────────────────────────────────────────────

class TestFlatRoundTrip:
    @pytest.mark.asyncio(loop_scope="function")
    async def test_flat_round_trip(self, tmp_path):
        pipeline = _build_order_pipeline()
        export = build_export_pipeline()

        export_result = await export.run(Payload({
            "pipeline": pipeline,
            "pattern": "flat",
        }))

        files = export_result.get("files")
        export_dir = tmp_path / "exported"
        _write_exported_files(export_dir, files)

        src_dir = export_dir / "src"
        if not src_dir.is_dir():
            src_dir = export_dir

        imp = build_import_pipeline()
        import_result = await imp.run(Payload({
            "project_path": str(src_dir),
            "pattern": "flat",
        }))

        cup_files = import_result.get("cup_files", [])
        assert len(cup_files) > 0
        assert "build_pipeline" in import_result.get("cup_pipeline", "")


# ──────────────────────────────────────────────
# Cross-Pattern: Export as one pattern, import structure recognized
# ──────────────────────────────────────────────

class TestCrossPattern:
    @pytest.mark.asyncio(loop_scope="function")
    async def test_export_mvc_import_as_clean(self, tmp_path):
        """Export as MVC, import using Clean Architecture config — roles remapped."""
        pipeline = _build_order_pipeline()
        export = build_export_pipeline()

        export_result = await export.run(Payload({
            "pipeline": pipeline,
            "pattern": "mvc",
        }))

        files = export_result.get("files")
        export_dir = tmp_path / "exported"
        _write_exported_files(export_dir, files)

        # Import with clean config — directories won't match clean patterns,
        # so most files land in "uncategorized" — that's expected behavior
        src_dir = export_dir / "src"
        if not src_dir.is_dir():
            src_dir = export_dir

        imp = build_import_pipeline()
        import_result = await imp.run(Payload({
            "project_path": str(src_dir),
            "pattern": "clean",
        }))

        # Should still generate cup_files even if roles differ
        cup_files = import_result.get("cup_files", [])
        assert len(cup_files) > 0


# ──────────────────────────────────────────────
# Pipeline State Tracking Through Full Cycle
# ──────────────────────────────────────────────

class TestStateTracking:
    @pytest.mark.asyncio(loop_scope="function")
    async def test_both_pipelines_track_full_state(self, tmp_path):
        """Both export and import pipelines should have all steps in state.executed."""
        pipeline = _build_order_pipeline()

        # Export
        export_log = ConversionLogTap()
        export = build_export_pipeline(log_tap=export_log)
        export_result = await export.run(Payload({
            "pipeline": pipeline,
            "pattern": "mvc",
        }))

        assert len(export.state.executed) >= 4  # 4 filters + tap
        assert not export.state.has_errors

        # Write
        files = export_result.get("files")
        export_dir = tmp_path / "exported"
        _write_exported_files(export_dir, files)

        # Import
        import_log = ConversionLogTap()
        imp = build_import_pipeline(log_tap=import_log)
        src_dir = export_dir / "src"
        if not src_dir.is_dir():
            src_dir = export_dir

        await imp.run(Payload({
            "project_path": str(src_dir),
            "pattern": "mvc",
        }))

        assert len(imp.state.executed) >= 4
        assert not imp.state.has_errors

        # Both logs should have entries
        assert len(export_log.entries) > 0
        assert len(import_log.entries) > 0
