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


# ── CI Provider Tests ───────────────────────────────────────────────


class TestCIProviders:
    """Tests for multi-platform CI scaffolding."""

    # ── Registry ────────────────────────────────────────────────────

    def test_ci_providers_list(self):
        from codeupipe.deploy.init import CI_PROVIDERS
        assert "github" in CI_PROVIDERS
        assert "gitlab" in CI_PROVIDERS
        assert "azure-devops" in CI_PROVIDERS
        assert "bitbucket" in CI_PROVIDERS
        assert "circleci" in CI_PROVIDERS

    def test_ci_providers_export(self):
        from codeupipe.deploy import CI_PROVIDERS
        assert len(CI_PROVIDERS) == 14

    # ── Default (GitHub) unchanged ──────────────────────────────────

    def test_default_is_github(self, tmp_path):
        from codeupipe.deploy.init import init_project
        init_project("api", "default-ci", str(tmp_path / "default-ci"))
        ci = tmp_path / "default-ci" / ".github" / "workflows" / "ci.yml"
        assert ci.exists()
        text = ci.read_text()
        assert "actions/checkout" in text
        assert "pytest" in text

    # ── GitHub ──────────────────────────────────────────────────────

    def test_github_ci_content(self, tmp_path):
        from codeupipe.deploy.init import init_project
        init_project("api", "gh-proj", str(tmp_path / "gh-proj"), ci_provider="github")
        ci = tmp_path / "gh-proj" / ".github" / "workflows" / "ci.yml"
        assert ci.exists()
        text = ci.read_text()
        assert "actions/checkout@v4" in text
        assert "actions/setup-python@v5" in text
        assert "3.9" in text
        assert "3.13" in text

    def test_github_ci_with_frontend(self, tmp_path):
        from codeupipe.deploy.init import init_project
        init_project("api", "gh-fe", str(tmp_path / "gh-fe"), ci_provider="github", frontend="react")
        ci = (tmp_path / "gh-fe" / ".github" / "workflows" / "ci.yml").read_text()
        assert "setup-node" in ci
        assert "npm ci" in ci

    # ── GitLab ──────────────────────────────────────────────────────

    def test_gitlab_ci_file_location(self, tmp_path):
        from codeupipe.deploy.init import init_project
        init_project("api", "gl-proj", str(tmp_path / "gl-proj"), ci_provider="gitlab")
        ci = tmp_path / "gl-proj" / ".gitlab-ci.yml"
        assert ci.exists()

    def test_gitlab_ci_content(self, tmp_path):
        from codeupipe.deploy.init import init_project
        init_project("api", "gl-proj2", str(tmp_path / "gl-proj2"), ci_provider="gitlab")
        text = (tmp_path / "gl-proj2" / ".gitlab-ci.yml").read_text()
        assert "stages:" in text
        assert "pytest" in text
        assert "3.9" in text
        assert "3.13" in text

    def test_gitlab_ci_with_frontend(self, tmp_path):
        from codeupipe.deploy.init import init_project
        init_project("api", "gl-fe", str(tmp_path / "gl-fe"), ci_provider="gitlab", frontend="react")
        text = (tmp_path / "gl-fe" / ".gitlab-ci.yml").read_text()
        assert "npm ci" in text

    def test_gitlab_no_github_dir(self, tmp_path):
        from codeupipe.deploy.init import init_project
        init_project("api", "gl-no-gh", str(tmp_path / "gl-no-gh"), ci_provider="gitlab")
        assert not (tmp_path / "gl-no-gh" / ".github").exists()

    # ── Azure DevOps ────────────────────────────────────────────────

    def test_azure_pipelines_file_location(self, tmp_path):
        from codeupipe.deploy.init import init_project
        init_project("api", "ado-proj", str(tmp_path / "ado-proj"), ci_provider="azure-devops")
        ci = tmp_path / "ado-proj" / "azure-pipelines.yml"
        assert ci.exists()

    def test_azure_pipelines_content(self, tmp_path):
        from codeupipe.deploy.init import init_project
        init_project("api", "ado-proj2", str(tmp_path / "ado-proj2"), ci_provider="azure-devops")
        text = (tmp_path / "ado-proj2" / "azure-pipelines.yml").read_text()
        assert "vmImage: ubuntu-latest" in text
        assert "UsePythonVersion@0" in text
        assert "pytest" in text
        assert "3.9" in text
        assert "3.13" in text

    def test_azure_pipelines_with_frontend(self, tmp_path):
        from codeupipe.deploy.init import init_project
        init_project("api", "ado-fe", str(tmp_path / "ado-fe"), ci_provider="azure-devops", frontend="react")
        text = (tmp_path / "ado-fe" / "azure-pipelines.yml").read_text()
        assert "UseNode@1" in text
        assert "npm ci" in text

    def test_azure_no_github_dir(self, tmp_path):
        from codeupipe.deploy.init import init_project
        init_project("api", "ado-no-gh", str(tmp_path / "ado-no-gh"), ci_provider="azure-devops")
        assert not (tmp_path / "ado-no-gh" / ".github").exists()

    # ── Bitbucket ───────────────────────────────────────────────────

    def test_bitbucket_file_location(self, tmp_path):
        from codeupipe.deploy.init import init_project
        init_project("api", "bb-proj", str(tmp_path / "bb-proj"), ci_provider="bitbucket")
        ci = tmp_path / "bb-proj" / "bitbucket-pipelines.yml"
        assert ci.exists()

    def test_bitbucket_content(self, tmp_path):
        from codeupipe.deploy.init import init_project
        init_project("api", "bb-proj2", str(tmp_path / "bb-proj2"), ci_provider="bitbucket")
        text = (tmp_path / "bb-proj2" / "bitbucket-pipelines.yml").read_text()
        assert "pipelines:" in text
        assert "parallel:" in text
        assert "pytest" in text
        assert "3.9" in text
        assert "3.13" in text

    def test_bitbucket_with_frontend(self, tmp_path):
        from codeupipe.deploy.init import init_project
        init_project("api", "bb-fe", str(tmp_path / "bb-fe"), ci_provider="bitbucket", frontend="react")
        text = (tmp_path / "bb-fe" / "bitbucket-pipelines.yml").read_text()
        assert "npm ci" in text

    def test_bitbucket_no_github_dir(self, tmp_path):
        from codeupipe.deploy.init import init_project
        init_project("api", "bb-no-gh", str(tmp_path / "bb-no-gh"), ci_provider="bitbucket")
        assert not (tmp_path / "bb-no-gh" / ".github").exists()

    # ── CircleCI ────────────────────────────────────────────────────

    def test_circleci_file_location(self, tmp_path):
        from codeupipe.deploy.init import init_project
        init_project("api", "cci-proj", str(tmp_path / "cci-proj"), ci_provider="circleci")
        ci = tmp_path / "cci-proj" / ".circleci" / "config.yml"
        assert ci.exists()

    def test_circleci_content(self, tmp_path):
        from codeupipe.deploy.init import init_project
        init_project("api", "cci-proj2", str(tmp_path / "cci-proj2"), ci_provider="circleci")
        text = (tmp_path / "cci-proj2" / ".circleci" / "config.yml").read_text()
        assert "version: 2.1" in text
        assert "workflows:" in text
        assert "cimg/python" in text
        assert "pytest" in text
        assert "3.9" in text
        assert "3.13" in text

    def test_circleci_with_frontend(self, tmp_path):
        from codeupipe.deploy.init import init_project
        init_project("api", "cci-fe", str(tmp_path / "cci-fe"), ci_provider="circleci", frontend="react")
        text = (tmp_path / "cci-fe" / ".circleci" / "config.yml").read_text()
        assert "npm ci" in text

    def test_circleci_no_github_dir(self, tmp_path):
        from codeupipe.deploy.init import init_project
        init_project("api", "cci-no-gh", str(tmp_path / "cci-no-gh"), ci_provider="circleci")
        assert not (tmp_path / "cci-no-gh" / ".github").exists()

    # ── Error cases ─────────────────────────────────────────────────

    def test_invalid_ci_provider(self, tmp_path):
        from codeupipe.deploy.init import init_project, InitError
        with pytest.raises(InitError, match="Unknown CI provider"):
            init_project("api", "bad-ci", str(tmp_path / "bad-ci"), ci_provider="teamcity")

    # ── CLI --ci flag ───────────────────────────────────────────────

    def test_cli_init_with_gitlab(self, tmp_path, monkeypatch):
        from codeupipe.cli import main
        monkeypatch.chdir(tmp_path)
        result = main(["init", "api", "cli-gl", "--ci", "gitlab"])
        assert result == 0
        assert (tmp_path / "cli-gl" / ".gitlab-ci.yml").exists()

    def test_cli_init_with_azure_devops(self, tmp_path, monkeypatch):
        from codeupipe.cli import main
        monkeypatch.chdir(tmp_path)
        result = main(["init", "api", "cli-ado", "--ci", "azure-devops"])
        assert result == 0
        assert (tmp_path / "cli-ado" / "azure-pipelines.yml").exists()

    def test_cli_init_with_bitbucket(self, tmp_path, monkeypatch):
        from codeupipe.cli import main
        monkeypatch.chdir(tmp_path)
        result = main(["init", "api", "cli-bb", "--ci", "bitbucket"])
        assert result == 0
        assert (tmp_path / "cli-bb" / "bitbucket-pipelines.yml").exists()

    def test_cli_init_with_circleci(self, tmp_path, monkeypatch):
        from codeupipe.cli import main
        monkeypatch.chdir(tmp_path)
        result = main(["init", "api", "cli-cci", "--ci", "circleci"])
        assert result == 0
        assert (tmp_path / "cli-cci" / ".circleci" / "config.yml").exists()

    def test_cli_default_ci_is_github(self, tmp_path, monkeypatch):
        from codeupipe.cli import main
        monkeypatch.chdir(tmp_path)
        result = main(["init", "api", "cli-default"])
        assert result == 0
        assert (tmp_path / "cli-default" / ".github" / "workflows" / "ci.yml").exists()

    # ── Jenkins ─────────────────────────────────────────────────────

    def test_jenkins_file_location(self, tmp_path):
        from codeupipe.deploy.init import init_project
        init_project("api", "jk-proj", str(tmp_path / "jk-proj"), ci_provider="jenkins")
        assert (tmp_path / "jk-proj" / "Jenkinsfile").exists()

    def test_jenkins_content(self, tmp_path):
        from codeupipe.deploy.init import init_project
        init_project("api", "jk-proj2", str(tmp_path / "jk-proj2"), ci_provider="jenkins")
        text = (tmp_path / "jk-proj2" / "Jenkinsfile").read_text()
        assert "pipeline {" in text
        assert "pytest" in text
        assert "3.9" in text
        assert "3.13" in text

    def test_jenkins_with_frontend(self, tmp_path):
        from codeupipe.deploy.init import init_project
        init_project("api", "jk-fe", str(tmp_path / "jk-fe"), ci_provider="jenkins", frontend="react")
        text = (tmp_path / "jk-fe" / "Jenkinsfile").read_text()
        assert "npm ci" in text

    def test_jenkins_no_github_dir(self, tmp_path):
        from codeupipe.deploy.init import init_project
        init_project("api", "jk-no-gh", str(tmp_path / "jk-no-gh"), ci_provider="jenkins")
        assert not (tmp_path / "jk-no-gh" / ".github").exists()

    # ── Forgejo ─────────────────────────────────────────────────────

    def test_forgejo_file_location(self, tmp_path):
        from codeupipe.deploy.init import init_project
        init_project("api", "fg-proj", str(tmp_path / "fg-proj"), ci_provider="forgejo")
        assert (tmp_path / "fg-proj" / ".forgejo" / "workflows" / "ci.yml").exists()

    def test_forgejo_content(self, tmp_path):
        from codeupipe.deploy.init import init_project
        init_project("api", "fg-proj2", str(tmp_path / "fg-proj2"), ci_provider="forgejo")
        text = (tmp_path / "fg-proj2" / ".forgejo" / "workflows" / "ci.yml").read_text()
        assert "actions/checkout" in text
        assert "pytest" in text
        assert "3.9" in text

    def test_forgejo_with_frontend(self, tmp_path):
        from codeupipe.deploy.init import init_project
        init_project("api", "fg-fe", str(tmp_path / "fg-fe"), ci_provider="forgejo", frontend="react")
        text = (tmp_path / "fg-fe" / ".forgejo" / "workflows" / "ci.yml").read_text()
        assert "setup-node" in text

    def test_forgejo_no_github_dir(self, tmp_path):
        from codeupipe.deploy.init import init_project
        init_project("api", "fg-no-gh", str(tmp_path / "fg-no-gh"), ci_provider="forgejo")
        assert not (tmp_path / "fg-no-gh" / ".github").exists()

    # ── Gitea ───────────────────────────────────────────────────────

    def test_gitea_file_location(self, tmp_path):
        from codeupipe.deploy.init import init_project
        init_project("api", "gt-proj", str(tmp_path / "gt-proj"), ci_provider="gitea")
        assert (tmp_path / "gt-proj" / ".gitea" / "workflows" / "ci.yml").exists()

    def test_gitea_content(self, tmp_path):
        from codeupipe.deploy.init import init_project
        init_project("api", "gt-proj2", str(tmp_path / "gt-proj2"), ci_provider="gitea")
        text = (tmp_path / "gt-proj2" / ".gitea" / "workflows" / "ci.yml").read_text()
        assert "actions/checkout" in text
        assert "pytest" in text

    def test_gitea_no_github_dir(self, tmp_path):
        from codeupipe.deploy.init import init_project
        init_project("api", "gt-no-gh", str(tmp_path / "gt-no-gh"), ci_provider="gitea")
        assert not (tmp_path / "gt-no-gh" / ".github").exists()

    # ── Buildkite ───────────────────────────────────────────────────

    def test_buildkite_file_location(self, tmp_path):
        from codeupipe.deploy.init import init_project
        init_project("api", "bk-proj", str(tmp_path / "bk-proj"), ci_provider="buildkite")
        assert (tmp_path / "bk-proj" / ".buildkite" / "pipeline.yml").exists()

    def test_buildkite_content(self, tmp_path):
        from codeupipe.deploy.init import init_project
        init_project("api", "bk-proj2", str(tmp_path / "bk-proj2"), ci_provider="buildkite")
        text = (tmp_path / "bk-proj2" / ".buildkite" / "pipeline.yml").read_text()
        assert "steps:" in text
        assert "pytest" in text
        assert "3.9" in text
        assert "3.13" in text

    def test_buildkite_with_frontend(self, tmp_path):
        from codeupipe.deploy.init import init_project
        init_project("api", "bk-fe", str(tmp_path / "bk-fe"), ci_provider="buildkite", frontend="react")
        text = (tmp_path / "bk-fe" / ".buildkite" / "pipeline.yml").read_text()
        assert "npm ci" in text
        assert "node:20" in text

    def test_buildkite_no_github_dir(self, tmp_path):
        from codeupipe.deploy.init import init_project
        init_project("api", "bk-no-gh", str(tmp_path / "bk-no-gh"), ci_provider="buildkite")
        assert not (tmp_path / "bk-no-gh" / ".github").exists()

    # ── Drone ───────────────────────────────────────────────────────

    def test_drone_file_location(self, tmp_path):
        from codeupipe.deploy.init import init_project
        init_project("api", "dr-proj", str(tmp_path / "dr-proj"), ci_provider="drone")
        assert (tmp_path / "dr-proj" / ".drone.yml").exists()

    def test_drone_content(self, tmp_path):
        from codeupipe.deploy.init import init_project
        init_project("api", "dr-proj2", str(tmp_path / "dr-proj2"), ci_provider="drone")
        text = (tmp_path / "dr-proj2" / ".drone.yml").read_text()
        assert "kind: pipeline" in text
        assert "pytest" in text
        assert "3.9" in text

    def test_drone_with_frontend(self, tmp_path):
        from codeupipe.deploy.init import init_project
        init_project("api", "dr-fe", str(tmp_path / "dr-fe"), ci_provider="drone", frontend="react")
        text = (tmp_path / "dr-fe" / ".drone.yml").read_text()
        assert "npm ci" in text
        assert "node:20" in text

    def test_drone_no_github_dir(self, tmp_path):
        from codeupipe.deploy.init import init_project
        init_project("api", "dr-no-gh", str(tmp_path / "dr-no-gh"), ci_provider="drone")
        assert not (tmp_path / "dr-no-gh" / ".github").exists()

    # ── Woodpecker ──────────────────────────────────────────────────

    def test_woodpecker_file_location(self, tmp_path):
        from codeupipe.deploy.init import init_project
        init_project("api", "wp-proj", str(tmp_path / "wp-proj"), ci_provider="woodpecker")
        assert (tmp_path / "wp-proj" / ".woodpecker.yml").exists()

    def test_woodpecker_content(self, tmp_path):
        from codeupipe.deploy.init import init_project
        init_project("api", "wp-proj2", str(tmp_path / "wp-proj2"), ci_provider="woodpecker")
        text = (tmp_path / "wp-proj2" / ".woodpecker.yml").read_text()
        assert "kind: pipeline" in text
        assert "pytest" in text

    def test_woodpecker_no_github_dir(self, tmp_path):
        from codeupipe.deploy.init import init_project
        init_project("api", "wp-no-gh", str(tmp_path / "wp-no-gh"), ci_provider="woodpecker")
        assert not (tmp_path / "wp-no-gh" / ".github").exists()

    # ── Travis CI ───────────────────────────────────────────────────

    def test_travis_file_location(self, tmp_path):
        from codeupipe.deploy.init import init_project
        init_project("api", "tv-proj", str(tmp_path / "tv-proj"), ci_provider="travis")
        assert (tmp_path / "tv-proj" / ".travis.yml").exists()

    def test_travis_content(self, tmp_path):
        from codeupipe.deploy.init import init_project
        init_project("api", "tv-proj2", str(tmp_path / "tv-proj2"), ci_provider="travis")
        text = (tmp_path / "tv-proj2" / ".travis.yml").read_text()
        assert "language: python" in text
        assert "pytest" in text
        assert "3.9" in text
        assert "3.13" in text

    def test_travis_with_frontend(self, tmp_path):
        from codeupipe.deploy.init import init_project
        init_project("api", "tv-fe", str(tmp_path / "tv-fe"), ci_provider="travis", frontend="react")
        text = (tmp_path / "tv-fe" / ".travis.yml").read_text()
        assert "npm ci" in text

    def test_travis_no_github_dir(self, tmp_path):
        from codeupipe.deploy.init import init_project
        init_project("api", "tv-no-gh", str(tmp_path / "tv-no-gh"), ci_provider="travis")
        assert not (tmp_path / "tv-no-gh" / ".github").exists()

    # ── AWS CodeBuild ───────────────────────────────────────────────

    def test_aws_codebuild_file_location(self, tmp_path):
        from codeupipe.deploy.init import init_project
        init_project("api", "aws-proj", str(tmp_path / "aws-proj"), ci_provider="aws-codebuild")
        assert (tmp_path / "aws-proj" / "buildspec.yml").exists()

    def test_aws_codebuild_content(self, tmp_path):
        from codeupipe.deploy.init import init_project
        init_project("api", "aws-proj2", str(tmp_path / "aws-proj2"), ci_provider="aws-codebuild")
        text = (tmp_path / "aws-proj2" / "buildspec.yml").read_text()
        assert "version: 0.2" in text
        assert "phases:" in text
        assert "runtime-versions:" in text
        assert "pytest" in text

    def test_aws_codebuild_with_frontend(self, tmp_path):
        from codeupipe.deploy.init import init_project
        init_project("api", "aws-fe", str(tmp_path / "aws-fe"), ci_provider="aws-codebuild", frontend="react")
        text = (tmp_path / "aws-fe" / "buildspec.yml").read_text()
        assert "nodejs: 20" in text
        assert "npm ci" in text

    def test_aws_codebuild_no_github_dir(self, tmp_path):
        from codeupipe.deploy.init import init_project
        init_project("api", "aws-no-gh", str(tmp_path / "aws-no-gh"), ci_provider="aws-codebuild")
        assert not (tmp_path / "aws-no-gh" / ".github").exists()

    # ── Google Cloud Build ──────────────────────────────────────────

    def test_cloudbuild_file_location(self, tmp_path):
        from codeupipe.deploy.init import init_project
        init_project("api", "gcb-proj", str(tmp_path / "gcb-proj"), ci_provider="cloud-build")
        assert (tmp_path / "gcb-proj" / "cloudbuild.yaml").exists()

    def test_cloudbuild_content(self, tmp_path):
        from codeupipe.deploy.init import init_project
        init_project("api", "gcb-proj2", str(tmp_path / "gcb-proj2"), ci_provider="cloud-build")
        text = (tmp_path / "gcb-proj2" / "cloudbuild.yaml").read_text()
        assert "steps:" in text
        assert "pytest" in text
        assert "python:3.9" in text
        assert "python:3.13" in text

    def test_cloudbuild_with_frontend(self, tmp_path):
        from codeupipe.deploy.init import init_project
        init_project("api", "gcb-fe", str(tmp_path / "gcb-fe"), ci_provider="cloud-build", frontend="react")
        text = (tmp_path / "gcb-fe" / "cloudbuild.yaml").read_text()
        assert "node:20" in text
        assert "npm ci" in text

    def test_cloudbuild_no_github_dir(self, tmp_path):
        from codeupipe.deploy.init import init_project
        init_project("api", "gcb-no-gh", str(tmp_path / "gcb-no-gh"), ci_provider="cloud-build")
        assert not (tmp_path / "gcb-no-gh" / ".github").exists()

    # ── Full provider count ─────────────────────────────────────────

    def test_total_ci_providers(self):
        from codeupipe.deploy.init import CI_PROVIDERS
        assert len(CI_PROVIDERS) == 14

    # ── CLI for new providers ───────────────────────────────────────

    def test_cli_init_with_jenkins(self, tmp_path, monkeypatch):
        from codeupipe.cli import main
        monkeypatch.chdir(tmp_path)
        assert main(["init", "api", "cli-jk", "--ci", "jenkins"]) == 0
        assert (tmp_path / "cli-jk" / "Jenkinsfile").exists()

    def test_cli_init_with_forgejo(self, tmp_path, monkeypatch):
        from codeupipe.cli import main
        monkeypatch.chdir(tmp_path)
        assert main(["init", "api", "cli-fg", "--ci", "forgejo"]) == 0
        assert (tmp_path / "cli-fg" / ".forgejo" / "workflows" / "ci.yml").exists()

    def test_cli_init_with_gitea(self, tmp_path, monkeypatch):
        from codeupipe.cli import main
        monkeypatch.chdir(tmp_path)
        assert main(["init", "api", "cli-gt", "--ci", "gitea"]) == 0
        assert (tmp_path / "cli-gt" / ".gitea" / "workflows" / "ci.yml").exists()

    def test_cli_init_with_buildkite(self, tmp_path, monkeypatch):
        from codeupipe.cli import main
        monkeypatch.chdir(tmp_path)
        assert main(["init", "api", "cli-bk", "--ci", "buildkite"]) == 0
        assert (tmp_path / "cli-bk" / ".buildkite" / "pipeline.yml").exists()

    def test_cli_init_with_drone(self, tmp_path, monkeypatch):
        from codeupipe.cli import main
        monkeypatch.chdir(tmp_path)
        assert main(["init", "api", "cli-dr", "--ci", "drone"]) == 0
        assert (tmp_path / "cli-dr" / ".drone.yml").exists()

    def test_cli_init_with_woodpecker(self, tmp_path, monkeypatch):
        from codeupipe.cli import main
        monkeypatch.chdir(tmp_path)
        assert main(["init", "api", "cli-wp", "--ci", "woodpecker"]) == 0
        assert (tmp_path / "cli-wp" / ".woodpecker.yml").exists()

    def test_cli_init_with_travis(self, tmp_path, monkeypatch):
        from codeupipe.cli import main
        monkeypatch.chdir(tmp_path)
        assert main(["init", "api", "cli-tv", "--ci", "travis"]) == 0
        assert (tmp_path / "cli-tv" / ".travis.yml").exists()

    def test_cli_init_with_aws_codebuild(self, tmp_path, monkeypatch):
        from codeupipe.cli import main
        monkeypatch.chdir(tmp_path)
        assert main(["init", "api", "cli-aws", "--ci", "aws-codebuild"]) == 0
        assert (tmp_path / "cli-aws" / "buildspec.yml").exists()

    def test_cli_init_with_cloud_build(self, tmp_path, monkeypatch):
        from codeupipe.cli import main
        monkeypatch.chdir(tmp_path)
        assert main(["init", "api", "cli-gcb", "--ci", "cloud-build"]) == 0
        assert (tmp_path / "cli-gcb" / "cloudbuild.yaml").exists()


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


