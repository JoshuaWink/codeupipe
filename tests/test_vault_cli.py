"""Tests for ``cup vault`` CLI subcommands.

Covers:
- cup vault issue <provider>
- cup vault resolve <token>
- cup vault revoke <token>
- cup vault revoke-all [--provider <provider>]
- cup vault list
- cup vault status <token>
- cup vault help (no subcommand)

Uses tmp_path for CredentialStore isolation and capsys for output capture.
Calls ``main([...])`` directly — same pattern as test_auth.py.
"""

import json
import time
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from codeupipe.auth.credential import Credential, CredentialStore
from codeupipe.auth.proxy_token import ProxyToken


# ── Helpers ──────────────────────────────────────────────────


def _seed_store(tmp_path, provider="google"):
    """Create a CredentialStore with a valid credential for testing."""
    creds_file = str(tmp_path / "creds.json")
    store = CredentialStore(creds_file)
    store.save(Credential(
        provider=provider,
        access_token="ya29.real_token_value",
        refresh_token="1//refresh_token_value",
        expiry=time.time() + 3600,
        scopes=["email", "calendar"],
    ))
    return creds_file


def _seed_store_multi(tmp_path):
    """Seed store with both google and github credentials."""
    creds_file = str(tmp_path / "creds.json")
    store = CredentialStore(creds_file)
    store.save(Credential(
        provider="google",
        access_token="ya29.google_tok",
        refresh_token="1//gref",
        expiry=time.time() + 3600,
        scopes=["email"],
    ))
    store.save(Credential(
        provider="github",
        access_token="gho_github_tok",
        refresh_token=None,
        expiry=time.time() + 3600,
        scopes=["repo"],
    ))
    return creds_file


# ── cup vault (no subcommand) ────────────────────────────────


class TestVaultHelp:
    """cup vault without subcommand shows help."""

    def test_vault_no_subcommand_shows_help(self, capsys):
        from codeupipe.cli import main

        result = main(["vault"])
        captured = capsys.readouterr()
        output = captured.out + captured.err
        assert "issue" in output or "resolve" in output or result == 1


# ── cup vault issue ──────────────────────────────────────────


class TestVaultIssue:
    """cup vault issue <provider> emits an opaque proxy token."""

    def test_issue_prints_token(self, tmp_path, capsys):
        """Issue a proxy token for a valid provider and verify output."""
        creds_file = _seed_store(tmp_path)
        from codeupipe.cli import main

        result = main(["vault", "issue", "google", "--store", creds_file])
        captured = capsys.readouterr()
        assert result == 0
        assert "cup_tok_" in captured.out

    def test_issue_with_ttl(self, tmp_path, capsys):
        """Issue with explicit --ttl flag."""
        creds_file = _seed_store(tmp_path)
        from codeupipe.cli import main

        result = main(["vault", "issue", "google", "--store", creds_file, "--ttl", "120"])
        captured = capsys.readouterr()
        assert result == 0
        assert "cup_tok_" in captured.out

    def test_issue_with_scope_level(self, tmp_path, capsys):
        """Issue with explicit --scope-level flag."""
        creds_file = _seed_store(tmp_path)
        from codeupipe.cli import main

        result = main(["vault", "issue", "google", "--store", creds_file, "--scope-level", "session"])
        captured = capsys.readouterr()
        assert result == 0
        assert "cup_tok_" in captured.out

    def test_issue_with_max_uses(self, tmp_path, capsys):
        """Issue with --max-uses flag."""
        creds_file = _seed_store(tmp_path)
        from codeupipe.cli import main

        result = main(["vault", "issue", "google", "--store", creds_file, "--max-uses", "5"])
        captured = capsys.readouterr()
        assert result == 0
        assert "cup_tok_" in captured.out

    def test_issue_json_output(self, tmp_path, capsys):
        """Issue with --json flag produces parseable JSON."""
        creds_file = _seed_store(tmp_path)
        from codeupipe.cli import main

        result = main(["vault", "issue", "google", "--store", creds_file, "--json"])
        captured = capsys.readouterr()
        assert result == 0
        data = json.loads(captured.out)
        assert data["token"].startswith("cup_tok_")
        assert data["provider"] == "google"
        assert "ttl" in data
        assert "scope_level" in data

    def test_issue_unknown_provider(self, tmp_path, capsys):
        """Issue for a provider with no stored credential fails."""
        creds_file = _seed_store(tmp_path)
        from codeupipe.cli import main

        result = main(["vault", "issue", "myspace", "--store", creds_file])
        captured = capsys.readouterr()
        assert result == 1
        assert "error" in captured.err.lower() or "no credential" in captured.err.lower()

    def test_issue_empty_store(self, tmp_path, capsys):
        """Issue when no credentials exist at all."""
        creds_file = str(tmp_path / "empty.json")
        from codeupipe.cli import main

        result = main(["vault", "issue", "google", "--store", creds_file])
        captured = capsys.readouterr()
        assert result == 1


