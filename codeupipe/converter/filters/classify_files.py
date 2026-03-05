"""
ClassifyFilesFilter: Maps scanned project files to CUP roles by directory location.
"""

from typing import Any, Dict, List
from codeupipe import Payload


class ClassifyFilesFilter:
    """
    Filter: Classify scanned files into roles based on their directory.

    Input payload keys:
        - source_files (list[dict]): Files from ScanProjectFilter
        - config (dict): Config with output dirs mapping

    Output payload adds:
        - classified_files (dict[str, list[dict]]): role → files
    """

    def call(self, payload):
        source_files = payload.get("source_files", [])
        config = payload.get("config", {})
        output = config.get("output", {})

        # Build reverse map: directory → role
        dir_to_role: Dict[str, str] = {}
        for role, directory in output.items():
            if role == "base":
                continue
            # Normalize: strip trailing slash
            normalized = directory.rstrip("/")
            dir_to_role[normalized] = role

        classified: Dict[str, List[Dict[str, Any]]] = {}

        for file_info in source_files:
            file_dir = file_info.get("dir", "")
            role = _match_dir_to_role(file_dir, dir_to_role)
            classified.setdefault(role, []).append(file_info)

        return payload.insert("classified_files", classified)


def _match_dir_to_role(file_dir: str, dir_to_role: Dict[str, str]) -> str:
    """Match a file's directory to the closest role."""
    normalized = file_dir.rstrip("/")

    # Exact match
    if normalized in dir_to_role:
        return dir_to_role[normalized]

    # Check if file_dir is under a role directory
    for directory, role in dir_to_role.items():
        if normalized.startswith(directory):
            return role

    return "uncategorized"