# ── Docker Compose Generation ───────────────────────────────────────

class TestDockerCompose:
    """Tests for docker-compose.yml generation in DockerAdapter."""

    @pytest.fixture
    def adapter(self):
        from codeupipe.deploy.docker import DockerAdapter
        return DockerAdapter()

    @pytest.fixture
    def config_with_postgres(self):
        return {
            "project": {"name": "my-app"},
            "pipeline": {
                "name": "test",
                "steps": [{"name": "S1", "type": "filter"}],
            },
            "connectors": {
                "db": {
                    "provider": "postgres",
                    "connection_string_env": "DATABASE_URL",
                },
            },
        }

    @pytest.fixture
    def config_no_connectors(self):
        return {
            "pipeline": {
                "name": "test",
                "steps": [{"name": "S1", "type": "filter"}],
            },
        }

    def test_compose_generated_when_connectors_present(self, adapter, config_with_postgres, tmp_path):
        out = tmp_path / "out"
        files = adapter.generate(config_with_postgres, out)
        names = [f.name for f in files]
        assert "docker-compose.yml" in names

    def test_compose_not_generated_without_connectors(self, adapter, config_no_connectors, tmp_path):
        out = tmp_path / "out"
        files = adapter.generate(config_no_connectors, out)
        names = [f.name for f in files]
        assert "docker-compose.yml" not in names

    def test_compose_contains_postgres_service(self, adapter, config_with_postgres, tmp_path):
        out = tmp_path / "out"
        adapter.generate(config_with_postgres, out)
        compose = (out / "docker-compose.yml").read_text()
        assert "postgres:16-alpine" in compose
        assert "POSTGRES_USER" in compose
        assert "5432" in compose

    def test_compose_wires_database_url(self, adapter, config_with_postgres, tmp_path):
        out = tmp_path / "out"
        adapter.generate(config_with_postgres, out)
        compose = (out / "docker-compose.yml").read_text()
        assert "DATABASE_URL:" in compose
        assert "postgresql://" in compose

    def test_compose_contains_app_service(self, adapter, config_with_postgres, tmp_path):
        out = tmp_path / "out"
        adapter.generate(config_with_postgres, out)
        compose = (out / "docker-compose.yml").read_text()
        assert "my-app:" in compose
        assert "build: ." in compose
        assert "8000:8000" in compose

    def test_compose_has_depends_on(self, adapter, config_with_postgres, tmp_path):
        out = tmp_path / "out"
        adapter.generate(config_with_postgres, out)
        compose = (out / "docker-compose.yml").read_text()
        assert "depends_on:" in compose

    def test_compose_has_volumes(self, adapter, config_with_postgres, tmp_path):
        out = tmp_path / "out"
        adapter.generate(config_with_postgres, out)
        compose = (out / "docker-compose.yml").read_text()
        assert "volumes:" in compose

    def test_compose_generic_connector_passes_env(self, adapter, tmp_path):
        config = {
            "project": {"name": "test"},
            "pipeline": {
                "name": "test",
                "steps": [{"name": "S1", "type": "filter"}],
            },
            "connectors": {
                "gcal": {
                    "provider": "google-calendar",
                    "credentials_env": "GOOGLE_CREDS",
                },
            },
        }
        out = tmp_path / "out"
        adapter.generate(config, out)
        compose = (out / "docker-compose.yml").read_text()
        assert "GOOGLE_CREDS" in compose


