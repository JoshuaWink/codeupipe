"""Tests for GitHistory filter — RED phase first."""

import os
import subprocess

import pytest

from codeupipe import Payload
from codeupipe.linter.git_history import GitHistory


def _comp(name, stem, kind="filter", file_path=None):
    return {
        "file": file_path or f"src/{stem}.py",
        "stem": stem,
        "name": name,
        "kind": kind,
        "methods": ["call"] if kind == "filter" else [],
    }


_GIT_ENV = {
    "GIT_AUTHOR_NAME": "Test User",
    "GIT_AUTHOR_EMAIL": "test@test.com",
    "GIT_COMMITTER_NAME": "Test User",
    "GIT_COMMITTER_EMAIL": "test@test.com",
}


def _git(args, cwd, **kwargs):
    """Run a git command with check=True so test setup failures are loud."""
    env = {**os.environ, **_GIT_ENV}
    return subprocess.run(
        ["git"] + args, cwd=str(cwd), capture_output=True, text=True,
        check=True, env=env, **kwargs,
    )


def _init_repo(tmp_path):
    """Create a git repo with identity configured. Returns repo path."""
    _git(["init", "-b", "main"], tmp_path)
    _git(["config", "user.email", "test@test.com"], tmp_path)
    _git(["config", "user.name", "Test User"], tmp_path)
    return tmp_path


class TestGitHistory:
    """Unit tests for GitHistory filter."""

    @pytest.fixture(autouse=True)
    def _clean_git_env(self, monkeypatch):
        """Remove inherited GIT_* env vars that could mislead the filter."""
        for key in list(os.environ):
            if key.startswith("GIT_"):
                monkeypatch.delenv(key, raising=False)

    def test_returns_git_data_for_tracked_file(self, tmp_path):
        """Components in a real git repo get last_modified, author, commit_count."""
        _init_repo(tmp_path)
        f = tmp_path / "auth.py"
        f.write_text("class Auth:\n    def call(self, p): ...\n")
        _git(["add", "."], tmp_path)
        _git(["commit", "-m", "init"], tmp_path)

        comps = [_comp("Auth", "auth", file_path=str(f))]
        payload = Payload({"components": comps, "directory": str(tmp_path)})
        result = GitHistory().call(payload)

        git_info = result.get("git_info")
        assert "auth.py" in git_info or str(f) in git_info
        entry = list(git_info.values())[0]
        assert "last_modified" in entry
        assert "last_author" in entry
        assert "commit_count" in entry
        assert entry["commit_count"] >= 1
        assert entry["last_author"] == "Test User"

    def test_untracked_file_gets_none_info(self, tmp_path):
        """Files not in git get null/default git info."""
        _init_repo(tmp_path)
        # Create file but don't commit
        f = tmp_path / "new.py"
        f.write_text("class New:\n    def call(self, p): ...\n")

        comps = [_comp("New", "new", file_path=str(f))]
        payload = Payload({"components": comps, "directory": str(tmp_path)})
        result = GitHistory().call(payload)

        entry = list(result.get("git_info").values())[0]
        assert entry["commit_count"] == 0
        assert entry["last_modified"] is None

    def test_non_git_repo_graceful(self, tmp_path):
        """If directory is not a git repo, git_info is empty."""
        f = tmp_path / "auth.py"
        f.write_text("class Auth:\n    def call(self, p): ...\n")

        comps = [_comp("Auth", "auth", file_path=str(f))]
        payload = Payload({"components": comps, "directory": str(tmp_path)})
        result = GitHistory().call(payload)

        assert result.get("git_info") == {}

    def test_days_since_change_computed(self, tmp_path):
        """Each file entry should have days_since_change >= 0."""
        _init_repo(tmp_path)
        f = tmp_path / "auth.py"
        f.write_text("class Auth:\n    def call(self, p): ...\n")
        _git(["add", "."], tmp_path)
        _git(["commit", "-m", "init"], tmp_path)

        comps = [_comp("Auth", "auth", file_path=str(f))]
        payload = Payload({"components": comps, "directory": str(tmp_path)})
        result = GitHistory().call(payload)

        entry = list(result.get("git_info").values())[0]
        assert "days_since_change" in entry
        assert entry["days_since_change"] >= 0

    def test_empty_components(self, tmp_path):
        _init_repo(tmp_path)
        payload = Payload({"components": [], "directory": str(tmp_path)})
        result = GitHistory().call(payload)
        assert result.get("git_info") == {}

    def test_multiple_files(self, tmp_path):
        """Multiple component files each get their own git info."""
        _init_repo(tmp_path)
        f1 = tmp_path / "a.py"
        f1.write_text("class A:\n    def call(self, p): ...\n")
        f2 = tmp_path / "b.py"
        f2.write_text("class B:\n    def call(self, p): ...\n")
        _git(["add", "."], tmp_path)
        _git(["commit", "-m", "init"], tmp_path)

        comps = [
            _comp("A", "a", file_path=str(f1)),
            _comp("B", "b", file_path=str(f2)),
        ]
        payload = Payload({"components": comps, "directory": str(tmp_path)})
        result = GitHistory().call(payload)

        git_info = result.get("git_info")
        assert len(git_info) == 2

    def test_test_files_included_when_present(self, tmp_path):
        """test_map file entries also get git history."""
        _init_repo(tmp_path)
        comp_dir = tmp_path / "src"
        comp_dir.mkdir()
        f = comp_dir / "auth.py"
        f.write_text("class Auth:\n    def call(self, p): ...\n")
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        tf = tests_dir / "test_auth.py"
        tf.write_text("def test_a(): ...\n")
        _git(["add", "."], tmp_path)
        _git(["commit", "-m", "init"], tmp_path)

        comps = [_comp("Auth", "auth", file_path=str(f))]
        test_map = [{"test_file": str(tf), "stem": "auth", "test_methods": ["test_a"],
                      "imports": set(), "referenced_methods": set()}]
        payload = Payload({
            "components": comps,
            "test_map": test_map,
            "directory": str(tmp_path),
        })
        result = GitHistory().call(payload)

        git_info = result.get("git_info")
        # Should have git info for both the component file and the test file
        assert len(git_info) >= 2
