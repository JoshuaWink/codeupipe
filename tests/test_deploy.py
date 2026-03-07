"""
Tests for codeupipe.deploy — Ring 7a: Accelerate.

Covers:
- DeployTarget / DeployAdapter protocol
- DockerAdapter (validate, generate, mode detection, deploy)
- Adapter discovery (find_adapters)
- Manifest parser (load_manifest, ManifestError)
- Recipe engine (resolve_recipe, list_recipes, RecipeError)
- Init scaffolding (init_project, list_templates, InitError)
- CLI commands: cup deploy, cup recipe, cup init
"""

import json
import sys
from pathlib import Path

import pytest


# ── DeployTarget / DeployAdapter ────────────────────────────────────

class TestDeployTarget:
    """Tests for the DeployTarget dataclass."""

    def test_basic_creation(self):
        from codeupipe.deploy.adapter import DeployTarget
        t = DeployTarget(name="aws", description="AWS Lambda", requires=["boto3"])
        assert t.name == "aws"
        assert t.description == "AWS Lambda"
        assert t.requires == ["boto3"]

    def test_default_requires(self):
        from codeupipe.deploy.adapter import DeployTarget
        t = DeployTarget(name="local", description="Local")
        assert t.requires == []

    def test_abc_cannot_instantiate(self):
        from codeupipe.deploy.adapter import DeployAdapter
        with pytest.raises(TypeError):
            DeployAdapter()


# ── DockerAdapter ───────────────────────────────────────────────────

class TestDockerAdapter:
    """Tests for the built-in DockerAdapter."""

    @pytest.fixture
    def adapter(self):
        from codeupipe.deploy.docker import DockerAdapter
        return DockerAdapter()

    @pytest.fixture
    def valid_config(self):
        return {
            "pipeline": {
                "name": "test-pipeline",
                "steps": [
                    {"name": "Step1", "type": "filter"},
                    {"name": "Step2", "type": "filter"},
                ],
            }
        }

    @pytest.fixture
    def stream_config(self):
        return {
            "pipeline": {
                "name": "stream-pipeline",
                "steps": [
                    {"name": "Ingest", "type": "stream-filter"},
                ],
            }
        }

    def test_target_metadata(self, adapter):
        target = adapter.target()
        assert target.name == "docker"
        assert "Docker" in target.description or "container" in target.description.lower()
        assert target.requires == []

    def test_validate_valid_config(self, adapter, valid_config):
        issues = adapter.validate(valid_config)
        assert issues == []

    def test_validate_missing_pipeline(self, adapter):
        issues = adapter.validate({"not_pipeline": {}})
        assert len(issues) == 1
        assert "pipeline" in issues[0].lower()

    def test_validate_missing_steps(self, adapter):
        issues = adapter.validate({"pipeline": {"name": "x"}})
        assert len(issues) == 1
        assert "steps" in issues[0].lower()

    def test_generate_creates_artifacts(self, adapter, valid_config, tmp_path):
        files = adapter.generate(valid_config, tmp_path / "out")
        assert len(files) == 4
        names = [f.name for f in files]
        assert "pipeline.json" in names
        assert "entrypoint.py" in names
        assert "requirements.txt" in names
        assert "Dockerfile" in names

    def test_generate_pipeline_json_matches(self, adapter, valid_config, tmp_path):
        out = tmp_path / "out"
        adapter.generate(valid_config, out)
        written = json.loads((out / "pipeline.json").read_text())
        assert written == valid_config

    def test_generate_http_mode_entrypoint(self, adapter, valid_config, tmp_path):
        out = tmp_path / "out"
        adapter.generate(valid_config, out, mode="http", port=9999)
        ep = (out / "entrypoint.py").read_text()
        assert "HTTPServer" in ep
        assert "9999" in ep

    def test_generate_worker_mode_entrypoint(self, adapter, valid_config, tmp_path):
        out = tmp_path / "out"
        adapter.generate(valid_config, out, mode="worker")
        ep = (out / "entrypoint.py").read_text()
        assert "stdin" in ep
        assert "worker" in ep.lower()

    def test_generate_cli_mode_entrypoint(self, adapter, valid_config, tmp_path):
        out = tmp_path / "out"
        adapter.generate(valid_config, out, mode="cli")
        ep = (out / "entrypoint.py").read_text()
        assert "argv" in ep

    def test_generate_dockerfile_http_expose(self, adapter, valid_config, tmp_path):
        out = tmp_path / "out"
        adapter.generate(valid_config, out, mode="http", port=8080)
        df = (out / "Dockerfile").read_text()
        assert "EXPOSE 8080" in df

    def test_generate_dockerfile_worker_no_expose(self, adapter, valid_config, tmp_path):
        out = tmp_path / "out"
        adapter.generate(valid_config, out, mode="worker")
        df = (out / "Dockerfile").read_text()
        assert "EXPOSE" not in df

    def test_generate_requirements(self, adapter, tmp_path):
        config = {
            "pipeline": {"name": "x", "steps": [{"name": "A", "type": "filter"}]},
            "dependencies": {"boto3": ">=1.28", "requests": ""},
        }
        out = tmp_path / "out"
        adapter.generate(config, out)
        reqs = (out / "requirements.txt").read_text()
        assert "codeupipe" in reqs
        assert "boto3>=1.28" in reqs

    def test_detect_mode_http_default(self, adapter, valid_config):
        assert adapter._detect_mode(valid_config) == "http"

    def test_detect_mode_stream_worker(self, adapter, stream_config):
        assert adapter._detect_mode(stream_config) == "worker"

    def test_detect_mode_schedule_worker(self, adapter):
        config = {"pipeline": {"name": "x", "steps": [], "schedule": "0 * * * *"}}
        assert adapter._detect_mode(config) == "worker"

    def test_deploy_dry_run(self, adapter, tmp_path):
        result = adapter.deploy(tmp_path, dry_run=True)
        assert "dry-run" in result.lower()

    def test_deploy_real(self, adapter, tmp_path):
        result = adapter.deploy(tmp_path)
        assert "docker build" in result.lower()

    def test_generate_creates_output_dir(self, adapter, valid_config, tmp_path):
        out = tmp_path / "deeply" / "nested" / "dir"
        files = adapter.generate(valid_config, out)
        assert out.exists()
        assert len(files) == 4