# ── RenderAdapter ───────────────────────────────────────────────────

class TestRenderAdapter:
    """Tests for the RenderAdapter — free-tier cloud deploy."""

    @pytest.fixture
    def adapter(self):
        from codeupipe.deploy.render import RenderAdapter
        return RenderAdapter()

    @pytest.fixture
    def valid_config(self):
        return {
            "project": {"name": "test-app"},
            "pipeline": {
                "name": "test",
                "steps": [{"name": "S1", "type": "filter"}],
            },
            "connectors": {
                "db": {
                    "provider": "postgres",
                    "connection_string_env": "DATABASE_URL",
                },
            },
        }

    def test_target_metadata(self, adapter):
        target = adapter.target()
        assert target.name == "render"
        assert "free" in target.description.lower()

    def test_validate_valid_config(self, adapter, valid_config):
        issues = adapter.validate(valid_config)
        assert issues == []

    def test_validate_missing_pipeline(self, adapter):
        issues = adapter.validate({"not_pipeline": {}})
        assert len(issues) == 1

    def test_validate_missing_steps(self, adapter):
        issues = adapter.validate({"pipeline": {"name": "x"}})
        assert len(issues) == 1

    def test_generate_creates_artifacts(self, adapter, valid_config, tmp_path):
        out = tmp_path / "out"
        files = adapter.generate(valid_config, out)
        assert len(files) == 5
        names = [f.name for f in files]
        assert "render.yaml" in names
        assert "Dockerfile" in names
        assert "pipeline.json" in names
        assert "entrypoint.py" in names
        assert "requirements.txt" in names

    def test_render_yaml_has_free_plan(self, adapter, valid_config, tmp_path):
        out = tmp_path / "out"
        adapter.generate(valid_config, out)
        blueprint = (out / "render.yaml").read_text()
        assert "plan: free" in blueprint

    def test_render_yaml_has_database(self, adapter, valid_config, tmp_path):
        out = tmp_path / "out"
        adapter.generate(valid_config, out)
        blueprint = (out / "render.yaml").read_text()
        assert "databases:" in blueprint
        assert "test-app-db" in blueprint

    def test_render_yaml_wires_database_url(self, adapter, valid_config, tmp_path):
        out = tmp_path / "out"
        adapter.generate(valid_config, out)
        blueprint = (out / "render.yaml").read_text()
        assert "DATABASE_URL" in blueprint
        assert "fromDatabase:" in blueprint
        assert "connectionString" in blueprint

    def test_render_yaml_has_web_service(self, adapter, valid_config, tmp_path):
        out = tmp_path / "out"
        adapter.generate(valid_config, out)
        blueprint = (out / "render.yaml").read_text()
        assert "services:" in blueprint
        assert "type: web" in blueprint
        assert "runtime: docker" in blueprint

    def test_render_yaml_generic_connector_env(self, adapter, tmp_path):
        config = {
            "project": {"name": "x"},
            "pipeline": {
                "name": "test",
                "steps": [{"name": "S1", "type": "filter"}],
            },
            "connectors": {
                "gcal": {
                    "provider": "google-calendar",
                    "credentials_env": "GOOGLE_CREDS",
                },
            },
        }
        out = tmp_path / "out"
        adapter.generate(config, out)
        blueprint = (out / "render.yaml").read_text()
        assert "GOOGLE_CREDS" in blueprint
        assert "sync: false" in blueprint

    def test_deploy_dry_run(self, adapter, tmp_path):
        result = adapter.deploy(tmp_path, dry_run=True)
        assert "dry-run" in result.lower()
        assert "render.com" in result.lower() or "render" in result.lower()

    def test_deploy_with_artifacts(self, adapter, valid_config, tmp_path):
        out = tmp_path / "out"
        adapter.generate(valid_config, out)
        result = adapter.deploy(out)
        assert "render.yaml" in result.lower() or "render" in result.lower()
        assert "github" in result.lower()

    def test_entrypoint_reads_port_from_env(self, adapter, valid_config, tmp_path):
        out = tmp_path / "out"
        adapter.generate(valid_config, out)
        ep = (out / "entrypoint.py").read_text()
        assert "PORT" in ep
        assert "os.environ" in ep

    def test_no_connectors_no_databases(self, adapter, tmp_path):
        config = {
            "project": {"name": "simple"},
            "pipeline": {
                "name": "test",
                "steps": [{"name": "S1", "type": "filter"}],
            },
            "connectors": {},
        }
        out = tmp_path / "out"
        adapter.generate(config, out)
        blueprint = (out / "render.yaml").read_text()
        assert "databases:" not in blueprint


