"""Tests for codeupipe.auth.token_ledger — TokenLedger audit trail.

Covers:
- Logging issued, resolved, revoked events
- Querying events by token
- Querying events by provider
- Querying events by event type
- File-backed persistence
- Chronological ordering
"""

import json
import tempfile
import time
from pathlib import Path

import pytest

from codeupipe.auth.proxy_token import ProxyToken
from codeupipe.auth.token_ledger import TokenLedger, LedgerEvent


# ── Helpers ──────────────────────────────────────────────────


def _make_token(provider="google", ttl=600):
    """Quick helper to issue a test token."""
    return ProxyToken.issue(provider=provider, scopes=["email"], ttl=ttl)


# ── LedgerEvent ─────────────────────────────────────────────


class TestLedgerEvent:
    """LedgerEvent is a single audit entry."""

    def test_create_event(self):
        """Event captures token, event type, and timestamp."""
        evt = LedgerEvent(
            token="cup_tok_abc", event="issued", provider="google",
            timestamp=1000.0,
        )
        assert evt.token == "cup_tok_abc"
        assert evt.event == "issued"
        assert evt.provider == "google"
        assert evt.timestamp == 1000.0

    def test_event_metadata(self):
        """Event can carry optional metadata dict."""
        evt = LedgerEvent(
            token="cup_tok_abc", event="resolved", provider="google",
            timestamp=1000.0, metadata={"endpoint": "/api/userinfo"},
        )
        assert evt.metadata["endpoint"] == "/api/userinfo"

    def test_event_to_dict(self):
        """Event serializes to dict."""
        evt = LedgerEvent(
            token="cup_tok_abc", event="issued", provider="google",
            timestamp=1234.0, metadata={"scopes": ["email"]},
        )
        d = evt.to_dict()
        assert d["token"] == "cup_tok_abc"
        assert d["event"] == "issued"
        assert d["provider"] == "google"
        assert d["timestamp"] == 1234.0
        assert d["metadata"]["scopes"] == ["email"]

    def test_event_from_dict(self):
        """Event deserializes from dict."""
        d = {
            "token": "cup_tok_xyz", "event": "revoked",
            "provider": "github", "timestamp": 5678.0, "metadata": {},
        }
        evt = LedgerEvent.from_dict(d)
        assert evt.token == "cup_tok_xyz"
        assert evt.event == "revoked"


# ── TokenLedger: In-Memory ───────────────────────────────────


class TestTokenLedgerInMemory:
    """TokenLedger tracks audit events for proxy tokens."""

    def test_empty_ledger(self):
        """A new ledger has no events."""
        ledger = TokenLedger()
        assert ledger.events() == []

    def test_log_issued(self):
        """Logging an issued event records it."""
        ledger = TokenLedger()
        tok = _make_token()
        ledger.log_issued(tok)
        events = ledger.events()
        assert len(events) == 1
        assert events[0].event == "issued"
        assert events[0].token == tok.token
        assert events[0].provider == "google"

    def test_log_resolved(self):
        """Logging a resolved event records usage."""
        ledger = TokenLedger()
        tok = _make_token()
        ledger.log_resolved(tok.token, provider="google", metadata={"url": "/api/test"})
        events = ledger.events()
        assert len(events) == 1
        assert events[0].event == "resolved"
        assert events[0].metadata["url"] == "/api/test"

    def test_log_revoked(self):
        """Logging a revoked event records it."""
        ledger = TokenLedger()
        tok = _make_token()
        ledger.log_revoked(tok.token, provider="google")
        events = ledger.events()
        assert len(events) == 1
        assert events[0].event == "revoked"

    def test_chronological_order(self):
        """Events are returned in chronological order."""
        ledger = TokenLedger()
        tok = _make_token()
        ledger.log_issued(tok)
        ledger.log_resolved(tok.token, provider="google")
        ledger.log_revoked(tok.token, provider="google")
        events = ledger.events()
        assert len(events) == 3
        assert events[0].event == "issued"
        assert events[1].event == "resolved"
        assert events[2].event == "revoked"
        assert events[0].timestamp <= events[1].timestamp <= events[2].timestamp

    def test_query_by_token(self):
        """Filter events by token string."""
        ledger = TokenLedger()
        tok_a = _make_token()
        tok_b = _make_token()
        ledger.log_issued(tok_a)
        ledger.log_issued(tok_b)
        ledger.log_resolved(tok_a.token, provider="google")

        events_a = ledger.events(token=tok_a.token)
        assert len(events_a) == 2  # issued + resolved
        assert all(e.token == tok_a.token for e in events_a)

    def test_query_by_provider(self):
        """Filter events by provider name."""
        ledger = TokenLedger()
        tok_g = _make_token(provider="google")
        tok_h = _make_token(provider="github")
        ledger.log_issued(tok_g)
        ledger.log_issued(tok_h)

        google_events = ledger.events(provider="google")
        assert len(google_events) == 1
        assert google_events[0].provider == "google"

    def test_query_by_event_type(self):
        """Filter events by event type."""
        ledger = TokenLedger()
        tok = _make_token()
        ledger.log_issued(tok)
        ledger.log_resolved(tok.token, provider="google")
        ledger.log_resolved(tok.token, provider="google")
        ledger.log_revoked(tok.token, provider="google")

        resolved = ledger.events(event="resolved")
        assert len(resolved) == 2

    def test_combined_filters(self):
        """Multiple filters combine with AND logic."""
        ledger = TokenLedger()
        tok_a = _make_token(provider="google")
        tok_b = _make_token(provider="github")
        ledger.log_issued(tok_a)
        ledger.log_issued(tok_b)
        ledger.log_resolved(tok_a.token, provider="google")

        result = ledger.events(token=tok_a.token, event="resolved")
        assert len(result) == 1
        assert result[0].event == "resolved"
        assert result[0].token == tok_a.token

    def test_count(self):
        """Ledger tracks total event count."""
        ledger = TokenLedger()
        tok = _make_token()
        assert ledger.count() == 0
        ledger.log_issued(tok)
        ledger.log_resolved(tok.token, provider="google")
        assert ledger.count() == 2


# ── TokenLedger: File-Backed ─────────────────────────────────


class TestTokenLedgerPersistence:
    """TokenLedger can persist events to a JSON file."""

    def test_save_and_load(self, tmp_path):
        """Events survive save/load cycle."""
        path = tmp_path / "ledger.json"
        ledger = TokenLedger(path=str(path))
        tok = _make_token()
        ledger.log_issued(tok)
        ledger.log_resolved(tok.token, provider="google")
        ledger.save()

        # Load into a fresh ledger
        ledger2 = TokenLedger(path=str(path))
        ledger2.load()
        events = ledger2.events()
        assert len(events) == 2
        assert events[0].event == "issued"
        assert events[1].event == "resolved"

    def test_load_missing_file_is_empty(self, tmp_path):
        """Loading from a nonexistent file yields an empty ledger."""
        path = tmp_path / "nonexistent.json"
        ledger = TokenLedger(path=str(path))
        ledger.load()
        assert ledger.events() == []

    def test_in_memory_mode_no_path(self):
        """A ledger without a path operates purely in-memory."""
        ledger = TokenLedger()
        tok = _make_token()
        ledger.log_issued(tok)
        assert ledger.count() == 1
        # save() should be a no-op, not an error
        ledger.save()
