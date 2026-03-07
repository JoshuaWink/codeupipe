"""Tests for `cup run` CLI command — execute pipelines from config files."""

import json
import subprocess
import sys

import pytest


def _run_cup(*args):
    """Run cup CLI and capture output."""
    return subprocess.run(
        [sys.executable, "-m", "codeupipe.cli", *args],
        capture_output=True,
        text=True,
        timeout=15,
    )


class TestCupRun:
    """CLI: cup run <config> [--registry <path>]."""

    def test_run_json_pipeline(self, tmp_path):
        """Run a pipeline from a JSON config with a component directory."""
        # Create a filter
        comp_dir = tmp_path / "components"
        comp_dir.mkdir()
        (comp_dir / "add_ten.py").write_text(
            "from codeupipe import Payload\n\n"
            "class AddTenFilter:\n"
            "    def call(self, payload):\n"
            "        return payload.insert('value', payload.get('value', 0) + 10)\n"
        )

        # Create config
        config = tmp_path / "pipeline.json"
        config.write_text(json.dumps({
            "pipeline": {
                "name": "add-ten",
                "steps": [
                    {"name": "AddTenFilter", "type": "filter"},
                ],
            }
        }))

        result = _run_cup("run", str(config), "--discover", str(comp_dir))
        assert result.returncode == 0
        assert "add-ten" in result.stdout.lower() or "complete" in result.stdout.lower()

    def test_run_missing_config_errors(self):
        result = _run_cup("run", "/no/such/file.json")
        assert result.returncode != 0

    def test_run_no_args_shows_help(self):
        result = _run_cup("run")
        assert result.returncode != 0

    def test_run_with_input_json(self, tmp_path):
        """Pass initial payload data via --input."""
        comp_dir = tmp_path / "components"
        comp_dir.mkdir()
        (comp_dir / "echo.py").write_text(
            "from codeupipe import Payload\n\n"
            "class EchoFilter:\n"
            "    def call(self, payload):\n"
            "        return payload\n"
        )

        config = tmp_path / "pipeline.json"
        config.write_text(json.dumps({
            "pipeline": {
                "name": "echo",
                "steps": [
                    {"name": "EchoFilter", "type": "filter"},
                ],
            }
        }))

        result = _run_cup(
            "run", str(config),
            "--discover", str(comp_dir),
            "--input", '{"message": "hello"}',
        )
        assert result.returncode == 0

    def test_run_with_json_output(self, tmp_path):
        """--json flag outputs result as JSON."""
        comp_dir = tmp_path / "components"
        comp_dir.mkdir()
        (comp_dir / "stamp.py").write_text(
            "from codeupipe import Payload\n\n"
            "class StampFilter:\n"
            "    def call(self, payload):\n"
            "        return payload.insert('stamped', True)\n"
        )

        config = tmp_path / "pipeline.json"
        config.write_text(json.dumps({
            "pipeline": {
                "name": "stamp",
                "steps": [
                    {"name": "StampFilter", "type": "filter"},
                ],
            }
        }))

        result = _run_cup(
            "run", str(config),
            "--discover", str(comp_dir),
            "--json",
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["stamped"] is True