# ── Adapter Discovery ───────────────────────────────────────────────

class TestAdapterDiscovery:
    """Tests for find_adapters()."""

    def test_always_includes_docker(self):
        from codeupipe.deploy.discovery import find_adapters
        adapters = find_adapters()
        assert "docker" in adapters

    def test_docker_adapter_type(self):
        from codeupipe.deploy.discovery import find_adapters
        from codeupipe.deploy.docker import DockerAdapter
        adapters = find_adapters()
        assert isinstance(adapters["docker"], DockerAdapter)

    def test_returns_dict(self):
        from codeupipe.deploy.discovery import find_adapters
        result = find_adapters()
        assert isinstance(result, dict)


# ── Manifest Parser ─────────────────────────────────────────────────

class TestManifest:
    """Tests for cup.toml manifest parsing."""

    def test_load_json_manifest(self, tmp_path):
        from codeupipe.deploy.manifest import load_manifest
        manifest = {
            "project": {"name": "test-app", "version": "1.0.0"},
            "deploy": {"target": "docker"},
        }
        path = tmp_path / "cup.json"
        path.write_text(json.dumps(manifest))
        result = load_manifest(str(path))
        assert result["project"]["name"] == "test-app"

    def test_load_manifest_missing_file(self):
        from codeupipe.deploy.manifest import load_manifest
        with pytest.raises(FileNotFoundError):
            load_manifest("/nonexistent/cup.toml")

    def test_load_manifest_missing_project(self, tmp_path):
        from codeupipe.deploy.manifest import load_manifest, ManifestError
        path = tmp_path / "cup.json"
        path.write_text(json.dumps({"deploy": {}}))
        with pytest.raises(ManifestError, match="project"):
            load_manifest(str(path))

    def test_load_manifest_missing_name(self, tmp_path):
        from codeupipe.deploy.manifest import load_manifest, ManifestError
        path = tmp_path / "cup.json"
        path.write_text(json.dumps({"project": {"version": "1.0"}}))
        with pytest.raises(ManifestError, match="name"):
            load_manifest(str(path))

    def test_load_manifest_unsupported_format(self, tmp_path):
        from codeupipe.deploy.manifest import load_manifest, ManifestError
        path = tmp_path / "cup.yaml"
        path.write_text("name: test")
        with pytest.raises(ManifestError, match="Unsupported"):
            load_manifest(str(path))

    @pytest.mark.skipif(sys.version_info < (3, 11), reason="tomllib requires 3.11+")
    def test_load_toml_manifest(self, tmp_path):
        from codeupipe.deploy.manifest import load_manifest
        toml_content = '[project]\nname = "my-app"\n\n[deploy]\ntarget = "docker"\n'
        path = tmp_path / "cup.toml"
        path.write_text(toml_content)
        result = load_manifest(str(path))
        assert result["project"]["name"] == "my-app"


