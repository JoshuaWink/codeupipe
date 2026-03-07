"""
Deploy: Protocol, discovery, and built-in adapters for pipeline deployment.

Ring 7 of the codeupipe expansion. Zero external dependencies.
Cloud-specific adapters live in separate packages (codeupipe-deploy-aws, etc.)
and register via Python entry points.
"""

from .adapter import DeployTarget, DeployAdapter
from .discovery import find_adapters
from .docker import DockerAdapter
from .manifest import load_manifest, ManifestError
from .recipe import resolve_recipe, list_recipes, RecipeError
from .init import init_project, list_templates, InitError

__all__ = [
    "DeployTarget",
    "DeployAdapter",
    "DockerAdapter",
    "find_adapters",
    "load_manifest",
    "ManifestError",
    "resolve_recipe",
    "list_recipes",
    "RecipeError",
    "init_project",
    "list_templates",
    "InitError",
]
