"""
Project scaffolding engine for `cup init`.

Generates complete project structures — pipelines, filters, tests, deploy
artifacts, CI workflows, and cup.toml manifest. Zero external dependencies.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

__all__ = [
    "init_project",
    "list_templates",
    "InitError",
    "CI_PROVIDERS",
    "detect_ci",
    "validate_ci_deploy",
]


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
        ci_provider: CI platform(s).  Comma-separated for multiple
            (e.g. ``'github,gitlab'``).  Default: ``'github'``.
        frontend: Frontend framework ('react', 'next', 'vite', None).
        options: Additional options (auth, db, payments, ai providers).

    Returns:
        Dict with 'project_dir', 'files', 'warnings' (list of created files
        and any cross-axis validation warnings).

    Raises:
        InitError: If template is invalid or directory already exists.
    """
    if template not in _TEMPLATES:
        available = ", ".join(_TEMPLATES.keys())
        raise InitError(f"Unknown template '{template}'. Available: {available}")

    # Parse comma-separated CI providers
    ci_providers = [p.strip() for p in ci_provider.split(",") if p.strip()]
    for p in ci_providers:
        if p not in _CI_PROVIDERS:
            available = ", ".join(_CI_PROVIDERS.keys())
            raise InitError(
                f"Unknown CI provider '{p}'. Available: {available}"
            )

    # Cross-axis validation
    warnings = validate_ci_deploy(ci_providers, deploy_target)

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

    # 6. CI config(s) — one per provider (composite when comma-separated)
    for cp in ci_providers:
        renderer, ci_rel_dir, ci_filename = _CI_PROVIDERS[cp]
        ci_dir = project_dir / ci_rel_dir
        ci_dir.mkdir(parents=True, exist_ok=True)
        _write(
            ci_dir / ci_filename,
            renderer(name, frontend, deploy_target),
            created_files,
        )

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
        "warnings": warnings,
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


# ── Cross-axis Validation ────────────────────────────────────────────

# Deploy targets that auto-deploy on git push (no explicit CD step needed)
_AUTO_DEPLOY_TARGETS = {"render", "railway", "koyeb", "hf-spaces"}

# Deploy targets with known CLI deploy commands
_CD_COMMANDS: Dict[str, str] = {
    "vercel": "npx vercel deploy --prod",
    "netlify": "npx netlify deploy --prod --dir=dist",
    "fly": "flyctl deploy",
    "cloudrun": "gcloud run deploy {name} --source .",
    "azure-container-apps": "az containerapp up --name {name} --source .",
    "apprunner": "aws apprunner create-service --source-configuration file://apprunner.json",
    "oracle": "oci ce cluster create-kubeconfig && kubectl apply -f k8s/",
}


def validate_ci_deploy(
    ci_providers: List[str], deploy_target: str
) -> List[str]:
    """Check CI×Deploy compatibility and return advisory warnings."""
    warnings: List[str] = []

    if deploy_target == "docker":
        return warnings  # Docker is universally compatible

    if deploy_target in _AUTO_DEPLOY_TARGETS:
        for cp in ci_providers:
            warnings.append(
                f"'{deploy_target}' auto-deploys on git push — "
                f"no CD step added to {cp} config."
            )
        return warnings

    # Check if CD commands exist for this target
    if deploy_target in _CD_COMMANDS:
        return warnings  # Will be wired into the CI config

    return warnings