# ── Recipe Engine ───────────────────────────────────────────────────

class TestRecipeEngine:
    """Tests for recipe resolution and listing."""

    def test_list_recipes_returns_list(self):
        from codeupipe.deploy.recipe import list_recipes
        recipes = list_recipes()
        assert isinstance(recipes, list)
        assert len(recipes) > 0

    def test_list_recipes_has_expected_recipes(self):
        from codeupipe.deploy.recipe import list_recipes
        recipes = list_recipes()
        names = [r["name"] for r in recipes]
        assert "saas-signup" in names
        assert "api-crud" in names
        assert "etl" in names
        assert "ai-chat" in names
        assert "webhook-handler" in names

    def test_list_recipes_structure(self):
        from codeupipe.deploy.recipe import list_recipes
        recipes = list_recipes()
        for r in recipes:
            assert "name" in r
            assert "description" in r

    def test_resolve_recipe_substitution(self):
        from codeupipe.deploy.recipe import resolve_recipe
        resolved, deps = resolve_recipe("api-crud", {
            "auth_provider": "jwt",
            "db_provider": "postgres",
        })
        text = json.dumps(resolved)
        assert "jwt" in text
        assert "postgres" in text
        assert "${" not in text

    def test_resolve_recipe_returns_pipeline(self):
        from codeupipe.deploy.recipe import resolve_recipe
        resolved, _ = resolve_recipe("ai-chat", {"ai_provider": "openai"})
        assert "pipeline" in resolved
        assert "steps" in resolved["pipeline"]

    def test_resolve_recipe_strips_meta(self):
        from codeupipe.deploy.recipe import resolve_recipe
        resolved, _ = resolve_recipe("ai-chat", {"ai_provider": "openai"})
        assert "recipe" not in resolved

    def test_resolve_recipe_missing_variables(self):
        from codeupipe.deploy.recipe import resolve_recipe, RecipeError
        with pytest.raises(RecipeError, match="requires variables"):
            resolve_recipe("api-crud", {})

    def test_resolve_recipe_partial_variables(self):
        from codeupipe.deploy.recipe import resolve_recipe, RecipeError
        with pytest.raises(RecipeError, match="requires variables"):
            resolve_recipe("api-crud", {"auth_provider": "jwt"})

    def test_resolve_recipe_unknown_recipe(self):
        from codeupipe.deploy.recipe import resolve_recipe, RecipeError
        with pytest.raises(RecipeError, match="not found"):
            resolve_recipe("nonexistent-recipe", {})

    def test_resolve_recipe_dependencies(self):
        from codeupipe.deploy.recipe import resolve_recipe
        _, deps = resolve_recipe("saas-signup", {
            "auth_provider": "Clerk",
            "email_provider": "SendGrid",
            "payment_provider": "Stripe",
        })
        # Dependencies should include some codeupipe-* packages
        assert isinstance(deps, list)


# ── Init Scaffolding ────────────────────────────────────────────────

