"""Tests for codeupipe.auth.token_vault — TokenVault engine.

Covers:
- Issuing proxy tokens from real credentials
- Resolving proxy tokens back to real credentials
- Rejecting expired tokens
- Rejecting revoked tokens
- Rejecting exhausted tokens (single-use, max_uses)
- Revoking tokens
- Revoking all tokens for a provider
- Revoking all tokens (pipeline end cleanup)
- Audit trail integration (ledger receives events)
- Listing active tokens
"""

import time

import pytest

from codeupipe.auth.credential import Credential, CredentialStore
from codeupipe.auth.proxy_token import ProxyToken
from codeupipe.auth.token_ledger import TokenLedger
from codeupipe.auth.token_vault import TokenVault


# ── Helpers ──────────────────────────────────────────────────


def _make_store(tmp_path):
    """Create a CredentialStore with a fake Google credential."""
    store = CredentialStore(str(tmp_path / "creds.json"))
    cred = Credential(
        provider="google",
        access_token="ya29.REAL_GOOGLE_TOKEN",
        refresh_token="1//REAL_REFRESH_TOKEN",
        expiry=time.time() + 3600,
        scopes=["email", "calendar"],
    )
    store.save(cred)
    return store


def _make_github_store(tmp_path):
    """Create a CredentialStore with fake Google + GitHub credentials."""
    store = CredentialStore(str(tmp_path / "creds.json"))
    store.save(Credential(
        provider="google",
        access_token="ya29.REAL_GOOGLE_TOKEN",
        refresh_token="1//REAL_REFRESH",
        expiry=time.time() + 3600,
        scopes=["email"],
    ))
    store.save(Credential(
        provider="github",
        access_token="gho_REAL_GITHUB_TOKEN",
        expiry=0,  # GitHub tokens don't expire
        scopes=["repo", "user"],
    ))
    return store


# ── Issue ────────────────────────────────────────────────────


class TestTokenVaultIssue:
    """TokenVault.issue() creates proxy tokens backed by real credentials."""

    def test_issue_returns_proxy_token(self, tmp_path):
        """Issuing returns a ProxyToken with cup_tok_ prefix."""
        store = _make_store(tmp_path)
        vault = TokenVault(store)
        tok = vault.issue("google", scopes=["email"], ttl=600)
        assert isinstance(tok, ProxyToken)
        assert tok.token.startswith("cup_tok_")

    def test_issue_records_provider(self, tmp_path):
        """Issued token records which provider it proxies."""
        store = _make_store(tmp_path)
        vault = TokenVault(store)
        tok = vault.issue("google", scopes=["email"], ttl=600)
        assert tok.provider == "google"

    def test_issue_fails_without_credential(self, tmp_path):
        """Issuing for an unknown provider raises an error."""
        store = _make_store(tmp_path)
        vault = TokenVault(store)
        with pytest.raises(RuntimeError, match="No credential"):
            vault.issue("stripe", scopes=["charges"], ttl=600)

    def test_issue_logs_to_ledger(self, tmp_path):
        """Issuing a token creates a ledger event."""
        store = _make_store(tmp_path)
        ledger = TokenLedger()
        vault = TokenVault(store, ledger=ledger)
        tok = vault.issue("google", scopes=["email"], ttl=600)
        events = ledger.events(event="issued")
        assert len(events) == 1
        assert events[0].token == tok.token

    def test_issue_with_scope_level(self, tmp_path):
        """Token inherits the requested scope level."""
        store = _make_store(tmp_path)
        vault = TokenVault(store)
        tok = vault.issue("google", scopes=["email"], ttl=600, scope_level="single-use", max_uses=1)
        assert tok.scope_level == "single-use"
        assert tok.max_uses == 1


# ── Resolve ──────────────────────────────────────────────────


