"""
Recipe engine: composable workflow templates with variable substitution.

Recipes are TOML/JSON pipeline configs with ${variable} placeholders.
The engine resolves variables, identifies required codeupipe-* packages,
and writes the final pipeline config.
"""

import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

__all__ = ["resolve_recipe", "list_recipes", "RecipeError"]

# Bundled recipes live alongside this module
_RECIPES_DIR = Path(__file__).parent / "recipes"

_VAR_PATTERN = re.compile(r"\$\{(\w+)\}")


class RecipeError(Exception):
    """Raised when a recipe is invalid or variables are missing."""


def list_recipes() -> List[Dict[str, str]]:
    """List all available bundled recipes.

    Returns:
        List of dicts with 'name' and 'description' keys.
    """
    recipes = []
    if not _RECIPES_DIR.exists():
        return recipes

    for path in sorted(_RECIPES_DIR.glob("*.json")):
        try:
            data = json.loads(path.read_text())
            meta = data.get("recipe", {})
            recipes.append({
                "name": meta.get("name", path.stem),
                "description": meta.get("description", ""),
            })
        except Exception:
            continue
    return recipes


def resolve_recipe(
    recipe_name: str,
    variables: Dict[str, str],
) -> Tuple[Dict[str, Any], List[str]]:
    """Resolve a recipe template with variable substitution.

    Args:
        recipe_name: Name of the recipe (matches filename without extension).
        variables: Mapping of variable names to values.

    Returns:
        Tuple of (resolved pipeline config dict, list of dependency package names).

    Raises:
        RecipeError: If recipe not found or required variables missing.
    """
    template_path = _RECIPES_DIR / f"{recipe_name}.json"
    if not template_path.exists():
        available = [r["name"] for r in list_recipes()]
        raise RecipeError(
            f"Recipe '{recipe_name}' not found. "
            f"Available: {', '.join(available) if available else 'none'}"
        )

    raw = template_path.read_text()
    template = json.loads(raw)
    meta = template.get("recipe", {})
    required_vars = meta.get("variables", [])

    # Check for missing variables
    missing = [v for v in required_vars if v not in variables]
    if missing:
        raise RecipeError(
            f"Recipe '{recipe_name}' requires variables: {', '.join(missing)}"
        )

    # Substitute ${var} placeholders in the JSON text
    resolved_text = raw
    for var_name, var_value in variables.items():
        resolved_text = resolved_text.replace(f"${{{var_name}}}", var_value)

    # Check for unresolved variables
    unresolved = _VAR_PATTERN.findall(resolved_text)
    if unresolved:
        raise RecipeError(
            f"Unresolved variables in recipe '{recipe_name}': {', '.join(set(unresolved))}"
        )

    resolved = json.loads(resolved_text)

    # Remove the recipe metadata — return just the pipeline config
    resolved.pop("recipe", None)

    # Identify dependencies from step names
    deps = _extract_dependencies(resolved)

    return resolved, deps


def _extract_dependencies(config: dict) -> List[str]:
    """Identify codeupipe-* packages needed by analyzing step names."""
    deps: List[str] = []
    seen = set()
    steps = config.get("pipeline", {}).get("steps", [])

    # Known connector prefixes → package mapping
    _PREFIX_MAP = {
        "Stripe": "codeupipe-payments",
        "PayPal": "codeupipe-payments",
        "Clerk": "codeupipe-auth",
        "Auth0": "codeupipe-auth",
        "Supabase": "codeupipe-auth",
        "SendGrid": "codeupipe-email",
        "Resend": "codeupipe-email",
        "Postmark": "codeupipe-email",
        "OpenAI": "codeupipe-ai",
        "Anthropic": "codeupipe-ai",
        "Ollama": "codeupipe-ai",
        "S3": "codeupipe-storage",
        "GCS": "codeupipe-storage",
        "Postgres": "codeupipe-database",
        "MySQL": "codeupipe-database",
        "SQLite": "codeupipe-database",
        "Redis": "codeupipe-cache",
    }

    for step in steps:
        name = step.get("name", "")
        for prefix, pkg in _PREFIX_MAP.items():
            if name.startswith(prefix) and pkg not in seen:
                deps.append(pkg)
                seen.add(pkg)

    return deps
