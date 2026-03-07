"""
GitHistory: Retrieve git log data for component and test files.
"""

import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from codeupipe import Payload


def _git_file_info(filepath: str, repo_root: str) -> dict:
    """Get git log info for a single file.

    Returns dict with last_modified, last_author, commit_count, days_since_change.
    """
    try:
        # Get last commit date + author
        result = subprocess.run(
            ["git", "log", "-1", "--format=%aI%n%aN", "--", filepath],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=10,
        )
        lines = result.stdout.strip().split("\n")
        if result.returncode != 0 or not lines or not lines[0]:
            return {
                "last_modified": None,
                "last_author": None,
                "commit_count": 0,
                "days_since_change": None,
            }

        last_modified_iso = lines[0]
        last_author = lines[1] if len(lines) > 1 else None

        # Parse date for days_since_change
        # Python 3.9/3.10 fromisoformat doesn't accept 'Z' suffix
        if last_modified_iso.endswith("Z"):
            last_modified_iso = last_modified_iso[:-1] + "+00:00"
        last_dt = datetime.fromisoformat(last_modified_iso)
        now = datetime.now(timezone.utc)
        if last_dt.tzinfo is None:
            last_dt = last_dt.replace(tzinfo=timezone.utc)
        days = (now - last_dt).days

        # Get commit count
        count_result = subprocess.run(
            ["git", "rev-list", "--count", "HEAD", "--", filepath],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=10,
        )
        commit_count = int(count_result.stdout.strip()) if count_result.returncode == 0 else 0

        # Normalize date to YYYY-MM-DD
        last_modified = last_dt.strftime("%Y-%m-%d")

        return {
            "last_modified": last_modified,
            "last_author": last_author,
            "commit_count": commit_count,
            "days_since_change": days,
        }
    except (subprocess.TimeoutExpired, OSError, ValueError):
        return {
            "last_modified": None,
            "last_author": None,
            "commit_count": 0,
            "days_since_change": None,
        }


def _find_repo_root(directory: str) -> Optional[str]:
    """Find the git repository root for a directory."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=directory,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, OSError):
        pass
    return None


class GitHistory:
    """
    Filter (sync): Retrieve git history for each component and test file.

    Input keys:
        - components (list[dict]): from ScanComponents (each has 'file')
        - test_map (list[dict], optional): from ScanTests (each has 'test_file')
        - directory (str): component directory path

    Output keys (added):
        - git_info (dict[str, dict]): filepath → git data
            Each entry has: last_modified, last_author, commit_count, days_since_change
    """

    def call(self, payload: Payload) -> Payload:
        components = payload.get("components", [])
        test_map = payload.get("test_map", [])
        directory = payload.get("directory", ".")

        repo_root = _find_repo_root(directory)
        if repo_root is None:
            return payload.insert("git_info", {})

        # Collect unique file paths
        files = set()
        for comp in components:
            files.add(comp["file"])
        for entry in test_map:
            files.add(entry["test_file"])

        # Query git for each file
        git_info = {}
        for filepath in sorted(files):
            info = _git_file_info(filepath, repo_root)
            git_info[filepath] = info

        return payload.insert("git_info", git_info)