# ── Render Discovery + Manifest ─────────────────────────────────────

class TestRenderDiscovery:
    """Verify Render adapter is discovered and manifest accepts 'render' target."""

    def test_render_in_find_adapters(self):
        from codeupipe.deploy import find_adapters
        adapters = find_adapters()
        assert "render" in adapters

    def test_manifest_accepts_render_target(self, tmp_path):
        from codeupipe.deploy.manifest import load_manifest
        toml_content = (
            '[project]\nname = "test"\n\n'
            '[deploy]\ntarget = "render"\n'
        )
        toml_file = tmp_path / "cup.toml"
        toml_file.write_text(toml_content)
        m = load_manifest(str(toml_file))
        assert m["deploy"]["target"] == "render"

    def test_render_export_from_top_level(self):
        from codeupipe import RenderAdapter
        assert RenderAdapter is not None

    def test_render_export_from_deploy(self):
        from codeupipe.deploy import RenderAdapter
        assert RenderAdapter is not None


# ── FlyAdapter ───────────────────────────────────────────────────────

class TestFlyAdapter:
    """Tests for the FlyAdapter — Fly.io edge deployment."""

    @pytest.fixture
    def adapter(self):
        from codeupipe.deploy.fly import FlyAdapter
        return FlyAdapter()

    @pytest.fixture
    def valid_config(self):
        return {
            "project": {"name": "test-app"},
            "pipeline": {
                "name": "test",
                "steps": [{"name": "S1", "type": "filter"}],
            },
            "connectors": {},
        }

    def test_target_metadata(self, adapter):
        target = adapter.target()
        assert target.name == "fly"
        assert "fly.io" in target.description.lower()

    def test_validate_valid_config(self, adapter, valid_config):
        assert adapter.validate(valid_config) == []

    def test_validate_missing_pipeline(self, adapter):
        assert len(adapter.validate({"not_pipeline": {}})) == 1

    def test_generate_creates_artifacts(self, adapter, valid_config, tmp_path):
        out = tmp_path / "out"
        files = adapter.generate(valid_config, out)
        assert len(files) == 5
        names = [f.name for f in files]
        assert "fly.toml" in names
        assert "Dockerfile" in names
        assert "pipeline.json" in names

    def test_fly_toml_has_http_service(self, adapter, valid_config, tmp_path):
        out = tmp_path / "out"
        adapter.generate(valid_config, out)
        content = (out / "fly.toml").read_text()
        assert "[http_service]" in content
        assert "internal_port" in content

    def test_fly_toml_has_app_name(self, adapter, valid_config, tmp_path):
        out = tmp_path / "out"
        adapter.generate(valid_config, out)
        content = (out / "fly.toml").read_text()
        assert 'app = "test-app"' in content

    def test_deploy_dry_run(self, adapter, tmp_path):
        result = adapter.deploy(tmp_path, dry_run=True)
        assert "dry-run" in result.lower()
        assert "fly" in result.lower()

    def test_entrypoint_reads_port(self, adapter, valid_config, tmp_path):
        out = tmp_path / "out"
        adapter.generate(valid_config, out)
        ep = (out / "entrypoint.py").read_text()
        assert "PORT" in ep

    def test_postgres_comment_in_fly_toml(self, adapter, tmp_path):
        config = {
            "project": {"name": "x"},
            "pipeline": {"name": "test", "steps": [{"name": "S1", "type": "filter"}]},
            "connectors": {"db": {"provider": "postgres"}},
        }
        out = tmp_path / "out"
        adapter.generate(config, out)
        content = (out / "fly.toml").read_text()
        assert "postgres" in content.lower()


