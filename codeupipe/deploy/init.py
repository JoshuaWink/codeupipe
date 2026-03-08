"""
Project scaffolding engine for `cup init`.

Generates complete project structures — pipelines, filters, tests, deploy
artifacts, CI workflows, and cup.toml manifest. Zero external dependencies.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

__all__ = ["init_project", "list_templates", "InitError", "CI_PROVIDERS"]


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
    ci_provider: str = "github",
    frontend: Optional[str] = None,
    options: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """Initialize a new codeupipe project.

    Args:
        template: Project template type ('saas', 'api', 'etl', 'chatbot').
        name: Project name.
        output_dir: Directory to create project in (default: ./{name}).
        deploy_target: Deployment target (default: 'docker').
        ci_provider: CI platform ('github', 'gitlab', 'azure-devops',
            'bitbucket', 'circleci').  Default: 'github'.
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

    if ci_provider not in _CI_PROVIDERS:
        available = ", ".join(_CI_PROVIDERS.keys())
        raise InitError(
            f"Unknown CI provider '{ci_provider}'. Available: {available}"
        )

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

    # 6. CI config (provider-specific path and content)
    renderer, ci_rel_dir, ci_filename = _CI_PROVIDERS[ci_provider]
    ci_dir = project_dir / ci_rel_dir
    ci_dir.mkdir(parents=True, exist_ok=True)
    _write(ci_dir / ci_filename, renderer(name, frontend), created_files)

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


# ── CI Provider Registry ────────────────────────────────────────────

# Maps ci_provider key → (renderer_func, relative_dir, filename)
# The dispatcher is populated after the renderer functions are defined.

_CI_PROVIDERS: Dict[str, tuple] = {}  # filled at module bottom


def _render_github_ci(name: str, frontend: Optional[str] = None) -> str:
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


# Keep the old name as an alias for backward compatibility
_render_ci_workflow = _render_github_ci


def _render_gitlab_ci(name: str, frontend: Optional[str] = None) -> str:
    lines = [
        f"# CI — {name}",
        "",
        "stages:",
        "  - test",
        "",
        "test:",
        "  stage: test",
        "  image: python:3.12",
        "  parallel:",
        "    matrix:",
        "      - PYTHON_VERSION:",
        '          - "3.9"',
        '          - "3.12"',
        '          - "3.13"',
        "  image: python:$PYTHON_VERSION",
    ]

    if frontend:
        lines.extend([
            "  before_script:",
            "    - apt-get update && apt-get install -y nodejs npm",
            "    - cd frontend && npm ci && npm run build && cd ..",
        ])

    lines.extend([
        "  script:",
        "    - pip install -e '.[dev]'",
        "    - python -m pytest -q",
    ])
    return "\n".join(lines) + "\n"


def _render_azure_pipelines(name: str, frontend: Optional[str] = None) -> str:
    lines = [
        f"# CI — {name}",
        "",
        "trigger:",
        "  branches:",
        "    include:",
        "      - main",
        "",
        "pr:",
        "  branches:",
        "    include:",
        "      - main",
        "",
        "pool:",
        "  vmImage: ubuntu-latest",
        "",
        "strategy:",
        "  matrix:",
        "    Python39:",
        "      python.version: '3.9'",
        "    Python312:",
        "      python.version: '3.12'",
        "    Python313:",
        "      python.version: '3.13'",
        "",
        "steps:",
        "  - task: UsePythonVersion@0",
        "    inputs:",
        "      versionSpec: $(python.version)",
    ]

    if frontend:
        lines.extend([
            "  - task: UseNode@1",
            "    inputs:",
            "      version: '20.x'",
            "  - script: cd frontend && npm ci && npm run build",
            "    displayName: Build frontend",
        ])

    lines.extend([
        "  - script: pip install -e '.[dev]'",
        "    displayName: Install dependencies",
        "  - script: python -m pytest -q",
        "    displayName: Run tests",
    ])
    return "\n".join(lines) + "\n"


