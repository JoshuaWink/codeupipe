"""
cup.toml manifest parser.

The project manifest declares project metadata, deploy target,
dependencies, and secrets. Zero external dependencies — uses stdlib
tomllib (3.11+) or falls back to tomli.
"""

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

__all__ = ["load_manifest", "ManifestError"]


class ManifestError(Exception):
    """Raised when a cup.toml manifest is invalid or missing."""


def load_manifest(path: str = "cup.toml") -> Dict[str, Any]:
    """Load and validate a cup.toml project manifest.

    Args:
        path: Path to the manifest file. Supports .toml and .json.

    Returns:
        Parsed manifest dict with at least 'project' and 'deploy' sections.

    Raises:
        ManifestError: If the file is missing, unparsable, or invalid.
        FileNotFoundError: If the file does not exist.
    """
    manifest_path = Path(path)
    if not manifest_path.exists():
        raise FileNotFoundError(f"Manifest not found: {path}")

    text = manifest_path.read_text()
    suffix = manifest_path.suffix.lower()

    if suffix == ".toml":
        data = _parse_toml(text)
    elif suffix == ".json":
        data = json.loads(text)
    else:
        raise ManifestError(f"Unsupported manifest format '{suffix}'. Use .toml or .json")

    _validate(data, path)
    return data


def _parse_toml(text: str) -> dict:
    """Parse TOML text, using stdlib tomllib (3.11+) or fallback."""
    if sys.version_info >= (3, 11):
        import tomllib
        return tomllib.loads(text)
    try:
        import tomli
        return tomli.loads(text)
    except ImportError:
        raise ImportError(
            "TOML manifest requires Python 3.11+ or the 'tomli' package. "
            "Install with: pip install tomli"
        )


def _validate(data: dict, path: str) -> None:
    """Validate required manifest structure."""
    if "project" not in data:
        raise ManifestError(f"{path}: missing [project] section")

    project = data["project"]
    if "name" not in project:
        raise ManifestError(f"{path}: [project] missing 'name'")

    # Validate [frontend] section if present
    frontend = data.get("frontend")
    if frontend:
        if "framework" not in frontend:
            raise ManifestError(f"{path}: [frontend] missing 'framework'")
        valid_frameworks = ("react", "next", "vite", "remix", "static")
        if frontend["framework"] not in valid_frameworks:
            raise ManifestError(
                f"{path}: [frontend] unsupported framework '{frontend['framework']}'. "
                f"Valid: {', '.join(valid_frameworks)}"
            )

    # Validate [deploy] section if present
    deploy = data.get("deploy")
    if deploy and "target" in deploy:
        valid_targets = ("docker", "vercel", "netlify", "aws", "aws-lambda", "aws-s3")
        if deploy["target"] not in valid_targets:
            raise ManifestError(
                f"{path}: [deploy] unsupported target '{deploy['target']}'. "
                f"Valid: {', '.join(valid_targets)}"
            )