# ── cup vault resolve ────────────────────────────────────────


class TestVaultResolve:
    """cup vault resolve <token> resolves to credential info."""

    def test_resolve_valid_token(self, tmp_path, capsys):
        """Issue then resolve — shows credential status without leaking real token."""
        creds_file = _seed_store(tmp_path)
        from codeupipe.cli import main

        # Issue first
        result = main(["vault", "issue", "google", "--store", creds_file, "--json"])
        captured = capsys.readouterr()
        token_str = json.loads(captured.out)["token"]

        # Resolve
        result = main(["vault", "resolve", token_str, "--store", creds_file])
        captured = capsys.readouterr()
        assert result == 0
        assert "google" in captured.out
        # MUST NOT leak the real token
        assert "ya29.real_token_value" not in captured.out

    def test_resolve_json_output(self, tmp_path, capsys):
        """Resolve with --json returns structured info."""
        creds_file = _seed_store(tmp_path)
        from codeupipe.cli import main

        # Issue
        result = main(["vault", "issue", "google", "--store", creds_file, "--json"])
        captured = capsys.readouterr()
        token_str = json.loads(captured.out)["token"]

        # Resolve as JSON
        result = main(["vault", "resolve", token_str, "--store", creds_file, "--json"])
        captured = capsys.readouterr()
        assert result == 0
        data = json.loads(captured.out)
        assert data["provider"] == "google"
        assert data["valid"] is True
        # Real token MUST NOT appear
        assert "ya29.real_token_value" not in captured.out

    def test_resolve_unknown_token(self, tmp_path, capsys):
        """Resolve a token that was never issued fails."""
        creds_file = _seed_store(tmp_path)
        from codeupipe.cli import main

        result = main(["vault", "resolve", "cup_tok_bogus", "--store", creds_file])
        captured = capsys.readouterr()
        assert result == 1
        assert "unknown" in captured.err.lower() or "error" in captured.err.lower()

    def test_resolve_revoked_token(self, tmp_path, capsys):
        """Resolve a revoked token fails."""
        creds_file = _seed_store(tmp_path)
        from codeupipe.cli import main

        # Issue + revoke
        result = main(["vault", "issue", "google", "--store", creds_file, "--json"])
        captured = capsys.readouterr()
        token_str = json.loads(captured.out)["token"]

        main(["vault", "revoke", token_str, "--store", creds_file])

        # Try to resolve
        result = main(["vault", "resolve", token_str, "--store", creds_file])
        captured = capsys.readouterr()
        assert result == 1
        assert "revoked" in captured.err.lower() or "error" in captured.err.lower()


# ── cup vault revoke ─────────────────────────────────────────


class TestVaultRevoke:
    """cup vault revoke <token> revokes a single proxy token."""

    def test_revoke_valid_token(self, tmp_path, capsys):
        """Revoke an active token succeeds."""
        creds_file = _seed_store(tmp_path)
        from codeupipe.cli import main

        # Issue
        result = main(["vault", "issue", "google", "--store", creds_file, "--json"])
        captured = capsys.readouterr()
        token_str = json.loads(captured.out)["token"]

        # Revoke
        result = main(["vault", "revoke", token_str, "--store", creds_file])
        captured = capsys.readouterr()
        assert result == 0
        assert "revoked" in captured.out.lower()

    def test_revoke_unknown_token(self, tmp_path, capsys):
        """Revoke an unknown token is a silent success (idempotent)."""
        creds_file = _seed_store(tmp_path)
        from codeupipe.cli import main

        result = main(["vault", "revoke", "cup_tok_never_issued", "--store", creds_file])
        captured = capsys.readouterr()
        # Idempotent — should not be a hard error
        assert result == 0