def _render_bitbucket_pipelines(name: str, frontend: Optional[str] = None) -> str:
    lines = [
        f"# CI — {name}",
        "",
        "image: python:3.12",
        "",
        "pipelines:",
        "  default:",
        "    - parallel:",
    ]

    for ver in ("3.9", "3.12", "3.13"):
        lines.append(f"        - step:")
        lines.append(f"            name: Python {ver}")
        lines.append(f"            image: python:{ver}")

        if frontend:
            lines.extend([
                "            script:",
                "              - apt-get update && apt-get install -y nodejs npm",
                "              - cd frontend && npm ci && npm run build && cd ..",
                "              - pip install -e '.[dev]'",
                "              - python -m pytest -q",
            ])
        else:
            lines.extend([
                "            script:",
                "              - pip install -e '.[dev]'",
                "              - python -m pytest -q",
            ])

    return "\n".join(lines) + "\n"


def _render_circleci_config(name: str, frontend: Optional[str] = None) -> str:
    lines = [
        f"# CI — {name}",
        "",
        "version: 2.1",
        "",
        "jobs:",
        "  test:",
        "    parameters:",
        "      python-version:",
        "        type: string",
        "    docker:",
        "      - image: cimg/python:<< parameters.python-version >>",
        "    steps:",
        "      - checkout",
    ]

    if frontend:
        lines.extend([
            "      - run:",
            "          name: Install Node.js",
            "          command: |",
            "            curl -fsSL https://deb.nodesource.com/setup_20.x | sudo bash -",
            "            sudo apt-get install -y nodejs",
            "      - run:",
            "          name: Build frontend",
            "          command: cd frontend && npm ci && npm run build",
        ])

    lines.extend([
        "      - run:",
        "          name: Install dependencies",
        "          command: pip install -e '.[dev]'",
        "      - run:",
        "          name: Run tests",
        "          command: python -m pytest -q",
        "",
        "workflows:",
        f"  ci-{name}:",
        "    jobs:",
        "      - test:",
        "          matrix:",
        "            parameters:",
        "              python-version:",
        '                - "3.9"',
        '                - "3.12"',
        '                - "3.13"',
    ])
    return "\n".join(lines) + "\n"


def _render_jenkins(name: str, frontend: Optional[str] = None) -> str:
    lines = [
        f"// CI — {name}",
        "pipeline {",
        "    agent { docker { image 'python:3.12' } }",
        "",
        "    stages {",
    ]

    if frontend:
        lines.extend([
            "        stage('Frontend') {",
            "            agent { docker { image 'node:20' } }",
            "            steps {",
            "                dir('frontend') {",
            "                    sh 'npm ci'",
            "                    sh 'npm run build'",
            "                }",
            "            }",
            "        }",
        ])

    lines.extend([
        "        stage('Install') {",
        "            steps {",
        "                sh \"pip install -e '.[dev]'\"",
        "            }",
        "        }",
        "",
        "        stage('Test') {",
        "            matrix {",
        "                axes {",
        "                    axis {",
        "                        name 'PYTHON_VERSION'",
        "                        values '3.9', '3.12', '3.13'",
        "                    }",
        "                }",
        "                agent { docker { image \"python:${PYTHON_VERSION}\" } }",
        "                stages {",
        "                    stage('Run') {",
        "                        steps {",
        "                            sh \"pip install -e '.[dev]'\"",
        "                            sh 'python -m pytest -q'",
        "                        }",
        "                    }",
        "                }",
        "            }",
        "        }",
        "    }",
        "}",
    ])
    return "\n".join(lines) + "\n"


def _render_forgejo_ci(name: str, frontend: Optional[str] = None) -> str:
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


def _render_gitea_ci(name: str, frontend: Optional[str] = None) -> str:
    # Gitea Actions uses the same syntax as Forgejo/GitHub Actions
    return _render_forgejo_ci(name, frontend)


def _render_buildkite(name: str, frontend: Optional[str] = None) -> str:
    lines = [
        f"# CI — {name}",
        "",
        "steps:",
    ]

    if frontend:
        lines.extend([
            "  - label: \":nodejs: Build frontend\"",
            "    command:",
            "      - cd frontend && npm ci && npm run build",
            "    plugins:",
            "      - docker#v5.11.0:",
            "          image: node:20",
            "",
        ])

    for ver in ("3.9", "3.12", "3.13"):
        lines.extend([
            f"  - label: \":python: {ver}\"",
            "    command:",
            "      - pip install -e '.[dev]'",
            "      - python -m pytest -q",
            "    plugins:",
            "      - docker#v5.11.0:",
            f"          image: python:{ver}",
            "",
        ])

    return "\n".join(lines) + "\n"