class TestTokenVaultResolve:
    """TokenVault.resolve() maps a proxy token back to the real credential."""

    def test_resolve_returns_real_credential(self, tmp_path):
        """Resolving a valid proxy token returns the real access token."""
        store = _make_store(tmp_path)
        vault = TokenVault(store)
        tok = vault.issue("google", scopes=["email"], ttl=600)
        cred = vault.resolve(tok.token)
        assert cred.access_token == "ya29.REAL_GOOGLE_TOKEN"
        assert cred.provider == "google"

    def test_resolve_increments_usage(self, tmp_path):
        """Each resolution increments the proxy token's usage counter."""
        store = _make_store(tmp_path)
        vault = TokenVault(store)
        tok = vault.issue("google", scopes=["email"], ttl=600)
        vault.resolve(tok.token)
        vault.resolve(tok.token)
        assert tok.usage_count == 2

    def test_resolve_logs_to_ledger(self, tmp_path):
        """Resolution creates a ledger event."""
        store = _make_store(tmp_path)
        ledger = TokenLedger()
        vault = TokenVault(store, ledger=ledger)
        tok = vault.issue("google", scopes=["email"], ttl=600)
        vault.resolve(tok.token)
        events = ledger.events(event="resolved")
        assert len(events) == 1

    def test_resolve_unknown_token_fails(self, tmp_path):
        """Resolving an unrecognized token raises an error."""
        store = _make_store(tmp_path)
        vault = TokenVault(store)
        with pytest.raises(KeyError, match="Unknown proxy token"):
            vault.resolve("cup_tok_nonexistent")

    def test_resolve_expired_token_fails(self, tmp_path):
        """Resolving an expired proxy token raises an error."""
        store = _make_store(tmp_path)
        vault = TokenVault(store)
        tok = vault.issue("google", scopes=["email"], ttl=0)  # immediately expired
        with pytest.raises(RuntimeError, match="expired"):
            vault.resolve(tok.token)

    def test_resolve_revoked_token_fails(self, tmp_path):
        """Resolving a revoked proxy token raises an error."""
        store = _make_store(tmp_path)
        vault = TokenVault(store)
        tok = vault.issue("google", scopes=["email"], ttl=600)
        vault.revoke(tok.token)
        with pytest.raises(RuntimeError, match="revoked"):
            vault.resolve(tok.token)

    def test_resolve_exhausted_token_fails(self, tmp_path):
        """Resolving a single-use token after it's been used raises an error."""
        store = _make_store(tmp_path)
        vault = TokenVault(store)
        tok = vault.issue("google", scopes=["email"], ttl=600, scope_level="single-use", max_uses=1)
        vault.resolve(tok.token)  # first use is fine
        with pytest.raises(RuntimeError, match="exhausted"):
            vault.resolve(tok.token)  # second use fails

    def test_real_token_never_in_proxy(self, tmp_path):
        """The proxy token string never contains the real token."""
        store = _make_store(tmp_path)
        vault = TokenVault(store)
        tok = vault.issue("google", scopes=["email"], ttl=600)
        assert "ya29" not in tok.token
        assert "REAL" not in tok.token


# ── Revoke ───────────────────────────────────────────────────


class TestTokenVaultRevoke:
    """TokenVault.revoke() invalidates proxy tokens."""

    def test_revoke_single_token(self, tmp_path):
        """Revoking a token makes it unresolvable."""
        store = _make_store(tmp_path)
        vault = TokenVault(store)
        tok = vault.issue("google", scopes=["email"], ttl=600)
        vault.revoke(tok.token)
        assert tok.revoked is True

    def test_revoke_logs_to_ledger(self, tmp_path):
        """Revoking creates a ledger event."""
        store = _make_store(tmp_path)
        ledger = TokenLedger()
        vault = TokenVault(store, ledger=ledger)
        tok = vault.issue("google", scopes=["email"], ttl=600)
        vault.revoke(tok.token)
        events = ledger.events(event="revoked")
        assert len(events) == 1

    def test_revoke_all_for_provider(self, tmp_path):
        """Revoke all tokens for a specific provider."""
        store = _make_github_store(tmp_path)
        vault = TokenVault(store)
        tok_g1 = vault.issue("google", scopes=["email"], ttl=600)
        tok_g2 = vault.issue("google", scopes=["calendar"], ttl=600)
        tok_h = vault.issue("github", scopes=["repo"], ttl=600)

        revoked_count = vault.revoke_all(provider="google")
        assert revoked_count == 2
        assert tok_g1.revoked is True
        assert tok_g2.revoked is True
        assert tok_h.revoked is False  # GitHub untouched

    def test_revoke_all(self, tmp_path):
        """Revoke all active tokens (pipeline end cleanup)."""
        store = _make_github_store(tmp_path)
        vault = TokenVault(store)
        tok_g = vault.issue("google", scopes=["email"], ttl=600)
        tok_h = vault.issue("github", scopes=["repo"], ttl=600)

        revoked_count = vault.revoke_all()
        assert revoked_count == 2
        assert tok_g.revoked is True
        assert tok_h.revoked is True

    def test_revoke_unknown_token_is_noop(self, tmp_path):
        """Revoking an unknown token does not raise."""
        store = _make_store(tmp_path)
        vault = TokenVault(store)
        vault.revoke("cup_tok_nonexistent")  # no error


# ── Active Tokens ────────────────────────────────────────────


class TestTokenVaultActiveTokens:
    """TokenVault tracks which proxy tokens are currently active."""

    def test_list_active_tokens(self, tmp_path):
        """Active tokens are listed."""
        store = _make_store(tmp_path)
        vault = TokenVault(store)
        tok = vault.issue("google", scopes=["email"], ttl=600)
        active = vault.active_tokens()
        assert len(active) == 1
        assert active[0].token == tok.token

    def test_revoked_tokens_not_in_active(self, tmp_path):
        """Revoked tokens are not listed as active."""
        store = _make_store(tmp_path)
        vault = TokenVault(store)
        tok = vault.issue("google", scopes=["email"], ttl=600)
        vault.revoke(tok.token)
        assert vault.active_tokens() == []

    def test_expired_tokens_not_in_active(self, tmp_path):
        """Expired tokens are not listed as active."""
        store = _make_store(tmp_path)
        vault = TokenVault(store)
        vault.issue("google", scopes=["email"], ttl=0)  # immediately expired
        assert vault.active_tokens() == []

    def test_active_count(self, tmp_path):
        """Active count reflects only valid tokens."""
        store = _make_store(tmp_path)
        vault = TokenVault(store)
        vault.issue("google", scopes=["email"], ttl=600)
        vault.issue("google", scopes=["calendar"], ttl=600)
        tok3 = vault.issue("google", scopes=["drive"], ttl=600)
        vault.revoke(tok3.token)
        assert vault.active_count() == 2