# ── cup vault revoke-all ─────────────────────────────────────


class TestVaultRevokeAll:
    """cup vault revoke-all revokes all active tokens."""

    def test_revoke_all(self, tmp_path, capsys):
        """Revoke all tokens across all providers."""
        creds_file = _seed_store_multi(tmp_path)
        from codeupipe.cli import main

        # Issue for both providers
        main(["vault", "issue", "google", "--store", creds_file, "--json"])
        capsys.readouterr()
        main(["vault", "issue", "github", "--store", creds_file, "--json"])
        capsys.readouterr()

        # Revoke all
        result = main(["vault", "revoke-all", "--store", creds_file])
        captured = capsys.readouterr()
        assert result == 0
        assert "2" in captured.out  # should mention 2 revoked

    def test_revoke_all_by_provider(self, tmp_path, capsys):
        """Revoke all tokens for a specific provider only."""
        creds_file = _seed_store_multi(tmp_path)
        from codeupipe.cli import main

        # Issue for both
        main(["vault", "issue", "google", "--store", creds_file, "--json"])
        capsys.readouterr()
        main(["vault", "issue", "github", "--store", creds_file, "--json"])
        capsys.readouterr()

        # Revoke only google
        result = main(["vault", "revoke-all", "--provider", "google", "--store", creds_file])
        captured = capsys.readouterr()
        assert result == 0
        assert "1" in captured.out

    def test_revoke_all_empty(self, tmp_path, capsys):
        """Revoke-all with no active tokens returns 0."""
        creds_file = str(tmp_path / "empty.json")
        from codeupipe.cli import main

        result = main(["vault", "revoke-all", "--store", creds_file])
        captured = capsys.readouterr()
        assert result == 0
        assert "0" in captured.out


# ── cup vault list ───────────────────────────────────────────


class TestVaultList:
    """cup vault list shows all active proxy tokens."""

    def test_list_empty(self, tmp_path, capsys):
        """No active tokens prints informative message."""
        creds_file = str(tmp_path / "empty.json")
        from codeupipe.cli import main

        result = main(["vault", "list", "--store", creds_file])
        captured = capsys.readouterr()
        assert result == 0
        assert "no active" in captured.out.lower() or "0" in captured.out

    def test_list_shows_tokens(self, tmp_path, capsys):
        """List after issuing shows active token details."""
        creds_file = _seed_store(tmp_path)
        from codeupipe.cli import main

        # Issue
        main(["vault", "issue", "google", "--store", creds_file, "--json"])
        capsys.readouterr()

        # List
        result = main(["vault", "list", "--store", creds_file])
        captured = capsys.readouterr()
        assert result == 0
        assert "google" in captured.out
        assert "cup_tok_" in captured.out

    def test_list_json(self, tmp_path, capsys):
        """List with --json returns structured array."""
        creds_file = _seed_store(tmp_path)
        from codeupipe.cli import main

        main(["vault", "issue", "google", "--store", creds_file, "--json"])
        capsys.readouterr()

        result = main(["vault", "list", "--store", creds_file, "--json"])
        captured = capsys.readouterr()
        assert result == 0
        data = json.loads(captured.out)
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["provider"] == "google"


# ── cup vault status ─────────────────────────────────────────