class TestFlyDiscovery:
    """Verify Fly adapter is discovered and manifest accepts 'fly' target."""

    def test_fly_in_find_adapters(self):
        from codeupipe.deploy import find_adapters
        assert "fly" in find_adapters()

    def test_manifest_accepts_fly_target(self, tmp_path):
        from codeupipe.deploy.manifest import load_manifest
        toml = '[project]\nname = "t"\n\n[deploy]\ntarget = "fly"\n'
        f = tmp_path / "cup.toml"
        f.write_text(toml)
        assert load_manifest(str(f))["deploy"]["target"] == "fly"

    def test_fly_export_top_level(self):
        from codeupipe import FlyAdapter
        assert FlyAdapter is not None

    def test_fly_export_deploy(self):
        from codeupipe.deploy import FlyAdapter
        assert FlyAdapter is not None


# ── RailwayAdapter ───────────────────────────────────────────────────

class TestRailwayAdapter:
    """Tests for the RailwayAdapter — Railway deployment."""

    @pytest.fixture
    def adapter(self):
        from codeupipe.deploy.railway import RailwayAdapter
        return RailwayAdapter()

    @pytest.fixture
    def valid_config(self):
        return {
            "project": {"name": "test-app"},
            "pipeline": {
                "name": "test",
                "steps": [{"name": "S1", "type": "filter"}],
            },
            "connectors": {},
        }

    def test_target_metadata(self, adapter):
        target = adapter.target()
        assert target.name == "railway"
        assert "railway" in target.description.lower()

    def test_validate_valid_config(self, adapter, valid_config):
        assert adapter.validate(valid_config) == []

    def test_validate_missing_pipeline(self, adapter):
        assert len(adapter.validate({"not_pipeline": {}})) == 1

    def test_generate_creates_artifacts(self, adapter, valid_config, tmp_path):
        out = tmp_path / "out"
        files = adapter.generate(valid_config, out)
        assert len(files) == 5
        names = [f.name for f in files]
        assert "railway.json" in names
        assert "Dockerfile" in names

    def test_railway_json_has_builder(self, adapter, valid_config, tmp_path):
        import json
        out = tmp_path / "out"
        adapter.generate(valid_config, out)
        data = json.loads((out / "railway.json").read_text())
        assert data["build"]["builder"] == "DOCKERFILE"

    def test_deploy_dry_run(self, adapter, tmp_path):
        result = adapter.deploy(tmp_path, dry_run=True)
        assert "dry-run" in result.lower()
        assert "railway" in result.lower()

    def test_entrypoint_reads_port(self, adapter, valid_config, tmp_path):
        out = tmp_path / "out"
        adapter.generate(valid_config, out)
        assert "PORT" in (out / "entrypoint.py").read_text()


