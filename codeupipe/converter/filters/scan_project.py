"""
ScanProjectFilter: Scans a standard Python project directory for source files.
"""

from pathlib import Path
from typing import Any, Dict, List
from codeupipe import Payload


class ScanProjectFilter:
    """
    Filter: Scan a project directory and collect Python source files.

    Input payload keys:
        - project_path (str): Root directory to scan
        - config (dict): Config with output dirs (used to determine role by location)

    Output payload adds:
        - source_files (list[dict]): {"path": str, "relative": str, "content": str, "dir": str}
    """

    def call(self, payload):
        project_path = payload.get("project_path")
        if not project_path:
            raise ValueError("Payload must contain 'project_path' key")

        root = Path(project_path)
        if not root.is_dir():
            raise ValueError(f"Not a directory: {project_path}")

        source_files: List[Dict[str, Any]] = []

        for py_file in sorted(root.rglob("*.py")):
            # Skip __pycache__, __init__.py, and hidden dirs
            parts = py_file.relative_to(root).parts
            if any(p.startswith(".") or p == "__pycache__" for p in parts):
                continue
            if py_file.name == "__init__.py":
                continue

            relative = str(py_file.relative_to(root))
            parent_dir = str(py_file.parent.relative_to(root)) if py_file.parent != root else ""

            source_files.append({
                "path": str(py_file),
                "relative": relative,
                "content": py_file.read_text(encoding="utf-8"),
                "dir": parent_dir,
                "name": py_file.stem,
            })

        return payload.insert("source_files", source_files)