class TestVaultStatus:
    """cup vault status <token> shows detailed info about one proxy token."""

    def test_status_active_token(self, tmp_path, capsys):
        """Status of a freshly issued token shows valid + metadata."""
        creds_file = _seed_store(tmp_path)
        from codeupipe.cli import main

        # Issue
        result = main(["vault", "issue", "google", "--store", creds_file, "--json"])
        captured = capsys.readouterr()
        token_str = json.loads(captured.out)["token"]

        # Status
        result = main(["vault", "status", token_str, "--store", creds_file])
        captured = capsys.readouterr()
        assert result == 0
        assert "valid" in captured.out.lower() or "active" in captured.out.lower()
        assert "google" in captured.out

    def test_status_json_output(self, tmp_path, capsys):
        """Status with --json returns structured detail."""
        creds_file = _seed_store(tmp_path)
        from codeupipe.cli import main

        result = main(["vault", "issue", "google", "--store", creds_file, "--json"])
        captured = capsys.readouterr()
        token_str = json.loads(captured.out)["token"]

        result = main(["vault", "status", token_str, "--store", creds_file, "--json"])
        captured = capsys.readouterr()
        assert result == 0
        data = json.loads(captured.out)
        assert data["provider"] == "google"
        assert "valid" in data or "status" in data
        assert "usage_count" in data

    def test_status_unknown_token(self, tmp_path, capsys):
        """Status for unknown token fails."""
        creds_file = _seed_store(tmp_path)
        from codeupipe.cli import main

        result = main(["vault", "status", "cup_tok_nope", "--store", creds_file])
        captured = capsys.readouterr()
        assert result == 1
        assert "unknown" in captured.err.lower() or "not found" in captured.err.lower()

    def test_status_revoked_token(self, tmp_path, capsys):
        """Status of a revoked token shows revoked state."""
        creds_file = _seed_store(tmp_path)
        from codeupipe.cli import main

        result = main(["vault", "issue", "google", "--store", creds_file, "--json"])
        captured = capsys.readouterr()
        token_str = json.loads(captured.out)["token"]

        main(["vault", "revoke", token_str, "--store", creds_file])
        capsys.readouterr()

        result = main(["vault", "status", token_str, "--store", creds_file])
        captured = capsys.readouterr()
        assert result == 0
        assert "revoked" in captured.out.lower()


# ── Cross-command Integration ────────────────────────────────


class TestVaultIntegration:
    """Multi-step workflows across vault subcommands."""

    def test_full_lifecycle(self, tmp_path, capsys):
        """issue → status → resolve → revoke → status (revoked)."""
        creds_file = _seed_store(tmp_path)
        from codeupipe.cli import main

        # 1. Issue
        result = main(["vault", "issue", "google", "--store", creds_file, "--json"])
        captured = capsys.readouterr()
        assert result == 0
        token_str = json.loads(captured.out)["token"]

        # 2. Status — active
        result = main(["vault", "status", token_str, "--store", creds_file])
        captured = capsys.readouterr()
        assert result == 0
        assert "valid" in captured.out.lower() or "active" in captured.out.lower()

        # 3. Resolve — success
        result = main(["vault", "resolve", token_str, "--store", creds_file])
        captured = capsys.readouterr()
        assert result == 0
        assert "ya29.real_token_value" not in captured.out

        # 4. Revoke
        result = main(["vault", "revoke", token_str, "--store", creds_file])
        captured = capsys.readouterr()
        assert result == 0

        # 5. Status — revoked
        result = main(["vault", "status", token_str, "--store", creds_file])
        captured = capsys.readouterr()
        assert result == 0
        assert "revoked" in captured.out.lower()

        # 6. Resolve — should fail
        result = main(["vault", "resolve", token_str, "--store", creds_file])
        captured = capsys.readouterr()
        assert result == 1

    def test_issue_multiple_then_list(self, tmp_path, capsys):
        """Issue several tokens, list shows them all."""
        creds_file = _seed_store_multi(tmp_path)
        from codeupipe.cli import main

        # Issue 2 for google, 1 for github
        for _ in range(2):
            main(["vault", "issue", "google", "--store", creds_file, "--json"])
            capsys.readouterr()
        main(["vault", "issue", "github", "--store", creds_file, "--json"])
        capsys.readouterr()

        # List as JSON
        result = main(["vault", "list", "--store", creds_file, "--json"])
        captured = capsys.readouterr()
        assert result == 0
        data = json.loads(captured.out)
        assert len(data) == 3
        providers = {t["provider"] for t in data}
        assert "google" in providers
        assert "github" in providers