def detect_ci(project_dir: str) -> List[Dict[str, str]]:
    """Detect which CI platform configs exist in a project directory.

    Returns list of dicts with 'provider', 'file', and 'path' keys.
    """
    root = Path(project_dir)
    found: List[Dict[str, str]] = []

    # Check each known CI config location
    _DETECT_MAP = {
        "github": (".github/workflows", "ci.yml"),
        "gitlab": (".", ".gitlab-ci.yml"),
        "azure-devops": (".", "azure-pipelines.yml"),
        "bitbucket": (".", "bitbucket-pipelines.yml"),
        "circleci": (".circleci", "config.yml"),
        "jenkins": (".", "Jenkinsfile"),
        "forgejo": (".forgejo/workflows", "ci.yml"),
        "gitea": (".gitea/workflows", "ci.yml"),
        "buildkite": (".buildkite", "pipeline.yml"),
        "drone": (".", ".drone.yml"),
        "woodpecker": (".", ".woodpecker.yml"),
        "travis": (".", ".travis.yml"),
        "aws-codebuild": (".", "buildspec.yml"),
        "cloud-build": (".", "cloudbuild.yaml"),
    }

    for provider, (rel_dir, filename) in _DETECT_MAP.items():
        ci_file = root / rel_dir / filename
        if ci_file.exists():
            found.append({
                "provider": provider,
                "file": filename,
                "path": str(ci_file),
            })

    return found


def regenerate_ci(
    project_dir: str,
    *,
    ci_provider: Optional[str] = None,
    deploy_target: str = "docker",
    frontend: Optional[str] = None,
) -> Dict[str, Any]:
    """Regenerate CI config for an existing project.

    If ci_provider is None, detects the current provider and regenerates.
    If ci_provider is given, switches to that provider (removes old config).

    Returns dict with 'provider', 'file', 'warnings', and optionally
    'removed' (old config files removed when switching).
    """
    root = Path(project_dir)
    name = root.name

    # Try to read name from cup.toml if it exists
    manifest_path = root / "cup.toml"
    if manifest_path.exists():
        text = manifest_path.read_text()
        for line in text.splitlines():
            if line.strip().startswith("name"):
                parts = line.split("=", 1)
                if len(parts) == 2:
                    name = parts[1].strip().strip('"').strip("'")
                    break

    existing = detect_ci(project_dir)
    removed: List[str] = []

    if ci_provider is None:
        # Regenerate existing
        if not existing:
            raise InitError("No CI config detected. Use --provider to specify one.")
        ci_provider = existing[0]["provider"]
    else:
        # Validate
        if ci_provider not in _CI_PROVIDERS:
            available = ", ".join(_CI_PROVIDERS.keys())
            raise InitError(
                f"Unknown CI provider '{ci_provider}'. Available: {available}"
            )
        # Remove old configs when switching
        for entry in existing:
            old_path = Path(entry["path"])
            if old_path.exists():
                old_path.unlink()
                removed.append(entry["path"])

    renderer, ci_rel_dir, ci_filename = _CI_PROVIDERS[ci_provider]
    ci_dir = root / ci_rel_dir
    ci_dir.mkdir(parents=True, exist_ok=True)
    ci_path = ci_dir / ci_filename
    ci_path.write_text(renderer(name, frontend, deploy_target))

    warnings = validate_ci_deploy([ci_provider], deploy_target)

    result: Dict[str, Any] = {
        "provider": ci_provider,
        "file": str(ci_path),
        "warnings": warnings,
    }
    if removed:
        result["removed"] = removed
    return result


# ── CD Step Rendering ────────────────────────────────────────────────


def _github_cd_steps(name: str, deploy_target: str) -> List[str]:
    """Return GitHub Actions YAML lines for a deploy job."""
    cmd = _CD_COMMANDS.get(deploy_target, "")
    if not cmd:
        return []
    cmd = cmd.replace("{name}", name)
    lines = [
        "",
        "  deploy:",
        "    needs: test",
        "    runs-on: ubuntu-latest",
        "    if: github.ref == 'refs/heads/main' && github.event_name == 'push'",
        "    steps:",
        "      - uses: actions/checkout@v4",
        f"      - run: {cmd}",
    ]
    return lines


def _gitlab_cd_steps(name: str, deploy_target: str) -> List[str]:
    cmd = _CD_COMMANDS.get(deploy_target, "")
    if not cmd:
        return []
    cmd = cmd.replace("{name}", name)
    return [
        "",
        "deploy:",
        "  stage: deploy",
        "  image: python:3.12",
        "  script:",
        f"    - {cmd}",
        "  only:",
        "    - main",
    ]


