"""
Config: Conversion configuration parsing.

Reads .cup.json (zero deps) or pyproject.toml [tool.cup] (Python 3.11+).
Provides sensible defaults for MVC, Clean, Hexagonal, and Flat patterns.
"""

import json
from pathlib import Path
from typing import Any, Dict, Optional

__all__ = ["load_config", "DEFAULT_CONFIG", "PATTERN_DEFAULTS"]


PATTERN_DEFAULTS: Dict[str, Dict[str, Any]] = {
    "mvc": {
        "roles": {
            "model": ["fetch_*", "save_*", "db_*", "load_*", "store_*"],
            "view": ["format_*", "render_*", "serialize_*", "display_*"],
            "controller": ["validate_*", "authorize_*", "calc_*", "process_*", "route_*"],
            "middleware": ["_tap", "_hook", "_valve"],
        },
        "output": {
            "model": "models/",
            "view": "views/",
            "controller": "controllers/",
            "middleware": "middleware/",
        },
    },
    "clean": {
        "roles": {
            "entity": ["_payload"],
            "use_case": ["calc_*", "process_*", "validate_*", "apply_*", "check_*"],
            "interface_adapter": ["fetch_*", "save_*", "db_*", "send_*", "_tap", "_valve"],
            "framework": ["_hook", "retry_*", "log_*"],
        },
        "output": {
            "entity": "entities/",
            "use_case": "use_cases/",
            "interface_adapter": "interface_adapters/",
            "framework": "frameworks/",
        },
    },
    "hexagonal": {
        "roles": {
            "domain": ["calc_*", "process_*", "validate_*", "apply_*", "check_*"],
            "adapter_inbound": ["parse_*", "deserialize_*", "route_*"],
            "adapter_outbound": ["fetch_*", "save_*", "db_*", "send_*", "publish_*"],
            "port": ["_protocol"],
            "infrastructure": ["_tap", "_hook", "_valve", "retry_*", "log_*"],
        },
        "output": {
            "domain": "domain/",
            "adapter_inbound": "adapters/inbound/",
            "adapter_outbound": "adapters/outbound/",
            "port": "ports/",
            "infrastructure": "infrastructure/",
        },
    },
    "flat": {
        "roles": {
            "step": ["*"],
        },
        "output": {
            "step": "steps/",
        },
    },
}

DEFAULT_CONFIG: Dict[str, Any] = {
    "pattern": "flat",
    "roles": PATTERN_DEFAULTS["flat"]["roles"],
    "output": {
        "base": "src/",
        **PATTERN_DEFAULTS["flat"]["output"],
    },
}


def load_config(config_path: Optional[str] = None, pattern: Optional[str] = None) -> Dict[str, Any]:
    """
    Load conversion config from .cup.json, or fall back to pattern defaults.

    Priority:
    1. Explicit config_path (.cup.json)
    2. Pattern name → built-in defaults
    3. DEFAULT_CONFIG (flat)
    """
    if config_path:
        path = Path(config_path)
        if path.exists() and path.suffix == ".json":
            with open(path) as f:
                config = json.load(f)
            return _resolve_config(config)

    if pattern and pattern in PATTERN_DEFAULTS:
        return _resolve_config({"pattern": pattern})

    return DEFAULT_CONFIG.copy()


def _resolve_config(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Merge raw config with pattern defaults."""
    pattern = raw.get("pattern", "flat")
    defaults = PATTERN_DEFAULTS.get(pattern, PATTERN_DEFAULTS["flat"])

    roles = raw.get("roles", defaults["roles"])
    output_dirs = raw.get("output", {})
    base = output_dirs.pop("base", "src/") if isinstance(output_dirs, dict) else "src/"

    # Merge: explicit output dirs override pattern defaults
    resolved_output = {**defaults["output"], **output_dirs}
    resolved_output["base"] = base

    return {
        "pattern": pattern,
        "roles": roles,
        "output": resolved_output,
    }
