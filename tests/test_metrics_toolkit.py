"""
Tests for the prototype metrics toolkit.

Validates the reusable metric collectors that measure product-level
health: HTTP latency, bundle size, health polling, and report assembly.
Each collector is a codeupipe Filter (Payload in → Payload out).

RED → GREEN: These tests are written first, before the implementation.
"""

import asyncio
import http.server
import json
import threading
import time
from pathlib import Path

import pytest

from codeupipe import Payload, Pipeline
from codeupipe.testing import run_filter, assert_payload, assert_keys


# ── Test server fixture — lightweight HTTP server for probing ────────


def _start_test_server(port: int, handler_cls):
    """Start a test HTTP server on a background thread. Returns (server, thread)."""
    server = http.server.HTTPServer(("127.0.0.1", port), handler_cls)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


class _HealthHandler(http.server.BaseHTTPRequestHandler):
    """Minimal HTTP handler: /health returns 200, / returns HTML, others 404."""

    def do_GET(self):
        if self.path == "/health":
            body = json.dumps({"status": "ok"}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path == "/":
            body = b"<html><body><h1>Test App</h1></body></html>"
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path == "/slow":
            time.sleep(0.3)
            body = b"slow response"
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass  # Suppress request logging in test output


@pytest.fixture(scope="module")
def test_server():
    """Provide a running test HTTP server for the metric probes."""
    port = 18921  # Unlikely to conflict
    server, thread = _start_test_server(port, _HealthHandler)
    yield f"http://127.0.0.1:{port}"
    server.shutdown()


# ── Static assets fixture ────────────────────────────────────────────


@pytest.fixture
def static_dir(tmp_path):
    """Create a temporary static directory with sample files."""
    html = tmp_path / "index.html"
    html.write_text("<html><body>Hello</body></html>")
    css = tmp_path / "style.css"
    css.write_text("body { color: red; }" * 100)  # ~2KB
    js = tmp_path / "app.js"
    js.write_text("console.log('hello');\n" * 500)  # ~10KB
    sub = tmp_path / "images"
    sub.mkdir()
    (sub / "logo.png").write_bytes(b"\x89PNG" + b"\x00" * 2048)  # ~2KB fake PNG
    return tmp_path


# ═══════════════════════════════════════════════════════════════════════
# LatencyProbe — measures HTTP response latency
# ═══════════════════════════════════════════════════════════════════════


class TestLatencyProbe:
    """LatencyProbe sends N requests and records latency stats."""

    def test_import(self):
        from prototypes.metrics.latency_probe import LatencyProbe
        assert LatencyProbe is not None

    def test_records_latency_stats(self, test_server):
        from prototypes.metrics.latency_probe import LatencyProbe
        probe = LatencyProbe(requests=5)
        result = run_filter(probe, {
            "target_url": test_server,
            "endpoints": ["/health"],
        })
        latency = result.get("latency")
        assert latency is not None
        assert "/health" in latency

        stats = latency["/health"]
        assert "min_ms" in stats
        assert "max_ms" in stats
        assert "avg_ms" in stats
        assert "p95_ms" in stats
        assert "p99_ms" in stats
        assert "count" in stats
        assert stats["count"] == 5
        assert stats["min_ms"] > 0
        assert stats["max_ms"] >= stats["min_ms"]
        assert stats["avg_ms"] >= stats["min_ms"]

    def test_multiple_endpoints(self, test_server):
        from prototypes.metrics.latency_probe import LatencyProbe
        probe = LatencyProbe(requests=3)
        result = run_filter(probe, {
            "target_url": test_server,
            "endpoints": ["/health", "/"],
        })
        latency = result.get("latency")
        assert "/health" in latency
        assert "/" in latency

    def test_records_errors_for_bad_endpoints(self, test_server):
        from prototypes.metrics.latency_probe import LatencyProbe
        probe = LatencyProbe(requests=2)
        result = run_filter(probe, {
            "target_url": test_server,
            "endpoints": ["/nonexistent"],
        })
        latency = result.get("latency")
        stats = latency["/nonexistent"]
        assert stats["error_count"] > 0

    def test_slow_endpoint_higher_latency(self, test_server):
        from prototypes.metrics.latency_probe import LatencyProbe
        probe = LatencyProbe(requests=2)
        result = run_filter(probe, {
            "target_url": test_server,
            "endpoints": ["/health", "/slow"],
        })
        latency = result.get("latency")
        assert latency["/slow"]["avg_ms"] > latency["/health"]["avg_ms"]


# ═══════════════════════════════════════════════════════════════════════
# BundleSizeCheck — measures static asset sizes
# ═══════════════════════════════════════════════════════════════════════


class TestBundleSizeCheck:
    """BundleSizeCheck scans a static directory and reports sizes."""

    def test_import(self):
        from prototypes.metrics.bundle_size_check import BundleSizeCheck
        assert BundleSizeCheck is not None

    def test_reports_total_size(self, static_dir):
        from prototypes.metrics.bundle_size_check import BundleSizeCheck
        check = BundleSizeCheck()
        result = run_filter(check, {"static_dir": str(static_dir)})
        bundle = result.get("bundle")
        assert bundle is not None
        assert "total_bytes" in bundle
        assert bundle["total_bytes"] > 0

    def test_reports_per_extension_breakdown(self, static_dir):
        from prototypes.metrics.bundle_size_check import BundleSizeCheck
        check = BundleSizeCheck()
        result = run_filter(check, {"static_dir": str(static_dir)})
        bundle = result.get("bundle")
        assert "by_extension" in bundle
        assert ".html" in bundle["by_extension"]
        assert ".css" in bundle["by_extension"]
        assert ".js" in bundle["by_extension"]
        assert ".png" in bundle["by_extension"]

    def test_reports_file_count(self, static_dir):
        from prototypes.metrics.bundle_size_check import BundleSizeCheck
        check = BundleSizeCheck()
        result = run_filter(check, {"static_dir": str(static_dir)})
        bundle = result.get("bundle")
        assert bundle["file_count"] == 4

    def test_reports_largest_files(self, static_dir):
        from prototypes.metrics.bundle_size_check import BundleSizeCheck
        check = BundleSizeCheck()
        result = run_filter(check, {"static_dir": str(static_dir)})
        bundle = result.get("bundle")
        assert "largest_files" in bundle
        assert len(bundle["largest_files"]) > 0
        # Each entry is (filename, bytes)
        first = bundle["largest_files"][0]
        assert len(first) == 2
        assert isinstance(first[1], int)

    def test_handles_empty_dir(self, tmp_path):
        from prototypes.metrics.bundle_size_check import BundleSizeCheck
        check = BundleSizeCheck()
        result = run_filter(check, {"static_dir": str(tmp_path)})
        bundle = result.get("bundle")
        assert bundle["total_bytes"] == 0
        assert bundle["file_count"] == 0

    def test_warns_when_over_threshold(self, static_dir):
        from prototypes.metrics.bundle_size_check import BundleSizeCheck
        # Set threshold absurdly low so it triggers
        check = BundleSizeCheck(warn_bytes=100)
        result = run_filter(check, {"static_dir": str(static_dir)})
        bundle = result.get("bundle")
        assert bundle["over_threshold"] is True


# ═══════════════════════════════════════════════════════════════════════
# HealthPoller — polls health endpoint over a duration
# ═══════════════════════════════════════════════════════════════════════


class TestHealthPoller:
    """HealthPoller checks uptime by polling /health N times over M seconds."""

    def test_import(self):
        from prototypes.metrics.health_poller import HealthPoller
        assert HealthPoller is not None

    def test_reports_uptime_percentage(self, test_server):
        from prototypes.metrics.health_poller import HealthPoller
        poller = HealthPoller(polls=5, interval_s=0.1)
        result = run_filter(poller, {
            "target_url": test_server,
            "health_path": "/health",
        })
        health = result.get("health")
        assert health is not None
        assert health["uptime_pct"] == 100.0
        assert health["total_polls"] == 5
        assert health["successful_polls"] == 5
        assert health["failed_polls"] == 0

    def test_reports_failures_for_bad_endpoint(self, test_server):
        from prototypes.metrics.health_poller import HealthPoller
        poller = HealthPoller(polls=3, interval_s=0.05)
        result = run_filter(poller, {
            "target_url": test_server,
            "health_path": "/nonexistent",
        })
        health = result.get("health")
        # 404 counts as a failure
        assert health["failed_polls"] == 3
        assert health["uptime_pct"] == 0.0

    def test_reports_avg_response_time(self, test_server):
        from prototypes.metrics.health_poller import HealthPoller
        poller = HealthPoller(polls=3, interval_s=0.05)
        result = run_filter(poller, {
            "target_url": test_server,
            "health_path": "/health",
        })
        health = result.get("health")
        assert "avg_response_ms" in health
        assert health["avg_response_ms"] > 0


# ═══════════════════════════════════════════════════════════════════════
# AssembleMetricsReport — collects all metrics into a unified report
# ═══════════════════════════════════════════════════════════════════════


class TestAssembleMetricsReport:
    """AssembleMetricsReport combines all metric data into a final report."""

    def test_import(self):
        from prototypes.metrics.assemble_metrics_report import AssembleMetricsReport
        assert AssembleMetricsReport is not None

    def test_assembles_report_from_all_metrics(self):
        from prototypes.metrics.assemble_metrics_report import AssembleMetricsReport
        assembler = AssembleMetricsReport()
        result = run_filter(assembler, {
            "target_url": "http://localhost:8421",
            "latency": {
                "/health": {"min_ms": 1, "max_ms": 5, "avg_ms": 3, "p95_ms": 4, "p99_ms": 5, "count": 10, "error_count": 0},
            },
            "bundle": {
                "total_bytes": 14000,
                "file_count": 4,
                "by_extension": {".html": 44, ".css": 2000, ".js": 10000, ".png": 2052},
                "largest_files": [("app.js", 10000)],
                "over_threshold": False,
            },
            "health": {
                "uptime_pct": 100.0,
                "total_polls": 10,
                "successful_polls": 10,
                "failed_polls": 0,
                "avg_response_ms": 2.5,
            },
        })
        report = result.get("metrics_report")
        assert report is not None
        assert "summary" in report
        assert "latency" in report
        assert "bundle" in report
        assert "health" in report
        assert "timestamp" in report
        assert report["target"] == "http://localhost:8421"

    def test_summary_has_pass_fail(self):
        from prototypes.metrics.assemble_metrics_report import AssembleMetricsReport
        assembler = AssembleMetricsReport()
        result = run_filter(assembler, {
            "target_url": "http://localhost:8421",
            "latency": {"/health": {"avg_ms": 3, "p95_ms": 4, "p99_ms": 5, "min_ms": 1, "max_ms": 5, "count": 5, "error_count": 0}},
            "bundle": {"total_bytes": 5000, "file_count": 2, "by_extension": {}, "largest_files": [], "over_threshold": False},
            "health": {"uptime_pct": 100.0, "total_polls": 5, "successful_polls": 5, "failed_polls": 0, "avg_response_ms": 2},
        })
        report = result.get("metrics_report")
        summary = report["summary"]
        assert "grade" in summary  # "pass", "warn", or "fail"
        assert "checks_passed" in summary
        assert "checks_total" in summary

    def test_report_serializes_to_json(self):
        from prototypes.metrics.assemble_metrics_report import AssembleMetricsReport
        assembler = AssembleMetricsReport()
        result = run_filter(assembler, {
            "target_url": "http://localhost:8421",
            "latency": {"/health": {"avg_ms": 3, "p95_ms": 4, "p99_ms": 5, "min_ms": 1, "max_ms": 5, "count": 5, "error_count": 0}},
            "bundle": {"total_bytes": 5000, "file_count": 2, "by_extension": {}, "largest_files": [], "over_threshold": False},
            "health": {"uptime_pct": 100.0, "total_polls": 5, "successful_polls": 5, "failed_polls": 0, "avg_response_ms": 2},
        })
        report = result.get("metrics_report")
        # Must be JSON-serializable
        dumped = json.dumps(report, default=str)
        assert len(dumped) > 0

    def test_handles_missing_sections_gracefully(self):
        from prototypes.metrics.assemble_metrics_report import AssembleMetricsReport
        assembler = AssembleMetricsReport()
        result = run_filter(assembler, {
            "target_url": "http://localhost:8421",
        })
        report = result.get("metrics_report")
        assert report is not None
        assert report["summary"]["grade"] == "fail"


# ═══════════════════════════════════════════════════════════════════════
# Full Pipeline Integration
# ═══════════════════════════════════════════════════════════════════════


class TestMetricsPipeline:
    """Integration test: full metrics pipeline end-to-end."""

    def test_import_pipeline_builder(self):
        from prototypes.metrics.pipeline import build_metrics_pipeline
        assert build_metrics_pipeline is not None

    def test_pipeline_runs_all_collectors(self, test_server, static_dir):
        from prototypes.metrics.pipeline import build_metrics_pipeline
        pipeline = build_metrics_pipeline(
            requests=3,
            polls=3,
            poll_interval=0.05,
        )
        payload = Payload({
            "target_url": test_server,
            "endpoints": ["/health"],
            "health_path": "/health",
            "static_dir": str(static_dir),
        })
        result = asyncio.run(pipeline.run(payload))

        # All metric sections should be populated
        assert result.get("latency") is not None
        assert result.get("bundle") is not None
        assert result.get("health") is not None
        assert result.get("metrics_report") is not None

        report = result.get("metrics_report")
        assert report["summary"]["grade"] in ("pass", "warn", "fail")

    def test_pipeline_state_tracks_all_filters(self, test_server, static_dir):
        from prototypes.metrics.pipeline import build_metrics_pipeline
        pipeline = build_metrics_pipeline(
            requests=2,
            polls=2,
            poll_interval=0.05,
        )
        payload = Payload({
            "target_url": test_server,
            "endpoints": ["/health"],
            "health_path": "/health",
            "static_dir": str(static_dir),
        })
        asyncio.run(pipeline.run(payload))

        executed = pipeline.state.executed
        assert "latency_probe" in executed
        assert "bundle_size_check" in executed
        assert "health_poller" in executed
        assert "assemble_report" in executed