def _azure_cd_steps(name: str, deploy_target: str) -> List[str]:
    cmd = _CD_COMMANDS.get(deploy_target, "")
    if not cmd:
        return []
    cmd = cmd.replace("{name}", name)
    return [
        "",
        "  - script: " + cmd,
        "    displayName: Deploy to " + deploy_target,
        "    condition: and(succeeded(), eq(variables['Build.SourceBranch'], 'refs/heads/main'))",
    ]


def _bitbucket_cd_steps(name: str, deploy_target: str) -> List[str]:
    cmd = _CD_COMMANDS.get(deploy_target, "")
    if not cmd:
        return []
    cmd = cmd.replace("{name}", name)
    return [
        "",
        "  branches:",
        "    main:",
        "      - step:",
        "          name: Deploy",
        "          deployment: production",
        "          script:",
        f"            - {cmd}",
    ]


def _circleci_cd_steps(name: str, deploy_target: str) -> List[str]:
    cmd = _CD_COMMANDS.get(deploy_target, "")
    if not cmd:
        return []
    cmd = cmd.replace("{name}", name)
    return [
        "",
        "  deploy:",
        "    docker:",
        "      - image: cimg/python:3.12",
        "    steps:",
        "      - checkout",
        "      - run:",
        "          name: Deploy to " + deploy_target,
        f"          command: {cmd}",
    ]


def _jenkins_cd_steps(name: str, deploy_target: str) -> List[str]:
    cmd = _CD_COMMANDS.get(deploy_target, "")
    if not cmd:
        return []
    cmd = cmd.replace("{name}", name)
    return [
        "",
        "        stage('Deploy') {",
        "            when { branch 'main' }",
        "            steps {",
        f"                sh '{cmd}'",
        "            }",
        "        }",
    ]


def _generic_cd_steps(name: str, deploy_target: str) -> List[str]:
    """Fallback CD steps — returns the raw deploy command as a comment."""
    cmd = _CD_COMMANDS.get(deploy_target, "")
    if not cmd:
        return []
    cmd = cmd.replace("{name}", name)
    return [f"# Deploy: {cmd}"]


# Map CI providers to their CD step generators
_CD_RENDERERS = {
    "github": _github_cd_steps,
    "gitlab": _gitlab_cd_steps,
    "azure-devops": _azure_cd_steps,
    "bitbucket": _bitbucket_cd_steps,
    "circleci": _circleci_cd_steps,
    "jenkins": _jenkins_cd_steps,
}


# ── CI Provider Registry ────────────────────────────────────────────

# Maps ci_provider key → (renderer_func, relative_dir, filename)
# The dispatcher is populated after the renderer functions are defined.

_CI_PROVIDERS: Dict[str, tuple] = {}  # filled at module bottom


def _render_github_ci(name: str, frontend: Optional[str] = None, deploy_target: str = "docker") -> str:
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
    lines.extend(_github_cd_steps(name, deploy_target))
    return "\n".join(lines) + "\n"


# Keep the old name as an alias for backward compatibility
_render_ci_workflow = _render_github_ci


def _render_gitlab_ci(name: str, frontend: Optional[str] = None, deploy_target: str = "docker") -> str:
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
    cd = _gitlab_cd_steps(name, deploy_target)
    if cd:
        # Add deploy stage to stages list
        lines[3] = "  - test"
        lines.insert(4, "  - deploy")
        lines.extend(cd)
    return "\n".join(lines) + "\n"


def _render_azure_pipelines(name: str, frontend: Optional[str] = None, deploy_target: str = "docker") -> str:
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
    lines.extend(_azure_cd_steps(name, deploy_target))
    return "\n".join(lines) + "\n"


def _render_bitbucket_pipelines(name: str, frontend: Optional[str] = None, deploy_target: str = "docker") -> str:
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

    lines.extend(_bitbucket_cd_steps(name, deploy_target))
    return "\n".join(lines) + "\n"


