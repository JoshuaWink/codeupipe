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
from .render import RenderAdapter
from .fly import FlyAdapter
from .railway import RailwayAdapter
from .cloudrun import CloudRunAdapter
from .koyeb import KoyebAdapter
from .apprunner import AppRunnerAdapter
from .oracle import OracleAdapter
from .azure_container_apps import AzureContainerAppsAdapter
from .huggingface import HuggingFaceAdapter
from .manifest import load_manifest, ManifestError
from .recipe import resolve_recipe, list_recipes, RecipeError
from .init import (
    init_project, list_templates, InitError, CI_PROVIDERS,
    detect_ci, validate_ci_deploy, regenerate_ci,
)
from .handlers import render_vercel_handler, render_netlify_handler, render_lambda_handler

__all__ = [
    "DeployTarget",
    "DeployAdapter",
    "DockerAdapter",
    "VercelAdapter",
    "NetlifyAdapter",
    "RenderAdapter",
    "FlyAdapter",
    "RailwayAdapter",
    "CloudRunAdapter",
    "KoyebAdapter",
    "AppRunnerAdapter",
    "OracleAdapter",
    "AzureContainerAppsAdapter",
    "HuggingFaceAdapter",
    "find_adapters",
    "load_manifest",
    "ManifestError",
    "resolve_recipe",
    "list_recipes",
    "RecipeError",
    "init_project",
    "list_templates",
    "InitError",
    "CI_PROVIDERS",
    "detect_ci",
    "validate_ci_deploy",
    "regenerate_ci",
    "render_vercel_handler",
    "render_netlify_handler",
    "render_lambda_handler",
]
