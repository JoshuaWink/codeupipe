"""
BundleSizeCheck — measures static asset sizes in a directory.

Scans a static directory recursively and reports total size,
per-extension breakdown, file count, largest files, and
whether the bundle exceeds a configurable threshold.

Payload contract:
    Reads:  static_dir (str) — path to static assets directory
    Writes: bundle (dict) — size metrics
"""

import os
from pathlib import Path
from typing import Any, Dict, List, Tuple

import sys

_proto_dir = Path(__file__).parent
_repo_root = _proto_dir.parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from codeupipe import Payload

__all__ = ["BundleSizeCheck"]


class BundleSizeCheck:
    """Scan a static directory and report size metrics."""

    def __init__(self, warn_bytes: int = 5_000_000, top_n: int = 10):
        self._warn_bytes = warn_bytes
        self._top_n = top_n

    def call(self, payload: Payload) -> Payload:
        static_dir = Path(payload.get("static_dir"))

        total_bytes = 0
        file_count = 0
        by_extension: Dict[str, int] = {}
        file_sizes: List[Tuple[str, int]] = []

        if static_dir.exists():
            for path in static_dir.rglob("*"):
                if path.is_file():
                    size = path.stat().st_size
                    total_bytes += size
                    file_count += 1
                    ext = path.suffix.lower() or "(none)"
                    by_extension[ext] = by_extension.get(ext, 0) + size
                    rel = str(path.relative_to(static_dir))
                    file_sizes.append((rel, size))

        # Sort largest first
        file_sizes.sort(key=lambda x: x[1], reverse=True)
        largest = file_sizes[: self._top_n]

        bundle: Dict[str, Any] = {
            "total_bytes": total_bytes,
            "file_count": file_count,
            "by_extension": by_extension,
            "largest_files": largest,
            "over_threshold": total_bytes > self._warn_bytes,
        }

        return payload.insert("bundle", bundle)