class TestInitProject:
    """Tests for cup init project scaffolding."""

    def test_list_templates(self):
        from codeupipe.deploy.init import list_templates
        templates = list_templates()
        assert len(templates) > 0
        names = [t["name"] for t in templates]
        assert "saas" in names
        assert "api" in names
        assert "etl" in names
        assert "chatbot" in names

    def test_init_creates_project(self, tmp_path):
        from codeupipe.deploy.init import init_project
        result = init_project("api", "my-api", str(tmp_path / "my-api"))
        assert result["project_dir"] == str(tmp_path / "my-api")
        assert len(result["files"]) > 0

    def test_init_creates_expected_files(self, tmp_path):
        from codeupipe.deploy.init import init_project
        result = init_project("api", "my-api", str(tmp_path / "my-api"))
        files = result["files"]
        filenames = [Path(f).name for f in files]
        assert "cup.toml" in filenames
        assert "pyproject.toml" in filenames
        assert "README.md" in filenames
        assert "ci.yml" in filenames

    def test_init_cup_toml_valid(self, tmp_path):
        from codeupipe.deploy.init import init_project
        init_project("api", "my-api", str(tmp_path / "my-api"))
        manifest_text = (tmp_path / "my-api" / "cup.toml").read_text()
        assert 'name = "my-api"' in manifest_text
        assert 'target = "docker"' in manifest_text

    def test_init_creates_tests_dir(self, tmp_path):
        from codeupipe.deploy.init import init_project
        init_project("etl", "my-etl", str(tmp_path / "my-etl"))
        assert (tmp_path / "my-etl" / "tests").is_dir()
        assert (tmp_path / "my-etl" / "tests" / "__init__.py").exists()

    def test_init_creates_filters_dir(self, tmp_path):
        from codeupipe.deploy.init import init_project
        init_project("chatbot", "my-bot", str(tmp_path / "my-bot"))
        assert (tmp_path / "my-bot" / "filters").is_dir()
        assert (tmp_path / "my-bot" / "filters" / "__init__.py").exists()

    def test_init_creates_github_ci(self, tmp_path):
        from codeupipe.deploy.init import init_project
        init_project("saas", "my-saas", str(tmp_path / "my-saas"))
        ci_path = tmp_path / "my-saas" / ".github" / "workflows" / "ci.yml"
        assert ci_path.exists()
        assert "pytest" in ci_path.read_text()

    def test_init_with_options(self, tmp_path):
        from codeupipe.deploy.init import init_project
        result = init_project(
            "api", "my-api", str(tmp_path / "my-api"),
            options={"auth": "jwt", "db": "postgres"},
        )
        manifest_text = (tmp_path / "my-api" / "cup.toml").read_text()
        assert "jwt" in manifest_text
        assert "postgres" in manifest_text

    def test_init_unknown_template(self, tmp_path):
        from codeupipe.deploy.init import init_project, InitError
        with pytest.raises(InitError, match="Unknown template"):
            init_project("invalid", "x", str(tmp_path / "x"))

    def test_init_existing_directory(self, tmp_path):
        from codeupipe.deploy.init import init_project, InitError
        existing = tmp_path / "exists"
        existing.mkdir()
        with pytest.raises(InitError, match="already exists"):
            init_project("api", "exists", str(existing))

    def test_init_readme_content(self, tmp_path):
        from codeupipe.deploy.init import init_project
        init_project("etl", "data-pipe", str(tmp_path / "data-pipe"))
        readme = (tmp_path / "data-pipe" / "README.md").read_text()
        assert "data-pipe" in readme
        assert "etl" in readme


# ── CLI Integration ─────────────────────────────────────────────────

class TestCLIDeploy:
    """Tests for cup deploy CLI command."""

    @pytest.fixture
    def valid_config_file(self, tmp_path):
        config = {
            "pipeline": {
                "name": "test-pipe",
                "steps": [{"name": "A", "type": "filter"}],
            }
        }
        path = tmp_path / "pipeline.json"
        path.write_text(json.dumps(config))
        return str(path)

    def test_deploy_dry_run(self, valid_config_file):
        from codeupipe.cli import main
        result = main(["deploy", "docker", valid_config_file, "--dry-run"])
        assert result == 0

    def test_deploy_generate_artifacts(self, valid_config_file, tmp_path):
        from codeupipe.cli import main
        out = str(tmp_path / "deploy_out")
        result = main(["deploy", "docker", valid_config_file, "--output-dir", out])
        assert result == 0
        assert (Path(out) / "Dockerfile").exists()
        assert (Path(out) / "entrypoint.py").exists()

    def test_deploy_unknown_target(self, valid_config_file):
        from codeupipe.cli import main
        result = main(["deploy", "nonexistent", valid_config_file])
        assert result == 1

    def test_deploy_with_mode_override(self, valid_config_file, tmp_path):
        from codeupipe.cli import main
        out = str(tmp_path / "deploy_out")
        result = main(["deploy", "docker", valid_config_file, "--mode", "worker", "--output-dir", out])
        assert result == 0
        ep = (Path(out) / "entrypoint.py").read_text()
        assert "stdin" in ep


