"""
VercelAdapter: Deploy adapter for Vercel (static frontend + serverless API).

Generates vercel.json, serverless function wrappers, requirements.txt,
and optional frontend build configuration. Zero external dependencies.

Usage:
    cup deploy vercel cup.toml
    cup deploy vercel pipeline.json --output-dir deploy_output
"""

import json
import shutil
import subprocess
from pathlib import Path
from typing import List

from .adapter import DeployAdapter, DeployTarget
from .handlers import render_vercel_handler

__all__ = ["VercelAdapter"]


class VercelAdapter(DeployAdapter):
    """Generates Vercel deployment artifacts for pipeline + optional frontend."""

    def target(self) -> DeployTarget:
        return DeployTarget(
            name="vercel",
            description="Vercel — static frontend + Python serverless API",
            requires=[],
        )

    def validate(self, pipeline_config: dict, **options) -> List[str]:
        issues = []
        # Must have pipeline config unless it's frontend-only
        has_pipeline = "pipeline" in pipeline_config
        has_frontend = "frontend" in pipeline_config

        if not has_pipeline and not has_frontend:
            issues.append("Config needs 'pipeline' and/or 'frontend' section")
        if has_pipeline and "steps" not in pipeline_config.get("pipeline", {}):
            issues.append("Config 'pipeline' missing 'steps'")
        if has_frontend:
            fw = pipeline_config["frontend"].get("framework")
            if not fw:
                issues.append("[frontend] missing 'framework'")
        return issues

    def generate(self, pipeline_config: dict, output_dir: Path, **options) -> List[Path]:
        output_dir.mkdir(parents=True, exist_ok=True)
        generated: List[Path] = []

        project_name = pipeline_config.get("project", {}).get("name", "my-app")
        has_pipeline = "pipeline" in pipeline_config
        has_frontend = "frontend" in pipeline_config
        frontend = pipeline_config.get("frontend", {})

        # 1. vercel.json
        vercel_config = self._render_vercel_json(
            project_name, has_pipeline, has_frontend, frontend
        )
        vercel_path = output_dir / "vercel.json"
        vercel_path.write_text(json.dumps(vercel_config, indent=2) + "\n")
        generated.append(vercel_path)

        # 2. Serverless API function (if pipeline present)
        if has_pipeline:
            api_dir = output_dir / "api"
            api_dir.mkdir(exist_ok=True)

            # Handler
            handler_path = api_dir / "pipeline.py"
            handler_path.write_text(render_vercel_handler())
            generated.append(handler_path)

            # Pipeline config at project root (handler reads ../pipeline.json)
            config_path = output_dir / "pipeline.json"
            config_path.write_text(json.dumps(pipeline_config, indent=2))
            generated.append(config_path)

            # requirements.txt for the API
            reqs_path = output_dir / "requirements.txt"
            reqs_path.write_text(self._render_requirements(pipeline_config))
            generated.append(reqs_path)

        # 3. Frontend scaffold (if frontend section present)
        if has_frontend:
            framework = frontend.get("framework", "react")
            public_dir = output_dir / "public"
            public_dir.mkdir(exist_ok=True)

            index_path = public_dir / "index.html"
            index_path.write_text(self._render_placeholder_html(project_name))
            generated.append(index_path)

            # package.json for frontend build
            pkg_path = output_dir / "package.json"
            pkg_path.write_text(
                json.dumps(self._render_package_json(project_name, framework), indent=2) + "\n"
            )
            generated.append(pkg_path)

            # Environment config hint
            env_path = output_dir / ".env.example"
            api_url = "/api/pipeline" if has_pipeline else ""
            env_path.write_text(
                f"# Vercel environment variables\n"
                f"VITE_API_URL={api_url}\n"
                f"# Set these in Vercel dashboard > Settings > Environment Variables\n"
            )
            generated.append(env_path)

        return generated

    def deploy(self, output_dir: Path, *, dry_run: bool = False, **options) -> str:
        if dry_run:
            return f"[dry-run] Would deploy {output_dir} to Vercel"

        # Check if vercel CLI is available
        if not shutil.which("vercel"):
            return (
                f"Artifacts generated in {output_dir}/\n"
                f"Install Vercel CLI: npm i -g vercel\n"
                f"Then run: cd {output_dir} && vercel --prod"
            )

        try:
            result = subprocess.run(
                ["vercel", "--prod", "--yes"],
                cwd=str(output_dir),
                capture_output=True,
                text=True,
                timeout=120,
            )
            if result.returncode == 0:
                url = result.stdout.strip().splitlines()[-1]
                return f"Deployed to Vercel: {url}"
            return f"Vercel deploy failed:\n{result.stderr}"
        except subprocess.TimeoutExpired:
            return "Vercel deploy timed out after 120s"
        except Exception as e:
            return f"Vercel deploy error: {e}"

    # ── Internal ────────────────────────────────────────────────

    @staticmethod
    def _render_vercel_json(
        name: str, has_api: bool, has_frontend: bool, frontend: dict
    ) -> dict:
        """Render vercel.json configuration."""
        config: dict = {"version": 2}

        builds = []
        routes = []

        if has_api:
            builds.append({
                "src": "api/pipeline.py",
                "use": "@vercel/python",
            })
            routes.append({
                "src": "/api/pipeline",
                "dest": "/api/pipeline.py",
            })

        if has_frontend:
            framework = frontend.get("framework", "react")
            build_command = frontend.get("build_command")
            output_directory = frontend.get("output_dir", "dist")

            if framework in ("react", "vite"):
                if not build_command:
                    build_command = "npm run build"
                config["buildCommand"] = build_command
                config["outputDirectory"] = output_directory
            elif framework == "next":
                config["framework"] = "nextjs"
        else:
            # API-only: serve static public/ as fallback
            builds.append({
                "src": "public/**",
                "use": "@vercel/static",
            })

        if builds:
            config["builds"] = builds
        if routes:
            # API routes first, then frontend catch-all
            if has_frontend:
                routes.append({"src": "/(.*)", "dest": "/$1"})
            config["routes"] = routes

        return config

    @staticmethod
    def _render_requirements(pipeline_config: dict) -> str:
        lines = ["codeupipe"]
        deps = pipeline_config.get("dependencies", {})
        for pkg in deps:
            if isinstance(deps[pkg], str):
                lines.append(f"{pkg}{deps[pkg]}")
            else:
                lines.append(pkg)
        return "\n".join(lines) + "\n"

    @staticmethod
    def _render_package_json(name: str, framework: str) -> dict:
        if framework == "next":
            return {
                "name": name,
                "private": True,
                "scripts": {
                    "dev": "next dev",
                    "build": "next build",
                    "start": "next start",
                },
                "dependencies": {
                    "next": "^14.0.0",
                    "react": "^18.0.0",
                    "react-dom": "^18.0.0",
                },
            }
        # Default: Vite + React
        return {
            "name": name,
            "private": True,
            "scripts": {
                "dev": "vite",
                "build": "vite build",
                "preview": "vite preview",
            },
            "dependencies": {
                "react": "^18.0.0",
                "react-dom": "^18.0.0",
            },
            "devDependencies": {
                "vite": "^5.0.0",
                "@vitejs/plugin-react": "^4.0.0",
            },
        }

    @staticmethod
    def _render_placeholder_html(name: str) -> str:
        return (
            "<!DOCTYPE html>\n"
            "<html lang=\"en\">\n"
            "<head>\n"
            "  <meta charset=\"UTF-8\" />\n"
            "  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\" />\n"
            f"  <title>{name}</title>\n"
            "</head>\n"
            "<body>\n"
            f"  <h1>{name}</h1>\n"
            "  <p>Powered by <a href=\"https://pypi.org/project/codeupipe/\">codeupipe</a></p>\n"
            "  <div id=\"root\"></div>\n"
            "</body>\n"
            "</html>\n"
        )
