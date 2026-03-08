"""Tests for cup distribute CLI command.

Covers: checkpoint save/load/clear/status, remote test, worker info.
"""

import json
from pathlib import Path

import pytest
from codeupipe.cli import main


class TestDistributeCheckpoint:
    """cup distribute checkpoint subcommand."""

    def test_checkpoint_save_and_load(self, tmp_path):
        """Save a payload then load it back."""
        cp_path = str(tmp_path / "cp.json")
        data = json.dumps({"x": 42, "name": "test"})

        rc = main(["distribute", "checkpoint", cp_path, "--save", data])
        assert rc == 0

        # Load it back — capture output
        import io, sys
        buf = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = buf
        rc = main(["distribute", "checkpoint", cp_path, "--load"])
        sys.stdout = old_stdout
        assert rc == 0
        loaded = json.loads(buf.getvalue())
        assert loaded["x"] == 42

    def test_checkpoint_load_missing(self, tmp_path):
        """Loading a nonexistent checkpoint fails."""
        cp_path = str(tmp_path / "nope.json")
        rc = main(["distribute", "checkpoint", cp_path, "--load"])
        assert rc == 1

    def test_checkpoint_clear(self, tmp_path):
        """Clear removes a checkpoint."""
        cp_path = str(tmp_path / "cp.json")
        data = json.dumps({"x": 1})
        main(["distribute", "checkpoint", cp_path, "--save", data])

        rc = main(["distribute", "checkpoint", cp_path, "--clear"])
        assert rc == 0

    def test_checkpoint_status_exists(self, tmp_path):
        """Status shows info for existing checkpoint."""
        cp_path = str(tmp_path / "cp.json")
        data = json.dumps({"val": 99})
        main(["distribute", "checkpoint", cp_path, "--save", data])

        import io, sys
        buf = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = buf
        rc = main(["distribute", "checkpoint", cp_path, "--status"])
        sys.stdout = old_stdout
        assert rc == 0
        output = buf.getvalue()
        assert "exists: True" in output

    def test_checkpoint_status_missing(self, tmp_path):
        """Status for nonexistent checkpoint."""
        cp_path = str(tmp_path / "nope.json")

        import io, sys
        buf = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = buf
        rc = main(["distribute", "checkpoint", cp_path, "--status"])
        sys.stdout = old_stdout
        assert rc == 0
        assert "No checkpoint" in buf.getvalue()


class TestDistributeWorker:
    """cup distribute worker subcommand."""

    def test_worker_info_thread(self):
        """Worker info for thread pool type."""
        import io, sys
        buf = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = buf
        rc = main(["distribute", "worker"])
        sys.stdout = old_stdout
        assert rc == 0
        output = buf.getvalue()
        assert "thread" in output

    def test_worker_info_process(self):
        """Worker info for process pool type."""
        import io, sys
        buf = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = buf
        rc = main(["distribute", "worker", "--kind", "process"])
        sys.stdout = old_stdout
        assert rc == 0
        output = buf.getvalue()
        assert "process" in output


class TestDistributeNoSubcommand:
    """cup distribute with no subcommand shows help."""

    def test_no_subcommand_returns_1(self):
        """No subcommand prints help and returns 1."""
        rc = main(["distribute"])
        assert rc == 1
