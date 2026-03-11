"""
HealthPoller — polls a health endpoint repeatedly to measure uptime.

Sends N polls at a configurable interval and reports uptime percentage,
success/failure counts, and average response time.

Payload contract:
    Reads:  target_url (str), health_path (str)
    Writes: health (dict) — uptime metrics
"""

import time
import urllib.request
import urllib.error
from pathlib import Path
from typing import Any, Dict, List

import sys

_proto_dir = Path(__file__).parent
_repo_root = _proto_dir.parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from codeupipe import Payload

__all__ = ["HealthPoller"]


class HealthPoller:
    """Poll a health endpoint and report uptime metrics."""

    def __init__(self, polls: int = 10, interval_s: float = 1.0, timeout_s: float = 5.0):
        self._polls = polls
        self._interval = interval_s
        self._timeout = timeout_s

    def call(self, payload: Payload) -> Payload:
        target_url = payload.get("target_url")
        health_path = payload.get("health_path") or "/health"
        url = f"{target_url.rstrip('/')}{health_path}"

        successful = 0
        failed = 0
        response_times: List[float] = []

        for i in range(self._polls):
            if i > 0:
                time.sleep(self._interval)

            start = time.perf_counter()
            try:
                req = urllib.request.Request(url, method="GET")
                with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                    resp.read()
                    elapsed_ms = (time.perf_counter() - start) * 1000
                    if 200 <= resp.status < 400:
                        successful += 1
                        response_times.append(elapsed_ms)
                    else:
                        failed += 1
            except (urllib.error.HTTPError, urllib.error.URLError, OSError):
                failed += 1

        total = successful + failed
        uptime_pct = (successful / total * 100) if total > 0 else 0.0
        avg_ms = sum(response_times) / len(response_times) if response_times else 0.0

        health: Dict[str, Any] = {
            "uptime_pct": round(uptime_pct, 1),
            "total_polls": total,
            "successful_polls": successful,
            "failed_polls": failed,
            "avg_response_ms": round(avg_ms, 2),
        }

        return payload.insert("health", health)