class TestCLIRecipe:
    """Tests for cup recipe CLI command."""

    def test_recipe_list(self):
        from codeupipe.cli import main
        result = main(["recipe", "--list"])
        assert result == 0

    def test_recipe_dry_run(self):
        from codeupipe.cli import main
        result = main([
            "recipe", "ai-chat",
            "--var", "ai_provider=openai",
            "--dry-run",
        ])
        assert result == 0

    def test_recipe_generate(self, tmp_path):
        from codeupipe.cli import main
        out = str(tmp_path / "pipelines")
        result = main([
            "recipe", "ai-chat",
            "--var", "ai_provider=openai",
            "--output-dir", out,
        ])
        assert result == 0
        assert (Path(out) / "ai-chat.json").exists()

    def test_recipe_missing_name(self):
        from codeupipe.cli import main
        result = main(["recipe"])
        assert result == 1

    def test_recipe_unknown_name(self):
        from codeupipe.cli import main
        result = main(["recipe", "nonexistent", "--dry-run"])
        assert result == 1

    def test_recipe_missing_var(self):
        from codeupipe.cli import main
        result = main(["recipe", "api-crud", "--dry-run"])
        assert result == 1


class TestCLIInit:
    """Tests for cup init CLI command."""

    def test_init_list(self):
        from codeupipe.cli import main
        result = main(["init", "--list"])
        assert result == 0

    def test_init_creates_project(self, tmp_path, monkeypatch):
        from codeupipe.cli import main
        monkeypatch.chdir(tmp_path)
        result = main(["init", "api", "test-project"])
        assert result == 0
        assert (tmp_path / "test-project").is_dir()

    def test_init_missing_args(self):
        from codeupipe.cli import main
        result = main(["init", "api"])
        assert result == 1

    def test_init_with_options(self, tmp_path, monkeypatch):
        from codeupipe.cli import main
        monkeypatch.chdir(tmp_path)
        result = main([
            "init", "api", "my-project",
            "--auth", "jwt",
            "--db", "postgres",
        ])
        assert result == 0


# ── Re-exports from codeupipe ──────────────────────────────────────

class TestExports:
    """Verify Ring 7 types are accessible from top-level."""

    def test_deploy_types_accessible(self):
        from codeupipe import (
            DeployTarget, DeployAdapter, DockerAdapter,
            find_adapters, load_manifest, ManifestError,
        )

    def test_recipe_types_accessible(self):
        from codeupipe import resolve_recipe, list_recipes, RecipeError

    def test_init_types_accessible(self):
        from codeupipe import init_project, list_templates, InitError


# ══════════════════════════════════════════════════════════════════════
# Ring 7b — Platform Adapters & Frontend Support
# ══════════════════════════════════════════════════════════════════════


# ── Serverless Handler Wrappers ─────────────────────────────────────

class TestHandlers:
    """Tests for serverless handler rendering functions."""

    def test_render_vercel_handler(self):
        from codeupipe.deploy.handlers import render_vercel_handler
        code = render_vercel_handler("my_pipeline")
        assert "BaseHTTPRequestHandler" in code
        assert "my_pipeline" in code
        assert "do_POST" in code
        assert "do_GET" in code

    def test_render_netlify_handler(self):
        from codeupipe.deploy.handlers import render_netlify_handler
        code = render_netlify_handler("my_pipeline")
        assert "def handler(event, context)" in code
        assert "my_pipeline" in code
        assert "statusCode" in code

    def test_render_lambda_handler(self):
        from codeupipe.deploy.handlers import render_lambda_handler
        code = render_lambda_handler("my_pipeline")
        assert "def handler(event, context)" in code
        assert "my_pipeline" in code
        assert "statusCode" in code

    def test_handler_default_names(self):
        from codeupipe.deploy.handlers import (
            render_vercel_handler,
            render_netlify_handler,
            render_lambda_handler,
        )
        # Default pipeline name should be "pipeline"
        assert "pipeline.json" in render_vercel_handler()
        assert "pipeline.json" in render_netlify_handler()
        assert "pipeline.json" in render_lambda_handler()


