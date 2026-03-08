"""Tests for codeupipe.auth.proxy_token — ProxyToken value object.

Covers:
- Creation with cup_tok_ prefix
- TTL and expiry tracking
- Scope enforcement
- Scope level (run, session, persistent, single-use)
- Serialization round-trip
- Usage counting
- Revocation flag
"""

import time

import pytest

from codeupipe.auth.proxy_token import ProxyToken


# ── Creation ─────────────────────────────────────────────────


class TestProxyTokenCreation:
    """ProxyToken is an opaque reference to a real credential."""

    def test_token_has_cup_prefix(self):
        """All proxy tokens start with 'cup_tok_'."""
        tok = ProxyToken.issue(provider="google", scopes=["email"], ttl=600)
        assert tok.token.startswith("cup_tok_")

    def test_token_is_unique(self):
        """Two issued tokens are never the same."""
        a = ProxyToken.issue(provider="google", scopes=["email"], ttl=600)
        b = ProxyToken.issue(provider="google", scopes=["email"], ttl=600)
        assert a.token != b.token

    def test_stores_provider(self):
        """Token records which provider it proxies."""
        tok = ProxyToken.issue(provider="github", scopes=["repo"], ttl=300)
        assert tok.provider == "github"

    def test_stores_scopes(self):
        """Token records the allowed scopes."""
        tok = ProxyToken.issue(provider="google", scopes=["email", "calendar"], ttl=600)
        assert tok.scopes == ["email", "calendar"]

    def test_empty_scopes_allowed(self):
        """Token can be issued with no scopes (provider-level access)."""
        tok = ProxyToken.issue(provider="google", scopes=[], ttl=600)
        assert tok.scopes == []

    def test_stores_scope_level(self):
        """Token records the scope level (run, session, persistent, single-use)."""
        tok = ProxyToken.issue(
            provider="google", scopes=["email"], ttl=600, scope_level="session"
        )
        assert tok.scope_level == "session"

    def test_default_scope_level_is_run(self):
        """Default scope level is 'run' — safest default."""
        tok = ProxyToken.issue(provider="google", scopes=["email"], ttl=600)
        assert tok.scope_level == "run"

    def test_invalid_scope_level_rejected(self):
        """Only valid scope levels are accepted."""
        with pytest.raises(ValueError, match="scope_level"):
            ProxyToken.issue(
                provider="google", scopes=["email"], ttl=600, scope_level="forever"
            )


# ── TTL & Expiry ─────────────────────────────────────────────


class TestProxyTokenExpiry:
    """ProxyToken has its own TTL, separate from the real credential."""

    def test_not_expired_within_ttl(self):
        """Token is valid within its TTL."""
        tok = ProxyToken.issue(provider="google", scopes=["email"], ttl=600)
        assert tok.expired is False

    def test_expired_after_ttl(self):
        """Token is expired after its TTL elapses."""
        tok = ProxyToken.issue(provider="google", scopes=["email"], ttl=0)
        # TTL=0 means immediately expired
        assert tok.expired is True

    def test_issued_at_recorded(self):
        """Token records when it was issued."""
        before = time.time()
        tok = ProxyToken.issue(provider="google", scopes=["email"], ttl=600)
        after = time.time()
        assert before <= tok.issued_at <= after

    def test_expires_at_computed(self):
        """expires_at = issued_at + ttl."""
        tok = ProxyToken.issue(provider="google", scopes=["email"], ttl=600)
        assert abs(tok.expires_at - (tok.issued_at + 600)) < 0.01

    def test_ttl_stored(self):
        """TTL value is accessible."""
        tok = ProxyToken.issue(provider="google", scopes=["email"], ttl=300)
        assert tok.ttl == 300


# ── Usage Tracking ───────────────────────────────────────────