class TestRailwayDiscovery:

    def test_railway_in_find_adapters(self):
        from codeupipe.deploy import find_adapters
        assert "railway" in find_adapters()

    def test_manifest_accepts_railway_target(self, tmp_path):
        from codeupipe.deploy.manifest import load_manifest
        toml = '[project]\nname = "t"\n\n[deploy]\ntarget = "railway"\n'
        f = tmp_path / "cup.toml"
        f.write_text(toml)
        assert load_manifest(str(f))["deploy"]["target"] == "railway"

    def test_railway_export_top_level(self):
        from codeupipe import RailwayAdapter
        assert RailwayAdapter is not None


# ── CloudRunAdapter ──────────────────────────────────────────────────

class TestCloudRunAdapter:
    """Tests for the CloudRunAdapter — Google Cloud Run."""

    @pytest.fixture
    def adapter(self):
        from codeupipe.deploy.cloudrun import CloudRunAdapter
        return CloudRunAdapter()

    @pytest.fixture
    def valid_config(self):
        return {
            "project": {"name": "test-app"},
            "pipeline": {
                "name": "test",
                "steps": [{"name": "S1", "type": "filter"}],
            },
            "connectors": {},
        }

    def test_target_metadata(self, adapter):
        target = adapter.target()
        assert target.name == "cloudrun"
        assert "cloud run" in target.description.lower()

    def test_validate_warns_missing_project(self, adapter, valid_config):
        issues = adapter.validate(valid_config)
        assert any("gcp_project" in i for i in issues)

    def test_validate_with_project_option(self, adapter, valid_config):
        issues = adapter.validate(valid_config, gcp_project="my-proj")
        assert issues == []

    def test_generate_creates_artifacts(self, adapter, valid_config, tmp_path):
        out = tmp_path / "out"
        files = adapter.generate(valid_config, out, gcp_project="proj")
        assert len(files) == 6  # deploy.sh + Dockerfile + pipeline.json + entrypoint + req + .dockerignore
        names = [f.name for f in files]
        assert "deploy.sh" in names
        assert "Dockerfile" in names

    def test_deploy_script_has_gcloud(self, adapter, valid_config, tmp_path):
        out = tmp_path / "out"
        adapter.generate(valid_config, out, gcp_project="test-proj")
        script = (out / "deploy.sh").read_text()
        assert "gcloud run deploy" in script
        assert "test-proj" in script

    def test_deploy_dry_run(self, adapter, tmp_path):
        result = adapter.deploy(tmp_path, dry_run=True)
        assert "dry-run" in result.lower()
        assert "cloud run" in result.lower()