# ── VercelAdapter ───────────────────────────────────────────────────

class TestVercelAdapter:
    """Tests for VercelAdapter."""

    @pytest.fixture
    def adapter(self):
        from codeupipe.deploy.vercel import VercelAdapter
        return VercelAdapter()

    @pytest.fixture
    def valid_config(self):
        return {
            "pipeline": {
                "name": "test-pipeline",
                "steps": [{"name": "Step1", "type": "filter"}],
            },
        }

    @pytest.fixture
    def config_with_frontend(self):
        return {
            "pipeline": {
                "name": "test-pipeline",
                "steps": [{"name": "Step1", "type": "filter"}],
            },
            "frontend": {
                "framework": "react",
                "build_command": "npm run build",
                "output_dir": "dist",
            },
        }

    def test_target(self, adapter):
        t = adapter.target()
        assert t.name == "vercel"
        assert "Vercel" in t.description

    def test_validate_ok(self, adapter, valid_config):
        errors = adapter.validate(valid_config)
        assert errors == []

    def test_validate_missing_pipeline(self, adapter):
        errors = adapter.validate({})
        assert any("pipeline" in e.lower() for e in errors)

    def test_generate_minimal(self, adapter, valid_config, tmp_path):
        files = adapter.generate(valid_config, tmp_path)
        assert any("vercel.json" in str(f) for f in files)
        assert any("pipeline.py" in str(f) for f in files)
        assert any("pipeline.json" in str(f) for f in files)

    def test_generate_with_frontend(self, adapter, config_with_frontend, tmp_path):
        files = adapter.generate(config_with_frontend, tmp_path)
        file_names = [str(f) for f in files]
        assert any("vercel.json" in f for f in file_names)
        assert any("package.json" in f for f in file_names)
        assert any("index.html" in f for f in file_names)

    def test_vercel_json_structure(self, adapter, valid_config, tmp_path):
        adapter.generate(valid_config, tmp_path)
        vercel_cfg = json.loads((tmp_path / "vercel.json").read_text())
        assert "routes" in vercel_cfg

    def test_deploy_without_cli(self, adapter, valid_config, tmp_path):
        """deploy() gracefully handles missing vercel CLI."""
        adapter.generate(valid_config, tmp_path)
        result = adapter.deploy(tmp_path)
        # Should return instructions or succeed — no crash
        assert isinstance(result, str)
        assert len(result) > 0


# ── NetlifyAdapter ──────────────────────────────────────────────────

class TestNetlifyAdapter:
    """Tests for NetlifyAdapter."""

    @pytest.fixture
    def adapter(self):
        from codeupipe.deploy.netlify import NetlifyAdapter
        return NetlifyAdapter()

    @pytest.fixture
    def valid_config(self):
        return {
            "pipeline": {
                "name": "test-pipeline",
                "steps": [{"name": "Step1", "type": "filter"}],
            },
        }

    @pytest.fixture
    def config_with_frontend(self):
        return {
            "pipeline": {
                "name": "test-pipeline",
                "steps": [{"name": "Step1", "type": "filter"}],
            },
            "frontend": {
                "framework": "vite",
                "build_command": "npm run build",
                "output_dir": "dist",
            },
        }

    def test_target(self, adapter):
        t = adapter.target()
        assert t.name == "netlify"
        assert "Netlify" in t.description

    def test_validate_ok(self, adapter, valid_config):
        errors = adapter.validate(valid_config)
        assert errors == []

    def test_validate_missing_pipeline(self, adapter):
        errors = adapter.validate({})
        assert any("pipeline" in e.lower() for e in errors)

    def test_generate_minimal(self, adapter, valid_config, tmp_path):
        files = adapter.generate(valid_config, tmp_path)
        assert any("netlify.toml" in str(f) for f in files)
        assert any("pipeline.py" in str(f) for f in files)
        assert any("pipeline.json" in str(f) for f in files)

    def test_generate_with_frontend(self, adapter, config_with_frontend, tmp_path):
        files = adapter.generate(config_with_frontend, tmp_path)
        file_names = [str(f) for f in files]
        assert any("netlify.toml" in f for f in file_names)
        assert any("package.json" in f for f in file_names)
        assert any("index.html" in f for f in file_names)

    def test_netlify_toml_structure(self, adapter, valid_config, tmp_path):
        adapter.generate(valid_config, tmp_path)
        toml_content = (tmp_path / "netlify.toml").read_text()
        assert "[build]" in toml_content
        assert "functions" in toml_content

    def test_deploy_without_cli(self, adapter, valid_config, tmp_path):
        """deploy() gracefully handles missing netlify CLI."""
        adapter.generate(valid_config, tmp_path)
        result = adapter.deploy(tmp_path)
        assert isinstance(result, str)
        assert len(result) > 0


