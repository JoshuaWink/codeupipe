"""
NetlifyAdapter: Deploy adapter for Netlify (static frontend + serverless functions).

Generates netlify.toml, function handlers, requirements.txt,
and optional frontend build configuration. Zero external dependencies.

Usage:
    cup deploy netlify cup.toml
    cup deploy netlify pipeline.json --output-dir deploy_output
"""

import json
import shutil
import subprocess
from pathlib import Path
from typing import List

from .adapter import DeployAdapter, DeployTarget
from .handlers import render_netlify_handler

__all__ = ["NetlifyAdapter"]


class NetlifyAdapter(DeployAdapter):
    """Generates Netlify deployment artifacts for pipeline + optional frontend."""

    def target(self) -> DeployTarget:
        return DeployTarget(
            name="netlify",
            description="Netlify — static frontend + Python serverless functions",
            requires=[],
        )

    def validate(self, pipeline_config: dict, **options) -> List[str]:
        issues = []
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

        # 1. netlify.toml
        netlify_config = self._render_netlify_toml(
            has_pipeline, has_frontend, frontend
        )
        netlify_path = output_dir / "netlify.toml"
        netlify_path.write_text(netlify_config)
        generated.append(netlify_path)

        # 2. Serverless function (if pipeline present)
        if has_pipeline:
            func_dir = output_dir / "netlify" / "functions"
            func_dir.mkdir(parents=True, exist_ok=True)

            # Handler
            handler_path = func_dir / "pipeline.py"
            handler_path.write_text(render_netlify_handler())
            generated.append(handler_path)

            # Pipeline config at project root
            config_path = output_dir / "pipeline.json"
            config_path.write_text(json.dumps(pipeline_config, indent=2))
            generated.append(config_path)

            # requirements.txt
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

            pkg_path = output_dir / "package.json"
            pkg_path.write_text(
                json.dumps(self._render_package_json(project_name, framework), indent=2) + "\n"
            )
            generated.append(pkg_path)

            env_path = output_dir / ".env.example"
            api_url = "/.netlify/functions/pipeline" if has_pipeline else ""
            env_path.write_text(
                f"# Netlify environment variables\n"
                f"VITE_API_URL={api_url}\n"
                f"# Set these in Netlify dashboard > Site settings > Environment variables\n"
            )
            generated.append(env_path)

        return generated

    def deploy(self, output_dir: Path, *, dry_run: bool = False, **options) -> str:
        if dry_run:
            return f"[dry-run] Would deploy {output_dir} to Netlify"

        if not shutil.which("netlify"):
            return (
                f"Artifacts generated in {output_dir}/\n"
                f"Install Netlify CLI: npm i -g netlify-cli\n"
                f"Then run: cd {output_dir} && netlify deploy --prod"
            )

        try:
            result = subprocess.run(
                ["netlify", "deploy", "--prod", "--dir", "."],
                cwd=str(output_dir),
                capture_output=True,
                text=True,
                timeout=120,
            )
            if result.returncode == 0:
                # Extract URL from output
                for line in result.stdout.splitlines():
                    if "Website URL" in line or "https://" in line:
                        return f"Deployed to Netlify: {line.strip()}"
                return f"Deployed to Netlify successfully"
            return f"Netlify deploy failed:\n{result.stderr}"
        except subprocess.TimeoutExpired:
            return "Netlify deploy timed out after 120s"
        except Exception as e:
            return f"Netlify deploy error: {e}"

    # ── Internal ────────────────────────────────────────────────

    @staticmethod
    def _render_netlify_toml(
        has_api: bool, has_frontend: bool, frontend: dict
    ) -> str:
        """Render netlify.toml configuration."""
        lines = []

        # Build settings
        if has_frontend:
            framework = frontend.get("framework", "react")
            build_command = frontend.get("build_command")
            output_dir = frontend.get("output_dir", "dist")

            if not build_command:
                if framework == "next":
                    build_command = "next build"
                else:
                    build_command = "npm run build"

            lines.append("[build]")
            lines.append(f'  command = "{build_command}"')
            lines.append(f'  publish = "{output_dir}"')
            if has_api:
                lines.append('  functions = "netlify/functions"')
            lines.append("")
        elif has_api:
            lines.append("[build]")
            lines.append('  publish = "public"')
            lines.append('  functions = "netlify/functions"')
            lines.append("")

        # Redirects for SPA routing
        if has_frontend:
            lines.append("# SPA fallback — serves index.html for client-side routing")
            lines.append("[[redirects]]")
            lines.append('  from = "/*"')
            lines.append('  to = "/index.html"')
            lines.append("  status = 200")
            lines.append("")

        # API redirect for cleaner URLs
        if has_api:
            lines.append("# API route — maps /api/pipeline to function")
            lines.append("[[redirects]]")
            lines.append('  from = "/api/pipeline"')
            lines.append('  to = "/.netlify/functions/pipeline"')
            lines.append("  status = 200")
            lines.append("")

        return "\n".join(lines)

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