def _render_circleci_config(name: str, frontend: Optional[str] = None, deploy_target: str = "docker") -> str:
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
    cd = _circleci_cd_steps(name, deploy_target)
    if cd:
        lines.extend(cd)
        # Add deploy job to workflow
        lines.extend([
            "      - deploy:",
            "          requires:",
            "            - test",
            "          filters:",
            "            branches:",
            "              only: main",
        ])
    return "\n".join(lines) + "\n"


def _render_jenkins(name: str, frontend: Optional[str] = None, deploy_target: str = "docker") -> str:
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
    # Insert deploy stage before closing braces
    cd = _jenkins_cd_steps(name, deploy_target)
    if cd:
        # Insert before the last two lines ("    }" and "}")
        lines[-2:-2] = cd
    return "\n".join(lines) + "\n"


def _render_forgejo_ci(name: str, frontend: Optional[str] = None, deploy_target: str = "docker") -> str:
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
    lines.extend(_github_cd_steps(name, deploy_target))
    return "\n".join(lines) + "\n"


def _render_gitea_ci(name: str, frontend: Optional[str] = None, deploy_target: str = "docker") -> str:
    # Gitea Actions uses the same syntax as Forgejo/GitHub Actions
    return _render_forgejo_ci(name, frontend, deploy_target)


def _render_buildkite(name: str, frontend: Optional[str] = None, deploy_target: str = "docker") -> str:
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

    cd_cmd = _CD_COMMANDS.get(deploy_target, "")
    if cd_cmd:
        cd_cmd = cd_cmd.replace("{name}", name)
        lines.extend([
            "  - label: \":rocket: Deploy\"",
            "    command:",
            f"      - {cd_cmd}",
            "    branches: main",
            "",
        ])
    return "\n".join(lines) + "\n"


def _render_drone(name: str, frontend: Optional[str] = None, deploy_target: str = "docker") -> str:
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

    cd_cmd = _CD_COMMANDS.get(deploy_target, "")
    if cd_cmd:
        cd_cmd = cd_cmd.replace("{name}", name)
        lines.extend([
            f"  - name: deploy",
            "    image: python:3.12",
            "    commands:",
            f"      - {cd_cmd}",
            "    when:",
            "      branch: main",
            "",
        ])
    return "\n".join(lines) + "\n"


def _render_woodpecker(name: str, frontend: Optional[str] = None, deploy_target: str = "docker") -> str:
    # Woodpecker uses the same YAML syntax as Drone
    return _render_drone(name, frontend, deploy_target)


def _render_travis(name: str, frontend: Optional[str] = None, deploy_target: str = "docker") -> str:
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
    cd_cmd = _CD_COMMANDS.get(deploy_target, "")
    if cd_cmd:
        cd_cmd = cd_cmd.replace("{name}", name)
        lines.extend([
            "",
            "after_success:",
            f"  - {cd_cmd}",
        ])
    return "\n".join(lines) + "\n"


def _render_aws_codebuild(name: str, frontend: Optional[str] = None, deploy_target: str = "docker") -> str:
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
    cd_cmd = _CD_COMMANDS.get(deploy_target, "")
    if cd_cmd:
        cd_cmd = cd_cmd.replace("{name}", name)
        lines.extend([
            "  post_build:",
            "    commands:",
            f"      - {cd_cmd}",
        ])
    return "\n".join(lines) + "\n"


def _render_cloudbuild(name: str, frontend: Optional[str] = None, deploy_target: str = "docker") -> str:
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

    cd_cmd = _CD_COMMANDS.get(deploy_target, "")
    if cd_cmd:
        cd_cmd = cd_cmd.replace("{name}", name)
        lines.extend([
            f"  - name: python:3.12",
            "    entrypoint: bash",
            "    args:",
            "      - -c",
            f"      - {cd_cmd}",
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