# ── Manifest [frontend] Validation ──────────────────────────────────

class TestManifestFrontend:
    """Tests for [frontend] and [deploy] manifest validation."""

    @pytest.fixture
    def valid_manifest(self, tmp_path):
        content = (
            '[project]\nname = "test"\nversion = "0.1.0"\n\n'
            '[frontend]\nframework = "react"\n\n'
            '[deploy]\ntarget = "vercel"\n\n'
            '[dependencies]\ncodeupipe = ">=0.6.0"\n'
        )
        f = tmp_path / "cup.toml"
        f.write_text(content)
        return f

    def test_valid_frontend_loads(self, valid_manifest):
        from codeupipe.deploy.manifest import load_manifest
        m = load_manifest(valid_manifest)
        assert m["frontend"]["framework"] == "react"

    def test_invalid_frontend_framework(self, tmp_path):
        from codeupipe.deploy.manifest import load_manifest, ManifestError
        content = (
            '[project]\nname = "test"\nversion = "0.1.0"\n\n'
            '[frontend]\nframework = "angular"\n\n'
            '[dependencies]\ncodeupipe = ">=0.6.0"\n'
        )
        f = tmp_path / "cup.toml"
        f.write_text(content)
        with pytest.raises(ManifestError, match="framework"):
            load_manifest(f)

    def test_invalid_deploy_target(self, tmp_path):
        from codeupipe.deploy.manifest import load_manifest, ManifestError
        content = (
            '[project]\nname = "test"\nversion = "0.1.0"\n\n'
            '[deploy]\ntarget = "heroku"\n\n'
            '[dependencies]\ncodeupipe = ">=0.6.0"\n'
        )
        f = tmp_path / "cup.toml"
        f.write_text(content)
        with pytest.raises(ManifestError, match="target"):
            load_manifest(f)


# ── Discovery Registers New Adapters ────────────────────────────────

class TestDiscoveryRing7b:
    """Verify discovery returns all built-in adapters."""

    def test_finds_vercel(self):
        from codeupipe.deploy.discovery import find_adapters
        adapters = find_adapters()
        assert "vercel" in adapters

    def test_finds_netlify(self):
        from codeupipe.deploy.discovery import find_adapters
        adapters = find_adapters()
        assert "netlify" in adapters

    def test_finds_all_three_builtins(self):
        from codeupipe.deploy.discovery import find_adapters
        adapters = find_adapters()
        assert {"docker", "vercel", "netlify"}.issubset(adapters.keys())


# ── Init --frontend Scaffold ────────────────────────────────────────

