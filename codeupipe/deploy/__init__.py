"""
Deploy: Protocol, discovery, and built-in adapters for pipeline deployment.

Ring 7 of the codeupipe expansion. Zero external dependencies.
Cloud-specific adapters live in separate packages (codeupipe-deploy-aws, etc.)
and register via Python entry points.
"""

from .adapter import DeployTarget, DeployAdapter
from .discovery import find_adapters
from .docker import DockerAdapter
from .vercel import VercelAdapter
from .netlify import NetlifyAdapter
from .manifest import load_manifest, ManifestError
from .recipe import resolve_recipe, list_recipes, RecipeError
from .init import init_project, list_templates, InitError
from .handlers import render_vercel_handler, render_netlify_handler, render_lambda_handler

__all__ = [
    "DeployTarget",
    "DeployAdapter",
    "DockerAdapter",
    "VercelAdapter",
    "NetlifyAdapter",
    "find_adapters",
    "load_manifest",
    "ManifestError",
    "resolve_recipe",
    "list_recipes",
    "RecipeError",
    "init_project",
    "list_templates",
    "InitError",
    "render_vercel_handler",
    "render_netlify_handler",
    "render_lambda_handler",
]