def _render_drone(name: str, frontend: Optional[str] = None) -> str:
    lines = [
        f"# CI — {name}",
        "",
        "kind: pipeline",
        "type: docker",
        f"name: {name}",
        "",
        "trigger:",
        "  branch:",
        "    - main",
        "",
        "steps:",
    ]

    if frontend:
        lines.extend([
            "  - name: frontend",
            "    image: node:20",
            "    commands:",
            "      - cd frontend && npm ci && npm run build",
            "",
        ])

    for ver in ("3.9", "3.12", "3.13"):
        lines.extend([
            f"  - name: test-{ver}",
            f"    image: python:{ver}",
            "    commands:",
            "      - pip install -e '.[dev]'",
            "      - python -m pytest -q",
            "",
        ])

    return "\n".join(lines) + "\n"


def _render_woodpecker(name: str, frontend: Optional[str] = None) -> str:
    # Woodpecker uses the same YAML syntax as Drone
    return _render_drone(name, frontend)


def _render_travis(name: str, frontend: Optional[str] = None) -> str:
    lines = [
        f"# CI — {name}",
        "",
        "language: python",
        "",
        "python:",
        '  - "3.9"',
        '  - "3.12"',
        '  - "3.13"',
        "",
    ]

    if frontend:
        lines.extend([
            "before_install:",
            "  - nvm install 20",
            "  - nvm use 20",
            "  - cd frontend && npm ci && npm run build && cd ..",
            "",
        ])

    lines.extend([
        "install:",
        "  - pip install -e '.[dev]'",
        "",
        "script:",
        "  - python -m pytest -q",
    ])
    return "\n".join(lines) + "\n"


def _render_aws_codebuild(name: str, frontend: Optional[str] = None) -> str:
    lines = [
        f"# CI — {name}",
        "",
        "version: 0.2",
        "",
        "phases:",
        "  install:",
        "    runtime-versions:",
        "      python: 3.12",
    ]

    if frontend:
        lines.extend([
            "      nodejs: 20",
        ])

    lines.append("    commands:")
    lines.append("      - pip install -e '.[dev]'")

    if frontend:
        lines.extend([
            "      - cd frontend && npm ci && npm run build && cd ..",
        ])

    lines.extend([
        "  build:",
        "    commands:",
        "      - python -m pytest -q",
    ])
    return "\n".join(lines) + "\n"


def _render_cloudbuild(name: str, frontend: Optional[str] = None) -> str:
    lines = [
        f"# CI — {name}",
        "",
        "steps:",
    ]

    if frontend:
        lines.extend([
            "  - name: node:20",
            "    entrypoint: bash",
            "    args:",
            "      - -c",
            "      - cd frontend && npm ci && npm run build",
            "",
        ])

    for ver in ("3.9", "3.12", "3.13"):
        lines.extend([
            f"  - name: python:{ver}",
            "    entrypoint: bash",
            "    args:",
            "      - -c",
            "      - pip install -e '.[dev]' && python -m pytest -q",
            "",
        ])

    return "\n".join(lines) + "\n"


# Dispatcher: provider → (renderer, relative_dir, filename)
_CI_PROVIDERS = {
    "github": (_render_github_ci, ".github/workflows", "ci.yml"),
    "gitlab": (_render_gitlab_ci, ".", ".gitlab-ci.yml"),
    "azure-devops": (_render_azure_pipelines, ".", "azure-pipelines.yml"),
    "bitbucket": (_render_bitbucket_pipelines, ".", "bitbucket-pipelines.yml"),
    "circleci": (_render_circleci_config, ".circleci", "config.yml"),
    "jenkins": (_render_jenkins, ".", "Jenkinsfile"),
    "forgejo": (_render_forgejo_ci, ".forgejo/workflows", "ci.yml"),
    "gitea": (_render_gitea_ci, ".gitea/workflows", "ci.yml"),
    "buildkite": (_render_buildkite, ".buildkite", "pipeline.yml"),
    "drone": (_render_drone, ".", ".drone.yml"),
    "woodpecker": (_render_woodpecker, ".", ".woodpecker.yml"),
    "travis": (_render_travis, ".", ".travis.yml"),
    "aws-codebuild": (_render_aws_codebuild, ".", "buildspec.yml"),
    "cloud-build": (_render_cloudbuild, ".", "cloudbuild.yaml"),
}

CI_PROVIDERS = list(_CI_PROVIDERS.keys())


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