class TestCloudRunDiscovery:

    def test_cloudrun_in_find_adapters(self):
        from codeupipe.deploy import find_adapters
        assert "cloudrun" in find_adapters()

    def test_manifest_accepts_cloudrun_target(self, tmp_path):
        from codeupipe.deploy.manifest import load_manifest
        toml = '[project]\nname = "t"\n\n[deploy]\ntarget = "cloudrun"\n'
        f = tmp_path / "cup.toml"
        f.write_text(toml)
        assert load_manifest(str(f))["deploy"]["target"] == "cloudrun"

    def test_cloudrun_export_top_level(self):
        from codeupipe import CloudRunAdapter
        assert CloudRunAdapter is not None


# ── KoyebAdapter ─────────────────────────────────────────────────────

class TestKoyebAdapter:
    """Tests for the KoyebAdapter — free nano instance."""

    @pytest.fixture
    def adapter(self):
        from codeupipe.deploy.koyeb import KoyebAdapter
        return KoyebAdapter()

    @pytest.fixture
    def valid_config(self):
        return {
            "project": {"name": "test-app"},
            "pipeline": {
                "name": "test",
                "steps": [{"name": "S1", "type": "filter"}],
            },
            "connectors": {},
        }

    def test_target_metadata(self, adapter):
        target = adapter.target()
        assert target.name == "koyeb"
        assert "koyeb" in target.description.lower()

    def test_validate_valid_config(self, adapter, valid_config):
        assert adapter.validate(valid_config) == []

    def test_generate_creates_artifacts(self, adapter, valid_config, tmp_path):
        out = tmp_path / "out"
        files = adapter.generate(valid_config, out)
        assert len(files) == 5
        names = [f.name for f in files]
        assert "koyeb.yaml" in names
        assert "Dockerfile" in names

    def test_koyeb_yaml_has_free_instance(self, adapter, valid_config, tmp_path):
        out = tmp_path / "out"
        adapter.generate(valid_config, out)
        content = (out / "koyeb.yaml").read_text()
        assert "instance_type: free" in content

    def test_koyeb_yaml_has_health_check(self, adapter, valid_config, tmp_path):
        out = tmp_path / "out"
        adapter.generate(valid_config, out)
        content = (out / "koyeb.yaml").read_text()
        assert "health_checks:" in content

    def test_deploy_dry_run(self, adapter, tmp_path):
        result = adapter.deploy(tmp_path, dry_run=True)
        assert "dry-run" in result.lower()
        assert "koyeb" in result.lower()


class TestKoyebDiscovery:

    def test_koyeb_in_find_adapters(self):
        from codeupipe.deploy import find_adapters
        assert "koyeb" in find_adapters()

    def test_manifest_accepts_koyeb_target(self, tmp_path):
        from codeupipe.deploy.manifest import load_manifest
        toml = '[project]\nname = "t"\n\n[deploy]\ntarget = "koyeb"\n'
        f = tmp_path / "cup.toml"
        f.write_text(toml)
        assert load_manifest(str(f))["deploy"]["target"] == "koyeb"

    def test_koyeb_export_top_level(self):
        from codeupipe import KoyebAdapter
        assert KoyebAdapter is not None


# ── AppRunnerAdapter ─────────────────────────────────────────────────

class TestAppRunnerAdapter:
    """Tests for the AppRunnerAdapter — AWS App Runner."""

    @pytest.fixture
    def adapter(self):
        from codeupipe.deploy.apprunner import AppRunnerAdapter
        return AppRunnerAdapter()

    @pytest.fixture
    def valid_config(self):
        return {
            "project": {"name": "test-app"},
            "pipeline": {
                "name": "test",
                "steps": [{"name": "S1", "type": "filter"}],
            },
            "connectors": {},
        }

    def test_target_metadata(self, adapter):
        target = adapter.target()
        assert target.name == "apprunner"
        assert "app runner" in target.description.lower()

    def test_validate_valid_config(self, adapter, valid_config):
        assert adapter.validate(valid_config) == []

    def test_generate_creates_artifacts(self, adapter, valid_config, tmp_path):
        out = tmp_path / "out"
        files = adapter.generate(valid_config, out)
        assert len(files) == 5
        names = [f.name for f in files]
        assert "apprunner.yaml" in names
        assert "Dockerfile" in names

    def test_apprunner_yaml_has_scaling(self, adapter, valid_config, tmp_path):
        out = tmp_path / "out"
        adapter.generate(valid_config, out)
        content = (out / "apprunner.yaml").read_text()
        assert "scaling:" in content
        assert "min_size:" in content

    def test_deploy_dry_run(self, adapter, tmp_path):
        result = adapter.deploy(tmp_path, dry_run=True)
        assert "dry-run" in result.lower()
        assert "app runner" in result.lower()


class TestAppRunnerDiscovery:

    def test_apprunner_in_find_adapters(self):
        from codeupipe.deploy import find_adapters
        assert "apprunner" in find_adapters()

    def test_manifest_accepts_apprunner_target(self, tmp_path):
        from codeupipe.deploy.manifest import load_manifest
        toml = '[project]\nname = "t"\n\n[deploy]\ntarget = "apprunner"\n'
        f = tmp_path / "cup.toml"
        f.write_text(toml)
        assert load_manifest(str(f))["deploy"]["target"] == "apprunner"

    def test_apprunner_export_top_level(self):
        from codeupipe import AppRunnerAdapter
        assert AppRunnerAdapter is not None


# ── OracleAdapter ────────────────────────────────────────────────────

class TestOracleAdapter:
    """Tests for the OracleAdapter — Oracle Cloud Always Free VM."""

    @pytest.fixture
    def adapter(self):
        from codeupipe.deploy.oracle import OracleAdapter
        return OracleAdapter()

    @pytest.fixture
    def valid_config(self):
        return {
            "project": {"name": "test-app"},
            "pipeline": {
                "name": "test",
                "steps": [{"name": "S1", "type": "filter"}],
            },
            "connectors": {},
        }

    def test_target_metadata(self, adapter):
        target = adapter.target()
        assert target.name == "oracle"
        assert "oracle" in target.description.lower()

    def test_validate_valid_config(self, adapter, valid_config):
        assert adapter.validate(valid_config) == []

    def test_generate_creates_artifacts(self, adapter, valid_config, tmp_path):
        out = tmp_path / "out"
        files = adapter.generate(valid_config, out)
        assert len(files) == 6  # compose + deploy.sh + Dockerfile + pipeline.json + entrypoint + reqs
        names = [f.name for f in files]
        assert "docker-compose.yml" in names
        assert "deploy.sh" in names
        assert "Dockerfile" in names

    def test_compose_has_service(self, adapter, valid_config, tmp_path):
        out = tmp_path / "out"
        adapter.generate(valid_config, out)
        content = (out / "docker-compose.yml").read_text()
        assert "services:" in content
        assert "test-app:" in content

    def test_compose_has_postgres_when_connector(self, adapter, tmp_path):
        config = {
            "project": {"name": "x"},
            "pipeline": {"name": "test", "steps": [{"name": "S1", "type": "filter"}]},
            "connectors": {"db": {"provider": "postgres"}},
        }
        out = tmp_path / "out"
        adapter.generate(config, out)
        content = (out / "docker-compose.yml").read_text()
        assert "postgres:" in content
        assert "pgdata:" in content

    def test_deploy_script_has_ssh(self, adapter, valid_config, tmp_path):
        out = tmp_path / "out"
        adapter.generate(valid_config, out)
        script = (out / "deploy.sh").read_text()
        assert "ssh" in script.lower()
        assert "docker compose" in script

    def test_deploy_dry_run(self, adapter, tmp_path):
        result = adapter.deploy(tmp_path, dry_run=True)
        assert "dry-run" in result.lower()
        assert "oracle" in result.lower()


