"""
ClassifyStepsFilter: Maps pipeline steps to architectural roles using config patterns.
"""

import fnmatch
from typing import Any, Dict, List
from codeupipe import Payload


class ClassifyStepsFilter:
    """
    Filter: Classify pipeline steps into architectural roles.

    Input payload keys:
        - steps (list[dict]): Step manifest from AnalyzePipelineFilter
        - hooks (list[dict]): Hook manifest from AnalyzePipelineFilter
        - config (dict): Resolved config with 'roles' mapping

    Output payload adds:
        - classified (dict[str, list[dict]]): role_name → list of steps
    """

    def call(self, payload):
        steps = payload.get("steps", [])
        hooks = payload.get("hooks", [])
        config = payload.get("config", {})
        roles = config.get("roles", {})

        classified: Dict[str, List[Dict[str, Any]]] = {}

        for step in steps:
            role = _match_role(step["name"], step["type"], roles)
            classified.setdefault(role, []).append(step)

        for hook in hooks:
            role = _match_role(hook["class_name"], "hook", roles)
            classified.setdefault(role, []).append(hook)

        return payload.insert("classified", classified)


def _match_role(name: str, step_type: str, roles: Dict[str, List[str]]) -> str:
    """Match a step name/type against role glob patterns."""
    for role, patterns in roles.items():
        for pattern in patterns:
            # Type-based special tokens
            if pattern.startswith("_") and pattern == f"_{step_type}":
                return role
            # Name-based glob matching
            if fnmatch.fnmatch(name, pattern):
                return role
    return "uncategorized"
