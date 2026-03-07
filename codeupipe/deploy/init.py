"""
Project scaffolding engine for `cup init`.

Generates complete project structures — pipelines, filters, tests, deploy
artifacts, CI workflows, and cup.toml manifest. Zero external dependencies.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

__all__ = ["init_project", "list_templates", "InitError"]


class InitError(Exception):
    """Raised when project initialization fails."""


# Available project template types
_TEMPLATES = {
    "saas": {
        "description": "Full-stack SaaS — signup, checkout, webhook handling",
        "recipes": ["saas-signup", "webhook-handler"],
    },
    "api": {
        "description": "REST API — CRUD endpoints with auth and database",
        "recipes": ["api-crud"],
    },
    "etl": {
        "description": "Data pipeline — extract, transform, load",
        "recipes": ["etl"],
    },
    "chatbot": {
        "description": "AI chatbot — input sanitization, LLM call, safety filter",
        "recipes": ["ai-chat"],
    },
}


def list_templates() -> List[Dict[str, str]]:
    """List available project template types."""
    return [
        {"name": name, "description": info["description"]}
        for name, info in _TEMPLATES.items()
    ]


def init_project(
    template: str,
    name: str,
    output_dir: Optional[str] = None,
    *,
    deploy_target: str = "docker",
    options: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """Initialize a new codeupipe project.

    Args:
        template: Project template type ('saas', 'api', 'etl', 'chatbot').
        name: Project name.
        output_dir: Directory to create project in (default: ./{name}).
        deploy_target: Deployment target (default: 'docker').
        options: Additional options (auth, db, payments, ai providers).

    Returns:
        Dict with 'project_dir' and 'files' (list of created files).

    Raises:
        InitError: If template is invalid or directory already exists.
    """
    if template not in _TEMPLATES:
        available = ", ".join(_TEMPLATES.keys())
        raise InitError(f"Unknown template '{template}'. Available: {available}")

    opts = options or {}
    project_dir = Path(output_dir) if output_dir else Path(name)

    if project_dir.exists():
        raise InitError(f"Directory '{project_dir}' already exists")

    project_dir.mkdir(parents=True)
    created_files: List[str] = []

    # 1. cup.toml manifest
    manifest = _render_manifest(name, deploy_target, opts)
    _write(project_dir / "cup.toml", manifest, created_files)

    # 2. pyproject.toml
    pyproject = _render_pyproject(name)
    _write(project_dir / "pyproject.toml", pyproject, created_files)

    # 3. pipelines/ directory with recipe-based configs
    pipelines_dir = project_dir / "pipelines"
    pipelines_dir.mkdir()
    template_info = _TEMPLATES[template]
    for recipe_name in template_info["recipes"]:
        config = _render_pipeline_config(recipe_name, opts)
        _write(pipelines_dir / f"{recipe_name}.json", config, created_files)

    # 4. filters/ directory with placeholder
    filters_dir = project_dir / "filters"
    filters_dir.mkdir()
    _write(filters_dir / "__init__.py", '"""Custom filters for this project."""\n', created_files)
    _write(filters_dir / "custom.py", _render_custom_filter(), created_files)

    # 5. tests/ directory with scaffold
    tests_dir = project_dir / "tests"
    tests_dir.mkdir()
    _write(tests_dir / "__init__.py", "", created_files)
    _write(tests_dir / f"test_{name.replace('-', '_')}.py", _render_test_scaffold(name), created_files)

    # 6. .github/workflows/ci.yml
    gh_dir = project_dir / ".github" / "workflows"
    gh_dir.mkdir(parents=True)
    _write(gh_dir / "ci.yml", _render_ci_workflow(name), created_files)

    # 7. README.md
    _write(project_dir / "README.md", _render_readme(name, template), created_files)

    return {
        "project_dir": str(project_dir),
        "files": created_files,
        "template": template,
    }


def _write(path: Path, content: str, tracker: List[str]) -> None:
    path.write_text(content)
    tracker.append(str(path))


def _render_manifest(name: str, deploy_target: str, opts: Dict[str, str]) -> str:
    lines = [
        "[project]",
        f'name = "{name}"',
        'version = "0.1.0"',
        "",
        "[deploy]",
        f'target = "{deploy_target}"',
        "",
        "[dependencies]",
        'codeupipe = ">=0.5.0"',
    ]
    for key, value in opts.items():
        lines.append(f'codeupipe-{key} = {{ provider = "{value}" }}')
    return "\n".join(lines) + "\n"


def _render_pyproject(name: str) -> str:
    safe_name = name.replace("-", "_")
    return (
        "[build-system]\n"
        'requires = ["setuptools>=68.0", "wheel"]\n'
        'build-backend = "setuptools.build_meta"\n'
        "\n"
        "[project]\n"
        f'name = "{name}"\n'
        'version = "0.1.0"\n'
        f'description = "{name} — powered by codeupipe"\n'
        'requires-python = ">=3.9"\n'
        'dependencies = ["codeupipe>=0.5.0"]\n'
    )


def _render_pipeline_config(recipe_name: str, opts: Dict[str, str]) -> str:
    """Generate a pipeline config, substituting known options."""
    # Simple mapping from option keys to recipe variable names
    var_map = {
        "auth": "auth_provider",
        "email": "email_provider",
        "payments": "payment_provider",
        "db": "db_provider",
        "ai": "ai_provider",
        "source": "source_provider",
        "sink": "sink_provider",
    }

    config: Dict[str, Any] = {
        "pipeline": {
            "name": recipe_name,
            "steps": [{"name": "Placeholder", "type": "filter"}],
        }
    }

    # Try to load and resolve the actual recipe
    try:
        from .recipe import resolve_recipe
        variables = {}
        for opt_key, var_name in var_map.items():
            if opt_key in opts:
                variables[var_name] = opts[opt_key]

        resolved, _ = resolve_recipe(recipe_name, variables)
        config = resolved
    except Exception:
        pass  # Fall back to placeholder config

    return json.dumps(config, indent=2) + "\n"


def _render_custom_filter() -> str:
    return (
        '"""Custom filter — replace with your business logic."""\n'
        "\n"
        "from codeupipe import Payload\n"
        "\n"
        "\n"
        "class CustomFilter:\n"
        '    """Example filter — modify and return the payload."""\n'
        "\n"
        "    async def call(self, payload: Payload) -> Payload:\n"
        '        return payload.insert("custom", True)\n'
    )


def _render_test_scaffold(name: str) -> str:
    safe = name.replace("-", "_")
    return (
        f'"""Tests for {name} pipeline."""\n'
        "\n"
        "import pytest\n"
        "from codeupipe import Payload, Pipeline\n"
        "\n"
        "\n"
        f"class Test{safe.title().replace('_', '')}:\n"
        f'    """Smoke tests for the {name} project."""\n'
        "\n"
        "    def test_placeholder(self):\n"
        '        """Replace with real tests."""\n'
        '        p = Payload({"test": True})\n'
        '        assert p.get("test") is True\n'
    )


def _render_ci_workflow(name: str) -> str:
    return (
        f"name: CI — {name}\n"
        "\n"
        "on:\n"
        "  push:\n"
        "    branches: [main]\n"
        "  pull_request:\n"
        "    branches: [main]\n"
        "\n"
        "jobs:\n"
        "  test:\n"
        "    runs-on: ubuntu-latest\n"
        "    strategy:\n"
        "      matrix:\n"
        '        python-version: ["3.9", "3.12", "3.13"]\n'
        "    steps:\n"
        "      - uses: actions/checkout@v4\n"
        "      - uses: actions/setup-python@v5\n"
        "        with:\n"
        "          python-version: ${{ matrix.python-version }}\n"
        "      - run: pip install -e '.[dev]'\n"
        "      - run: python -m pytest -q\n"
    )


def _render_readme(name: str, template: str) -> str:
    return (
        f"# {name}\n"
        "\n"
        f"A **{template}** project powered by [codeupipe](https://pypi.org/project/codeupipe/).\n"
        "\n"
        "## Quick Start\n"
        "\n"
        "```bash\n"
        "pip install -e .\n"
        "cup run pipelines/*.json\n"
        "```\n"
        "\n"
        "## Deploy\n"
        "\n"
        "```bash\n"
        "cup deploy docker\n"
        "```\n"
    )
