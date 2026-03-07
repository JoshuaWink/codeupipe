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
    frontend: Optional[str] = None,
    options: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """Initialize a new codeupipe project.

    Args:
        template: Project template type ('saas', 'api', 'etl', 'chatbot').
        name: Project name.
        output_dir: Directory to create project in (default: ./{name}).
        deploy_target: Deployment target (default: 'docker').
        frontend: Frontend framework ('react', 'next', 'vite', None).
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
    manifest = _render_manifest(name, deploy_target, frontend, opts)
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
    _write(gh_dir / "ci.yml", _render_ci_workflow(name, frontend), created_files)

    # 7. README.md
    _write(project_dir / "README.md", _render_readme(name, template, frontend, deploy_target), created_files)

    # 8. Frontend scaffold (if requested)
    if frontend:
        _scaffold_frontend(project_dir, name, frontend, deploy_target, created_files)

    return {
        "project_dir": str(project_dir),
        "files": created_files,
        "template": template,
        "frontend": frontend,
    }


def _write(path: Path, content: str, tracker: List[str]) -> None:
    path.write_text(content)
    tracker.append(str(path))


def _render_manifest(name: str, deploy_target: str, frontend: Optional[str], opts: Dict[str, str]) -> str:
    lines = [
        "[project]",
        f'name = "{name}"',
        'version = "0.1.0"',
        "",
    ]

    if frontend:
        lines.append("[frontend]")
        lines.append(f'framework = "{frontend}"')
        if frontend == "next":
            lines.append('build_command = "npm run build"')
            lines.append('output_dir = ".next"')
        else:
            lines.append('build_command = "npm run build"')
            lines.append('output_dir = "dist"')
        lines.append("")

    lines.append("[deploy]")
    lines.append(f'target = "{deploy_target}"')
    lines.append("")
    lines.append("[dependencies]")
    lines.append('codeupipe = ">=0.6.0"')

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


def _render_ci_workflow(name: str, frontend: Optional[str] = None) -> str:
    lines = [
        f"name: CI — {name}",
        "",
        "on:",
        "  push:",
        "    branches: [main]",
        "  pull_request:",
        "    branches: [main]",
        "",
        "jobs:",
        "  test:",
        "    runs-on: ubuntu-latest",
        "    strategy:",
        "      matrix:",
        '        python-version: ["3.9", "3.12", "3.13"]',
        "    steps:",
        "      - uses: actions/checkout@v4",
        "      - uses: actions/setup-python@v5",
        "        with:",
        "          python-version: ${{ matrix.python-version }}",
    ]

    if frontend:
        lines.extend([
            "      - uses: actions/setup-node@v4",
            "        with:",
            '          node-version: "20"',
            "      - run: cd frontend && npm ci",
            "      - run: cd frontend && npm run build",
        ])

    lines.extend([
        "      - run: pip install -e '.[dev]'",
        "      - run: python -m pytest -q",
    ])
    return "\n".join(lines) + "\n"


def _render_readme(
    name: str,
    template: str,
    frontend: Optional[str] = None,
    deploy_target: str = "docker",
) -> str:
    lines = [
        f"# {name}",
        "",
        f"A **{template}** project powered by [codeupipe](https://pypi.org/project/codeupipe/).",
        "",
        "## Quick Start",
        "",
        "```bash",
        "pip install -e .",
        "cup run pipelines/*.json",
        "```",
    ]

    if frontend:
        lines.extend([
            "",
            "## Frontend",
            "",
            "```bash",
            "cd frontend && npm install && npm run dev",
            "```",
        ])

    lines.extend([
        "",
        "## Deploy",
        "",
        "```bash",
        f"cup deploy {deploy_target}",
        "```",
    ])
    return "\n".join(lines) + "\n"


def _scaffold_frontend(
    project_dir: Path,
    name: str,
    frontend: str,
    deploy_target: str,
    created_files: List[str],
) -> None:
    """Create a minimal frontend scaffold."""
    fe_dir = project_dir / "frontend"
    fe_dir.mkdir()
    src_dir = fe_dir / "src"
    src_dir.mkdir()

    safe = name.replace("-", "_").replace(" ", "_")

    if frontend == "next":
        pkg = json.dumps(
            {
                "name": name,
                "private": True,
                "scripts": {"dev": "next dev", "build": "next build", "start": "next start"},
                "dependencies": {"next": "^14", "react": "^18", "react-dom": "^18"},
            },
            indent=2,
        )
        _write(fe_dir / "package.json", pkg + "\n", created_files)

        pages_dir = fe_dir / "pages"
        pages_dir.mkdir()
        _write(
            pages_dir / "index.jsx",
            f'export default function Home() {{\n  return <h1>{name}</h1>;\n}}\n',
            created_files,
        )
    else:
        # Vite + React (covers react, vite, and generic)
        pkg = json.dumps(
            {
                "name": name,
                "private": True,
                "type": "module",
                "scripts": {"dev": "vite", "build": "vite build", "preview": "vite preview"},
                "dependencies": {"react": "^18", "react-dom": "^18"},
                "devDependencies": {
                    "@vitejs/plugin-react": "^4",
                    "vite": "^5",
                },
            },
            indent=2,
        )
        _write(fe_dir / "package.json", pkg + "\n", created_files)
        _write(
            fe_dir / "vite.config.js",
            "import { defineConfig } from 'vite';\n"
            "import react from '@vitejs/plugin-react';\n"
            "\n"
            "export default defineConfig({\n"
            "  plugins: [react()],\n"
            "});\n",
            created_files,
        )
        _write(
            fe_dir / "index.html",
            '<!doctype html>\n<html lang="en">\n<head>\n'
            '  <meta charset="UTF-8" />\n'
            f'  <title>{name}</title>\n'
            '</head>\n<body>\n'
            '  <div id="root"></div>\n'
            '  <script type="module" src="/src/main.jsx"></script>\n'
            '</body>\n</html>\n',
            created_files,
        )
        _write(
            src_dir / "main.jsx",
            "import React from 'react';\n"
            "import ReactDOM from 'react-dom/client';\n"
            "import App from './App';\n"
            "\n"
            "ReactDOM.createRoot(document.getElementById('root')).render(\n"
            "  <React.StrictMode><App /></React.StrictMode>\n"
            ");\n",
            created_files,
        )

    _write(
        src_dir / "App.jsx",
        f'export default function App() {{\n  return <h1>{name}</h1>;\n}}\n',
        created_files,
    )