class TestInitFrontend:
    """Tests for cup init with --frontend."""

    def test_init_with_react_frontend(self, tmp_path, monkeypatch):
        from codeupipe.deploy.init import init_project
        monkeypatch.chdir(tmp_path)
        result = init_project("api", "test-fe-project", frontend="react")
        proj = tmp_path / "test-fe-project"

        assert (proj / "frontend" / "package.json").exists()
        assert (proj / "frontend" / "src" / "App.jsx").exists()
        assert (proj / "frontend" / "vite.config.js").exists()
        assert result["frontend"] == "react"

    def test_init_with_next_frontend(self, tmp_path, monkeypatch):
        from codeupipe.deploy.init import init_project
        monkeypatch.chdir(tmp_path)
        result = init_project("api", "test-next-proj", frontend="next")
        proj = tmp_path / "test-next-proj"

        assert (proj / "frontend" / "package.json").exists()
        assert (proj / "frontend" / "pages" / "index.jsx").exists()
        pkg = json.loads((proj / "frontend" / "package.json").read_text())
        assert "next" in pkg.get("dependencies", {})

    def test_init_frontend_none_no_frontend_dir(self, tmp_path, monkeypatch):
        from codeupipe.deploy.init import init_project
        monkeypatch.chdir(tmp_path)
        init_project("api", "test-no-fe")
        proj = tmp_path / "test-no-fe"
        assert not (proj / "frontend").exists()

    def test_manifest_includes_frontend_section(self, tmp_path, monkeypatch):
        from codeupipe.deploy.init import init_project
        monkeypatch.chdir(tmp_path)
        init_project("api", "test-manifest-fe", frontend="vite", deploy_target="vercel")
        manifest = (tmp_path / "test-manifest-fe" / "cup.toml").read_text()
        assert "[frontend]" in manifest
        assert 'framework = "vite"' in manifest
        assert 'target = "vercel"' in manifest

    def test_ci_workflow_includes_node_for_frontend(self, tmp_path, monkeypatch):
        from codeupipe.deploy.init import init_project
        monkeypatch.chdir(tmp_path)
        init_project("api", "test-ci-fe", frontend="react")
        ci = (tmp_path / "test-ci-fe" / ".github" / "workflows" / "ci.yml").read_text()
        assert "setup-node" in ci
        assert "npm" in ci

    def test_readme_includes_frontend_section(self, tmp_path, monkeypatch):
        from codeupipe.deploy.init import init_project
        monkeypatch.chdir(tmp_path)
        init_project("api", "test-readme-fe", frontend="react", deploy_target="vercel")
        readme = (tmp_path / "test-readme-fe" / "README.md").read_text()
        assert "Frontend" in readme
        assert "vercel" in readme

    def test_cli_init_with_frontend(self, tmp_path, monkeypatch):
        from codeupipe.cli import main
        monkeypatch.chdir(tmp_path)
        result = main(["init", "api", "cli-fe-proj", "--frontend", "react"])
        assert result == 0
        assert (tmp_path / "cli-fe-proj" / "frontend").is_dir()

    def test_cli_deploy_vercel_target(self, tmp_path):
        """cup deploy vercel generates vercel.json."""
        from codeupipe.cli import main
        config_path = tmp_path / "pipe.json"
        config_path.write_text(json.dumps({
            "pipeline": {
                "name": "test",
                "steps": [{"name": "S1", "type": "filter"}],
            },
        }))
        out = str(tmp_path / "vercel_out")
        result = main(["deploy", "vercel", str(config_path), "--output-dir", out])
        assert result == 0
        assert (Path(out) / "vercel.json").exists()

    def test_cli_deploy_netlify_target(self, tmp_path):
        """cup deploy netlify generates netlify.toml."""
        from codeupipe.cli import main
        config_path = tmp_path / "pipe.json"
        config_path.write_text(json.dumps({
            "pipeline": {
                "name": "test",
                "steps": [{"name": "S1", "type": "filter"}],
            },
        }))
        out = str(tmp_path / "netlify_out")
        result = main(["deploy", "netlify", str(config_path), "--output-dir", out])
        assert result == 0
        assert (Path(out) / "netlify.toml").exists()


# ── Exports Ring 7b ─────────────────────────────────────────────────

class TestExportsRing7b:
    """Verify Ring 7b types are accessible from top-level."""

    def test_adapter_exports(self):
        from codeupipe import VercelAdapter, NetlifyAdapter
        assert VercelAdapter is not None
        assert NetlifyAdapter is not None

    def test_handler_exports(self):
        from codeupipe import (
            render_vercel_handler,
            render_netlify_handler,
            render_lambda_handler,
        )
        assert callable(render_vercel_handler)
        assert callable(render_netlify_handler)
        assert callable(render_lambda_handler)