class TestOracleDiscovery:

    def test_oracle_in_find_adapters(self):
        from codeupipe.deploy import find_adapters
        assert "oracle" in find_adapters()

    def test_manifest_accepts_oracle_target(self, tmp_path):
        from codeupipe.deploy.manifest import load_manifest
        toml = '[project]\nname = "t"\n\n[deploy]\ntarget = "oracle"\n'
        f = tmp_path / "cup.toml"
        f.write_text(toml)
        assert load_manifest(str(f))["deploy"]["target"] == "oracle"

    def test_oracle_export_top_level(self):
        from codeupipe import OracleAdapter
        assert OracleAdapter is not None


# ── AzureContainerAppsAdapter ────────────────────────────────────────

class TestAzureContainerAppsAdapter:
    """Tests for the AzureContainerAppsAdapter — Azure Container Apps."""

    @pytest.fixture
    def adapter(self):
        from codeupipe.deploy.azure_container_apps import AzureContainerAppsAdapter
        return AzureContainerAppsAdapter()

    @pytest.fixture
    def valid_config(self):
        return {
            "project": {"name": "test-app"},
            "pipeline": {
                "name": "test",
                "steps": [{"name": "S1", "type": "filter"}],
            },
            "connectors": {},
        }

    def test_target_metadata(self, adapter):
        target = adapter.target()
        assert target.name == "azure-container-apps"
        assert "azure" in target.description.lower()

    def test_validate_valid_config(self, adapter, valid_config):
        assert adapter.validate(valid_config) == []

    def test_generate_creates_artifacts(self, adapter, valid_config, tmp_path):
        out = tmp_path / "out"
        files = adapter.generate(valid_config, out)
        assert len(files) == 5
        names = [f.name for f in files]
        assert "deploy.sh" in names
        assert "Dockerfile" in names

    def test_deploy_script_has_az_commands(self, adapter, valid_config, tmp_path):
        out = tmp_path / "out"
        adapter.generate(valid_config, out)
        script = (out / "deploy.sh").read_text()
        assert "az containerapp" in script

    def test_deploy_dry_run(self, adapter, tmp_path):
        result = adapter.deploy(tmp_path, dry_run=True)
        assert "dry-run" in result.lower()
        assert "azure" in result.lower()


class TestAzureContainerAppsDiscovery:

    def test_azure_container_apps_in_find_adapters(self):
        from codeupipe.deploy import find_adapters
        assert "azure-container-apps" in find_adapters()

    def test_manifest_accepts_azure_container_apps_target(self, tmp_path):
        from codeupipe.deploy.manifest import load_manifest
        toml = '[project]\nname = "t"\n\n[deploy]\ntarget = "azure-container-apps"\n'
        f = tmp_path / "cup.toml"
        f.write_text(toml)
        assert load_manifest(str(f))["deploy"]["target"] == "azure-container-apps"

    def test_azure_container_apps_export_top_level(self):
        from codeupipe import AzureContainerAppsAdapter
        assert AzureContainerAppsAdapter is not None


# ── HuggingFaceAdapter ──────────────────────────────────────────────

class TestHuggingFaceAdapter:
    """Tests for the HuggingFaceAdapter — HF Spaces deployment."""

    @pytest.fixture
    def adapter(self):
        from codeupipe.deploy.huggingface import HuggingFaceAdapter
        return HuggingFaceAdapter()

    @pytest.fixture
    def valid_config(self):
        return {
            "project": {"name": "test-app"},
            "pipeline": {
                "name": "test",
                "steps": [{"name": "S1", "type": "filter"}],
            },
            "connectors": {},
        }

    def test_target_metadata(self, adapter):
        target = adapter.target()
        assert target.name == "hf-spaces"
        assert "hugging face" in target.description.lower()

    def test_validate_valid_config(self, adapter, valid_config):
        assert adapter.validate(valid_config) == []

    def test_generate_creates_artifacts(self, adapter, valid_config, tmp_path):
        out = tmp_path / "out"
        files = adapter.generate(valid_config, out)
        assert len(files) == 5
        names = [f.name for f in files]
        assert "README.md" in names
        assert "Dockerfile" in names

    def test_readme_has_hf_metadata(self, adapter, valid_config, tmp_path):
        out = tmp_path / "out"
        adapter.generate(valid_config, out)
        readme = (out / "README.md").read_text()
        assert "sdk: docker" in readme
        assert "title: test-app" in readme

    def test_dockerfile_uses_port_7860(self, adapter, valid_config, tmp_path):
        out = tmp_path / "out"
        adapter.generate(valid_config, out)
        dockerfile = (out / "Dockerfile").read_text()
        assert "EXPOSE 7860" in dockerfile

    def test_dockerfile_has_non_root_user(self, adapter, valid_config, tmp_path):
        out = tmp_path / "out"
        adapter.generate(valid_config, out)
        dockerfile = (out / "Dockerfile").read_text()
        assert "USER user" in dockerfile

    def test_deploy_dry_run(self, adapter, tmp_path):
        result = adapter.deploy(tmp_path, dry_run=True)
        assert "dry-run" in result.lower()
        assert "hugging face" in result.lower()


class TestHuggingFaceDiscovery:

    def test_hf_spaces_in_find_adapters(self):
        from codeupipe.deploy import find_adapters
        assert "hf-spaces" in find_adapters()

    def test_manifest_accepts_hf_spaces_target(self, tmp_path):
        from codeupipe.deploy.manifest import load_manifest
        toml = '[project]\nname = "t"\n\n[deploy]\ntarget = "hf-spaces"\n'
        f = tmp_path / "cup.toml"
        f.write_text(toml)
        assert load_manifest(str(f))["deploy"]["target"] == "hf-spaces"

    def test_hf_export_top_level(self):
        from codeupipe import HuggingFaceAdapter
        assert HuggingFaceAdapter is not None
