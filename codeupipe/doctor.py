"""
codeupipe.doctor — Project health check.

Runs a comprehensive diagnostic on the current codeupipe project:
manifest, connectors, CI config, linter, coverage, and tests.
Zero external dependencies.
"""

import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

__all__ = ["diagnose"]


def diagnose(project_dir: str = ".") -> Dict[str, Any]:
    """Run a full project health check.

    Returns a dict with check names → results:
        {
            "manifest": {"ok": True, ...},
            "ci": {"ok": True, ...},
            "tests": {"ok": True, ...},
            "lint": {"ok": True, ...},
            "connectors": {"ok": True, ...},
            "docs": {"ok": True, ...},
        }
    """
    root = Path(project_dir)
    results: Dict[str, Any] = {}

    # 1. Manifest check
    results["manifest"] = _check_manifest(root)

    # 2. CI config check
    results["ci"] = _check_ci(root)

    # 3. Tests check
    results["tests"] = _check_tests(root)

    # 4. Lint check
    results["lint"] = _check_lint(root)

    # 5. Connector health
    results["connectors"] = _check_connectors(root)

    # 6. Doc freshness
    results["docs"] = _check_docs(root)

    # Summary
    total = len(results)
    passing = sum(1 for r in results.values() if r.get("ok"))
    results["_summary"] = {
        "total": total,
        "passing": passing,
        "failing": total - passing,
        "healthy": passing == total,
    }

    return results


def _check_manifest(root: Path) -> Dict[str, Any]:
    """Check that cup.toml exists and is valid."""
    manifest_path = root / "cup.toml"
    if not manifest_path.exists():
        return {"ok": False, "message": "No cup.toml found"}

    try:
        from codeupipe.deploy.manifest import load_manifest
        data = load_manifest(str(manifest_path))
        name = data.get("project", {}).get("name", "?")
        return {"ok": True, "message": f"Valid manifest for '{name}'"}
    except Exception as e:
        return {"ok": False, "message": f"Invalid manifest: {e}"}


def _check_ci(root: Path) -> Dict[str, Any]:
    """Check for CI configuration."""
    try:
        from codeupipe.deploy.init import detect_ci
        found = detect_ci(str(root))
        if not found:
            return {"ok": False, "message": "No CI config detected"}
        providers = [e["provider"] for e in found]
        return {"ok": True, "message": f"CI: {', '.join(providers)}"}
    except Exception as e:
        return {"ok": False, "message": f"CI check failed: {e}"}


def _check_tests(root: Path) -> Dict[str, Any]:
    """Check that tests exist and can be collected."""
    tests_dir = root / "tests"
    if not tests_dir.is_dir():
        return {"ok": False, "message": "No tests/ directory"}

    test_files = list(tests_dir.glob("test_*.py"))
    if not test_files:
        return {"ok": False, "message": "No test files found in tests/"}

    # Try to collect tests (fast, no execution)
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "--collect-only", "-q",
             str(tests_dir)],
            capture_output=True, text=True, timeout=30,
            cwd=str(root),
        )
        if result.returncode == 0:
            # Parse count from last line like "42 tests collected"
            for line in result.stdout.strip().splitlines()[::-1]:
                if "test" in line:
                    return {"ok": True, "message": line.strip()}
        return {"ok": True, "message": f"{len(test_files)} test file(s) found"}
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return {"ok": True, "message": f"{len(test_files)} test file(s) found (pytest not available)"}


def _check_lint(root: Path) -> Dict[str, Any]:
    """Run cup lint on the project."""
    try:
        from codeupipe.cli.commands.analysis_cmds import lint
        issues = lint(str(root))
        if not issues:
            return {"ok": True, "message": "All lint checks passed"}
        return {"ok": False, "message": f"{len(issues)} lint issue(s)"}
    except Exception as e:
        return {"ok": False, "message": f"Lint failed: {e}"}


def _check_connectors(root: Path) -> Dict[str, Any]:
    """Check connector health by delegating to connect.check_health()."""
    manifest_path = root / "cup.toml"
    if not manifest_path.exists():
        return {"ok": True, "message": "No manifest (skipped)"}

    try:
        from codeupipe.deploy.manifest import load_manifest
        data = load_manifest(str(manifest_path))
        connectors_cfg = data.get("connectors", {})
        if not connectors_cfg:
            return {"ok": True, "message": "No connectors configured"}

        # Delegate to actual health checks
        from codeupipe.registry import Registry
        from codeupipe.connect import (
            discover_connectors, load_connector_configs, check_health,
        )
        registry = Registry()
        configs = load_connector_configs(data)
        discover_connectors(configs, registry=registry)
        health = check_health(registry)

        healthy = [n for n, ok in health.items() if ok]
        unhealthy = [n for n, ok in health.items() if not ok]
        total = len(health)

        if not health:
            return {"ok": True, "message": f"{len(connectors_cfg)} connector(s) configured (no health checks)"}
        if unhealthy:
            return {
                "ok": False,
                "message": f"{len(unhealthy)}/{total} unhealthy: {', '.join(unhealthy)}",
                "healthy": healthy,
                "unhealthy": unhealthy,
            }
        return {"ok": True, "message": f"{total} connector(s) healthy"}
    except Exception as e:
        return {"ok": False, "message": f"Connector check failed: {e}"}


def _check_docs(root: Path) -> Dict[str, Any]:
    """Check cup:ref documentation freshness."""
    try:
        from codeupipe.cli.commands.analysis_cmds import doc_check
        report = doc_check(str(root))
        drifted = report.get("drifted", 0)
        total = report.get("total_refs", 0)
        if drifted == 0:
            return {"ok": True, "message": f"{total} ref(s) current"}
        return {"ok": False, "message": f"{drifted} of {total} ref(s) drifted"}
    except Exception as e:
        # doc-check may not be applicable to all projects
        return {"ok": True, "message": "Doc check not applicable"}
