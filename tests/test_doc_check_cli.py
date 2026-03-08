"""Tests for `cup doc-check` CLI command and doc_check() wrapper."""

import json
import os

import pytest

from codeupipe.cli import main
from codeupipe.cli.commands.analysis_cmds import doc_check


class TestDocCheckWrapper:
    """Tests for the doc_check() programmatic API."""

    def test_clean_directory_returns_ok(self, tmp_path):
        """No markers at all → status ok."""
        (tmp_path / "README.md").write_text("# Hello\nNo cup:ref markers here.\n")
        result = doc_check(str(tmp_path))
        assert result["status"] == "ok"
        assert result["total_refs"] == 0

    def test_detects_drift(self, tmp_path):
        """Stale hash → status stale with drifted count."""
        src = tmp_path / "module.py"
        src.write_text("class Foo:\n    pass\n")

        doc = tmp_path / "GUIDE.md"
        doc.write_text(
            "<!-- cup:ref file=module.py symbols=Foo hash=0000000 -->\n"
            "Uses Foo.\n"
            "<!-- /cup:ref -->\n"
        )
        result = doc_check(str(tmp_path))
        assert result["status"] == "stale"
        assert result["drifted"] >= 1

    def test_detects_missing_symbol(self, tmp_path):
        """Referenced symbol doesn't exist → missing_symbols count."""
        src = tmp_path / "module.py"
        src.write_text("class Foo:\n    pass\n")

        doc = tmp_path / "GUIDE.md"
        doc.write_text(
            "<!-- cup:ref file=module.py symbols=Bar -->\n"
            "Uses Bar.\n"
            "<!-- /cup:ref -->\n"
        )
        result = doc_check(str(tmp_path))
        assert result["status"] == "stale"
        assert result["missing_symbols"] >= 1

    def test_detects_missing_file(self, tmp_path):
        """Referenced file doesn't exist → missing_files count."""
        doc = tmp_path / "GUIDE.md"
        doc.write_text(
            "<!-- cup:ref file=gone.py hash=abc1234 -->\n"
            "Was here.\n"
            "<!-- /cup:ref -->\n"
        )
        result = doc_check(str(tmp_path))
        assert result["status"] == "stale"
        assert result["missing_files"] >= 1


class TestDocCheckCLI:
    """Tests for the `cup doc-check` CLI subcommand."""

    def test_clean_exit_zero(self, tmp_path, capsys):
        (tmp_path / "README.md").write_text("# Clean\n")
        code = main(["doc-check", str(tmp_path)])
        assert code == 0
        out = capsys.readouterr().out
        assert "✓" in out

    def test_stale_exit_one(self, tmp_path, capsys):
        src = tmp_path / "mod.py"
        src.write_text("x = 1\n")
        doc = tmp_path / "DOC.md"
        doc.write_text(
            "<!-- cup:ref file=mod.py hash=0000000 -->\nstale\n<!-- /cup:ref -->\n"
        )
        code = main(["doc-check", str(tmp_path)])
        assert code == 1
        out = capsys.readouterr().out
        assert "✗" in out
        assert "Drifted" in out

    def test_json_output(self, tmp_path, capsys):
        (tmp_path / "README.md").write_text("# OK\n")
        code = main(["doc-check", str(tmp_path), "--json"])
        assert code == 0
        out = capsys.readouterr().out
        data = json.loads(out)
        assert data["status"] == "ok"

    def test_json_stale_exit_one(self, tmp_path, capsys):
        doc = tmp_path / "DOC.md"
        doc.write_text(
            "<!-- cup:ref file=missing.py hash=abc1234 -->\ngone\n<!-- /cup:ref -->\n"
        )
        code = main(["doc-check", str(tmp_path), "--json"])
        assert code == 1
        out = capsys.readouterr().out
        data = json.loads(out)
        assert data["status"] == "stale"

    def test_default_path_is_cwd(self, tmp_path, capsys, monkeypatch):
        (tmp_path / "README.md").write_text("# Hello\n")
        monkeypatch.chdir(tmp_path)
        code = main(["doc-check"])
        assert code == 0
