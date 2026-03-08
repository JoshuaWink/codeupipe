"""Smoke tests for the `cup` CLI entry point.

These run `cup` as a subprocess — the way a user would after `pip install`.
They verify the entry point is wired correctly and basic commands work.
"""

import subprocess
import sys

import pytest


def _run_cup(*args: str) -> subprocess.CompletedProcess:
    """Run cup via `python -m codeupipe.cli` for reliable test invocation."""
    return subprocess.run(
        [sys.executable, "-m", "codeupipe.cli", *args],
        capture_output=True,
        text=True,
        timeout=30,
    )


class TestCupEntryPoint:
    """Verify the cup CLI responds to basic commands."""

    def test_no_args_shows_usage(self):
        result = _run_cup()
        # argparse prints usage to stderr on missing subcommand
        assert result.returncode != 0 or "usage" in (result.stdout + result.stderr).lower()

    def test_list_shows_component_types(self):
        result = _run_cup("list")
        assert result.returncode == 0
        assert "filter" in result.stdout.lower()

    def test_lint_on_package(self):
        result = _run_cup("lint", "codeupipe")
        # lint runs and produces output (may report known violations)
        assert "error" in result.stdout.lower() or result.returncode == 0

    def test_doc_check_runs(self):
        result = _run_cup("doc-check", ".")
        assert "ref(s) checked" in result.stdout

    def test_coverage_runs(self):
        result = _run_cup("coverage", "codeupipe")
        # coverage may return 0 or 1 depending on gaps; just verify it ran
        assert "component" in (result.stdout + result.stderr).lower() or result.returncode in (0, 1)

    def test_report_runs(self):
        result = _run_cup("report", "codeupipe")
        assert result.returncode == 0

    def test_unknown_command_fails(self):
        result = _run_cup("nonexistent")
        assert result.returncode != 0


class TestCupInstallable:
    """Verify the package metadata is correct."""

    def test_version_importable(self):
        result = subprocess.run(
            [sys.executable, "-c", "import codeupipe; print(codeupipe.__version__)"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0
        assert result.stdout.strip() == "0.10.0"

    def test_all_core_types_importable(self):
        result = subprocess.run(
            [sys.executable, "-c",
             "from codeupipe import Payload, Filter, Pipeline, Valve, Tap, State, Hook, StreamFilter, RetryFilter; print('ok')"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0
        assert result.stdout.strip() == "ok"
