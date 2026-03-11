"""
LatencyProbe — measures HTTP response latency for a set of endpoints.

Sends N requests to each endpoint and records min/max/avg/p95/p99
latency in milliseconds. Tracks error counts for non-2xx responses.

Payload contract:
    Reads:  target_url (str), endpoints (list[str])
    Writes: latency (dict) — per-endpoint stats
"""

import statistics
import time
import urllib.request
import urllib.error
from typing import Any, Dict, List

import sys
from pathlib import Path

_proto_dir = Path(__file__).parent
_repo_root = _proto_dir.parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from codeupipe import Payload

__all__ = ["LatencyProbe"]


class LatencyProbe:
    """Send N HTTP requests per endpoint and record latency statistics."""

    def __init__(self, requests: int = 10, timeout_s: float = 5.0):
        self._requests = requests
        self._timeout = timeout_s

    def call(self, payload: Payload) -> Payload:
        target_url = payload.get("target_url")
        endpoints = payload.get("endpoints") or ["/"]

        results: Dict[str, Dict[str, Any]] = {}
        for endpoint in endpoints:
            url = f"{target_url.rstrip('/')}{endpoint}"
            timings: List[float] = []
            error_count = 0

            for _ in range(self._requests):
                start = time.perf_counter()
                try:
                    req = urllib.request.Request(url, method="GET")
                    with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                        resp.read()
                        elapsed_ms = (time.perf_counter() - start) * 1000
                        if 200 <= resp.status < 400:
                            timings.append(elapsed_ms)
                        else:
                            error_count += 1
                            timings.append(elapsed_ms)
                except (urllib.error.HTTPError, urllib.error.URLError, OSError):
                    elapsed_ms = (time.perf_counter() - start) * 1000
                    error_count += 1
                    timings.append(elapsed_ms)

            if timings:
                sorted_t = sorted(timings)
                p95_idx = max(0, int(len(sorted_t) * 0.95) - 1)
                p99_idx = max(0, int(len(sorted_t) * 0.99) - 1)
                results[endpoint] = {
                    "min_ms": round(min(sorted_t), 2),
                    "max_ms": round(max(sorted_t), 2),
                    "avg_ms": round(statistics.mean(sorted_t), 2),
                    "p95_ms": round(sorted_t[p95_idx], 2),
                    "p99_ms": round(sorted_t[p99_idx], 2),
                    "count": len(timings),
                    "error_count": error_count,
                }
            else:
                results[endpoint] = {
                    "min_ms": 0, "max_ms": 0, "avg_ms": 0,
                    "p95_ms": 0, "p99_ms": 0,
                    "count": 0, "error_count": self._requests,
                }

        return payload.insert("latency", results)
