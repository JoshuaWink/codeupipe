"""
AssembleMetricsReport — combines all metric data into a unified report.

Takes the outputs of LatencyProbe, BundleSizeCheck, and HealthPoller
and assembles a single report with a summary grade (pass/warn/fail).

Payload contract:
    Reads:  target_url, latency, bundle, health
    Writes: metrics_report (dict) — unified report with summary
"""

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import sys

_proto_dir = Path(__file__).parent
_repo_root = _proto_dir.parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from codeupipe import Payload

__all__ = ["AssembleMetricsReport"]


# ── Thresholds for grading ───────────────────────────────────────────

_THRESHOLDS = {
    "latency_p95_warn_ms": 500,
    "latency_p95_fail_ms": 2000,
    "bundle_warn_bytes": 2_000_000,   # 2 MB
    "bundle_fail_bytes": 10_000_000,  # 10 MB
    "uptime_warn_pct": 99.0,
    "uptime_fail_pct": 95.0,
    "error_rate_warn_pct": 5.0,
    "error_rate_fail_pct": 20.0,
}


class AssembleMetricsReport:
    """Assemble all metric sections into a graded report."""

    def __init__(self, thresholds: Dict[str, Any] = None):
        self._t = dict(_THRESHOLDS)
        if thresholds:
            self._t.update(thresholds)

    def call(self, payload: Payload) -> Payload:
        target_url = payload.get("target_url") or "unknown"
        latency = payload.get("latency")
        bundle = payload.get("bundle")
        health = payload.get("health")

        checks: List[Dict[str, Any]] = []

        # ── Latency checks ───────────────────────────────────────
        if latency:
            for endpoint, stats in latency.items():
                p95 = stats.get("p95_ms", 0)
                error_count = stats.get("error_count", 0)
                total = stats.get("count", 1)
                error_rate = (error_count / total * 100) if total > 0 else 0

                if p95 > self._t["latency_p95_fail_ms"]:
                    checks.append({"name": f"latency:{endpoint}", "status": "fail", "detail": f"p95={p95}ms > {self._t['latency_p95_fail_ms']}ms"})
                elif p95 > self._t["latency_p95_warn_ms"]:
                    checks.append({"name": f"latency:{endpoint}", "status": "warn", "detail": f"p95={p95}ms > {self._t['latency_p95_warn_ms']}ms"})
                else:
                    checks.append({"name": f"latency:{endpoint}", "status": "pass", "detail": f"p95={p95}ms"})

                if error_rate > self._t["error_rate_fail_pct"]:
                    checks.append({"name": f"errors:{endpoint}", "status": "fail", "detail": f"error_rate={error_rate:.1f}%"})
                elif error_rate > self._t["error_rate_warn_pct"]:
                    checks.append({"name": f"errors:{endpoint}", "status": "warn", "detail": f"error_rate={error_rate:.1f}%"})
                else:
                    checks.append({"name": f"errors:{endpoint}", "status": "pass", "detail": f"error_rate={error_rate:.1f}%"})

        # ── Bundle checks ────────────────────────────────────────
        if bundle:
            total_bytes = bundle.get("total_bytes", 0)
            if total_bytes > self._t["bundle_fail_bytes"]:
                checks.append({"name": "bundle_size", "status": "fail", "detail": f"{total_bytes} bytes > {self._t['bundle_fail_bytes']}"})
            elif total_bytes > self._t["bundle_warn_bytes"]:
                checks.append({"name": "bundle_size", "status": "warn", "detail": f"{total_bytes} bytes > {self._t['bundle_warn_bytes']}"})
            else:
                checks.append({"name": "bundle_size", "status": "pass", "detail": f"{total_bytes} bytes"})

            if bundle.get("over_threshold"):
                checks.append({"name": "bundle_threshold", "status": "warn", "detail": "Custom threshold exceeded"})
            else:
                checks.append({"name": "bundle_threshold", "status": "pass", "detail": "Within threshold"})

        # ── Health checks ────────────────────────────────────────
        if health:
            uptime = health.get("uptime_pct", 0)
            if uptime < self._t["uptime_fail_pct"]:
                checks.append({"name": "uptime", "status": "fail", "detail": f"{uptime}% < {self._t['uptime_fail_pct']}%"})
            elif uptime < self._t["uptime_warn_pct"]:
                checks.append({"name": "uptime", "status": "warn", "detail": f"{uptime}% < {self._t['uptime_warn_pct']}%"})
            else:
                checks.append({"name": "uptime", "status": "pass", "detail": f"{uptime}%"})

        # ── Summary ──────────────────────────────────────────────
        if not checks:
            # No data at all
            grade = "fail"
            checks_passed = 0
            checks_total = 0
        else:
            statuses = [c["status"] for c in checks]
            checks_passed = statuses.count("pass")
            checks_total = len(statuses)
            if "fail" in statuses:
                grade = "fail"
            elif "warn" in statuses:
                grade = "warn"
            else:
                grade = "pass"

        report: Dict[str, Any] = {
            "target": target_url,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "summary": {
                "grade": grade,
                "checks_passed": checks_passed,
                "checks_total": checks_total,
                "checks": checks,
            },
            "latency": latency or {},
            "bundle": bundle or {},
            "health": health or {},
        }

        return payload.insert("metrics_report", report)