class TestProxyTokenUsage:
    """ProxyToken tracks how many times it has been resolved."""

    def test_initial_usage_is_zero(self):
        """A freshly issued token has zero uses."""
        tok = ProxyToken.issue(provider="google", scopes=["email"], ttl=600)
        assert tok.usage_count == 0

    def test_record_usage_increments(self):
        """Each call to record_usage increments the counter."""
        tok = ProxyToken.issue(provider="google", scopes=["email"], ttl=600)
        tok.record_usage()
        assert tok.usage_count == 1
        tok.record_usage()
        assert tok.usage_count == 2

    def test_single_use_limit(self):
        """A single-use token can only be used once."""
        tok = ProxyToken.issue(
            provider="google", scopes=["email"], ttl=600,
            scope_level="single-use", max_uses=1,
        )
        assert tok.exhausted is False
        tok.record_usage()
        assert tok.exhausted is True

    def test_multi_use_limit(self):
        """Token respects a custom max_uses limit."""
        tok = ProxyToken.issue(
            provider="google", scopes=["email"], ttl=600, max_uses=3,
        )
        tok.record_usage()
        tok.record_usage()
        assert tok.exhausted is False
        tok.record_usage()
        assert tok.exhausted is True

    def test_unlimited_uses_by_default(self):
        """When max_uses is None, token never exhausts from usage."""
        tok = ProxyToken.issue(provider="google", scopes=["email"], ttl=600)
        for _ in range(1000):
            tok.record_usage()
        assert tok.exhausted is False


# ── Revocation ───────────────────────────────────────────────


class TestProxyTokenRevocation:
    """ProxyToken can be explicitly revoked."""

    def test_not_revoked_by_default(self):
        """A fresh token is not revoked."""
        tok = ProxyToken.issue(provider="google", scopes=["email"], ttl=600)
        assert tok.revoked is False

    def test_revoke_marks_token(self):
        """Calling revoke() flags the token as revoked."""
        tok = ProxyToken.issue(provider="google", scopes=["email"], ttl=600)
        tok.revoke()
        assert tok.revoked is True

    def test_revoked_token_not_valid(self):
        """A revoked token is never valid, even if TTL hasn't expired."""
        tok = ProxyToken.issue(provider="google", scopes=["email"], ttl=600)
        tok.revoke()
        assert tok.valid is False

    def test_valid_requires_not_expired_not_revoked_not_exhausted(self):
        """Token is valid only when not expired, not revoked, and not exhausted."""
        tok = ProxyToken.issue(provider="google", scopes=["email"], ttl=600)
        assert tok.valid is True

        # Expired token
        tok_exp = ProxyToken.issue(provider="google", scopes=["email"], ttl=0)
        assert tok_exp.valid is False

        # Exhausted token
        tok_exh = ProxyToken.issue(
            provider="google", scopes=["email"], ttl=600, max_uses=1,
        )
        tok_exh.record_usage()
        assert tok_exh.valid is False


# ── Serialization ────────────────────────────────────────────


class TestProxyTokenSerialization:
    """ProxyToken serializes to dict for ledger storage."""

    def test_to_dict_round_trip(self):
        """Token can be serialized and deserialized."""
        original = ProxyToken.issue(
            provider="google", scopes=["email", "calendar"], ttl=600,
            scope_level="session", max_uses=10,
        )
        original.record_usage()
        data = original.to_dict()
        restored = ProxyToken.from_dict(data)

        assert restored.token == original.token
        assert restored.provider == original.provider
        assert restored.scopes == original.scopes
        assert restored.ttl == original.ttl
        assert restored.scope_level == original.scope_level
        assert restored.max_uses == original.max_uses
        assert restored.usage_count == original.usage_count
        assert restored.issued_at == original.issued_at
        assert restored.revoked == original.revoked

    def test_repr_shows_token_preview(self):
        """Repr shows truncated token and provider for debugging."""
        tok = ProxyToken.issue(provider="google", scopes=["email"], ttl=600)
        r = repr(tok)
        assert "google" in r
        assert "cup_tok_" in r
