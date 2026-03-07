"""
DockerAdapter: Built-in deploy adapter that generates containerized pipeline artifacts.

Generates Dockerfile, entrypoint, requirements.txt, and optionally docker-compose.yml.
Zero external dependencies — pure string template generation.
"""

import json
import shutil
from pathlib import Path
from typing import List

from .adapter import DeployAdapter, DeployTarget

__all__ = ["DockerAdapter"]

# Execution modes determined by pipeline shape
MODE_HTTP = "http"
MODE_WORKER = "worker"
MODE_CLI = "cli"


class DockerAdapter(DeployAdapter):
    """Generates Dockerfile + entrypoint for any pipeline config."""

    def target(self) -> DeployTarget:
        return DeployTarget(
            name="docker",
            description="Containerized pipeline — generates Dockerfile + entrypoint",
            requires=[],
        )

    def validate(self, pipeline_config: dict, **options) -> List[str]:
        issues = []
        if "pipeline" not in pipeline_config:
            issues.append("Config missing 'pipeline' key")
        elif "steps" not in pipeline_config.get("pipeline", {}):
            issues.append("Config 'pipeline' missing 'steps'")
        return issues

    def generate(self, pipeline_config: dict, output_dir: Path, **options) -> List[Path]:
        output_dir.mkdir(parents=True, exist_ok=True)
        generated: List[Path] = []

        mode = options.get("mode", self._detect_mode(pipeline_config))
        port = options.get("port", 8000)
        python_version = options.get("python_version", "3.12")

        # 1. Copy / write pipeline config
        config_path = output_dir / "pipeline.json"
        config_path.write_text(json.dumps(pipeline_config, indent=2))
        generated.append(config_path)

        # 2. Write entrypoint
        entrypoint_path = output_dir / "entrypoint.py"
        entrypoint_path.write_text(self._render_entrypoint(mode, port))
        generated.append(entrypoint_path)

        # 3. Write requirements.txt
        reqs_path = output_dir / "requirements.txt"
        reqs_path.write_text(self._render_requirements(pipeline_config))
        generated.append(reqs_path)

        # 4. Write Dockerfile
        dockerfile_path = output_dir / "Dockerfile"
        dockerfile_path.write_text(
            self._render_dockerfile(mode, port, python_version)
        )
        generated.append(dockerfile_path)

        return generated

    def deploy(self, output_dir: Path, *, dry_run: bool = False, **options) -> str:
        if dry_run:
            return f"[dry-run] Would build and run Docker image from {output_dir}"
        return (
            f"Artifacts generated in {output_dir}/\n"
            f"Build: docker build -t my-pipeline {output_dir}\n"
            f"Run:   docker run -p 8000:8000 my-pipeline"
        )

    # ── Internal ────────────────────────────────────────────────

    @staticmethod
    def _detect_mode(pipeline_config: dict) -> str:
        """Auto-detect execution mode from pipeline shape."""
        steps = pipeline_config.get("pipeline", {}).get("steps", [])
        for step in steps:
            if step.get("type") in ("stream-filter",):
                return MODE_WORKER
        # Check for trigger/schedule config
        pipeline_sec = pipeline_config.get("pipeline", {})
        if "schedule" in pipeline_sec or "trigger" in pipeline_sec:
            return MODE_WORKER
        return MODE_HTTP

    @staticmethod
    def _render_entrypoint(mode: str, port: int) -> str:
        """Render the pipeline entrypoint script."""
        header = (
            '"""Auto-generated pipeline entrypoint by cup deploy."""\n'
            "import asyncio\n"
            "import json\n"
            "import sys\n"
            "from pathlib import Path\n"
            "\n"
            "from codeupipe import Pipeline, Payload\n"
            "from codeupipe.registry import Registry, default_registry\n"
            "\n"
            "\n"
            'CONFIG_PATH = Path(__file__).parent / "pipeline.json"\n'
            "\n"
            "\n"
            "def _load_pipeline():\n"
            '    return Pipeline.from_config(str(CONFIG_PATH), registry=default_registry)\n'
            "\n"
        )

        if mode == MODE_HTTP:
            return header + (
                "\n"
                "def main():\n"
                "    from http.server import HTTPServer, BaseHTTPRequestHandler\n"
                "\n"
                "    pipeline = _load_pipeline()\n"
                "\n"
                "    class Handler(BaseHTTPRequestHandler):\n"
                "        def do_POST(self):\n"
                "            length = int(self.headers.get('Content-Length', 0))\n"
                "            body = self.rfile.read(length) if length else b'{}'\n"
                "            data = json.loads(body)\n"
                "            result = asyncio.run(pipeline.run(Payload(data)))\n"
                "            response = json.dumps(result.to_dict()).encode()\n"
                "            self.send_response(200)\n"
                "            self.send_header('Content-Type', 'application/json')\n"
                "            self.send_header('Content-Length', str(len(response)))\n"
                "            self.end_headers()\n"
                "            self.wfile.write(response)\n"
                "\n"
                "        def do_GET(self):\n"
                "            self.send_response(200)\n"
                "            self.send_header('Content-Type', 'application/json')\n"
                "            body = b'{\"status\": \"ok\"}'\n"
                "            self.send_header('Content-Length', str(len(body)))\n"
                "            self.end_headers()\n"
                "            self.wfile.write(body)\n"
                "\n"
                f'    server = HTTPServer(("0.0.0.0", {port}), Handler)\n'
                f'    print(f"Pipeline server listening on 0.0.0.0:{port}")\n'
                "    server.serve_forever()\n"
                "\n"
                "\n"
                'if __name__ == "__main__":\n'
                "    main()\n"
            )

        if mode == MODE_WORKER:
            return header + (
                "\n"
                "def main():\n"
                "    pipeline = _load_pipeline()\n"
                "    print('Pipeline worker started')\n"
                "    # Read payloads from stdin, one JSON per line\n"
                "    for line in sys.stdin:\n"
                "        line = line.strip()\n"
                "        if not line:\n"
                "            continue\n"
                "        data = json.loads(line)\n"
                "        result = asyncio.run(pipeline.run(Payload(data)))\n"
                "        print(json.dumps(result.to_dict()), flush=True)\n"
                "\n"
                "\n"
                'if __name__ == "__main__":\n'
                "    main()\n"
            )

        # CLI mode
        return header + (
            "\n"
            "def main():\n"
            "    pipeline = _load_pipeline()\n"
            "    # Read single payload from stdin or args\n"
            "    if len(sys.argv) > 1:\n"
            "        data = json.loads(sys.argv[1])\n"
            "    elif not sys.stdin.isatty():\n"
            "        data = json.loads(sys.stdin.read())\n"
            "    else:\n"
            "        data = {}\n"
            "    result = asyncio.run(pipeline.run(Payload(data)))\n"
            "    print(json.dumps(result.to_dict(), indent=2))\n"
            "\n"
            "\n"
            'if __name__ == "__main__":\n'
            "    main()\n"
        )

    @staticmethod
    def _render_requirements(pipeline_config: dict) -> str:
        """Extract requirements from pipeline config."""
        lines = ["codeupipe"]
        deps = pipeline_config.get("dependencies", {})
        for pkg in deps:
            if isinstance(deps[pkg], str):
                lines.append(f"{pkg}{deps[pkg]}")
            else:
                lines.append(pkg)
        return "\n".join(lines) + "\n"

    @staticmethod
    def _render_dockerfile(mode: str, port: int, python_version: str) -> str:
        """Render Dockerfile."""
        expose = f"EXPOSE {port}\n" if mode == MODE_HTTP else ""
        return (
            f"FROM python:{python_version}-slim\n"
            "\n"
            "WORKDIR /app\n"
            "\n"
            "COPY requirements.txt .\n"
            "RUN pip install --no-cache-dir -r requirements.txt\n"
            "\n"
            "COPY . .\n"
            "\n"
            f"{expose}"
            'CMD ["python", "entrypoint.py"]\n'
        )
