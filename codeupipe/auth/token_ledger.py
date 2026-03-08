"""
TokenLedger — audit trail for proxy token lifecycle events.

Records every issue, resolve, and revoke event for forensic analysis,
compliance reporting, and usage monitoring. Operates in-memory with
optional file-backed persistence.

Zero external dependencies — stdlib only.
"""

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from .proxy_token import ProxyToken

__all__ = ["LedgerEvent", "TokenLedger"]


class LedgerEvent:
    """A single audit entry in the token ledger.

    Attributes:
        token: The proxy token string (cup_tok_*).
        event: Event type — 'issued', 'resolved', or 'revoked'.
        provider: OAuth provider name.
        timestamp: Unix timestamp of the event.
        metadata: Optional extra data (endpoint, scopes, etc.).
    """

    __slots__ = ("token", "event", "provider", "timestamp", "metadata")

    def __init__(
        self,
        token: str,
        event: str,
        provider: str,
        timestamp: float,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.token = token
        self.event = event
        self.provider = provider
        self.timestamp = timestamp
        self.metadata = metadata if metadata is not None else {}

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict."""
        return {
            "token": self.token,
            "event": self.event,
            "provider": self.provider,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LedgerEvent":
        """Deserialize from dict."""
        return cls(
            token=data["token"],
            event=data["event"],
            provider=data.get("provider", ""),
            timestamp=data.get("timestamp", 0),
            metadata=data.get("metadata", {}),
        )

    def __repr__(self) -> str:
        return f"LedgerEvent({self.event}, token={self.token[:16]}..., provider={self.provider!r})"


class TokenLedger:
    """Audit trail for proxy token lifecycle.

    Logs issued, resolved, and revoked events with timestamps and metadata.
    Supports in-memory operation or file-backed persistence.

    Args:
        path: Optional path to a JSON file for persistence.
              If None, operates purely in-memory.
    """

    def __init__(self, path: Optional[str] = None):
        self._path: Optional[Path] = Path(path) if path else None
        self._events: List[LedgerEvent] = []

    # ── Logging ──────────────────────────────────────────────

    def log_issued(self, proxy_token: ProxyToken, metadata: Optional[Dict[str, Any]] = None) -> None:
        """Record that a proxy token was issued."""
        meta = metadata if metadata is not None else {
            "scopes": proxy_token.scopes,
            "ttl": proxy_token.ttl,
            "scope_level": proxy_token.scope_level,
            "max_uses": proxy_token.max_uses,
        }
        self._events.append(LedgerEvent(
            token=proxy_token.token,
            event="issued",
            provider=proxy_token.provider,
            timestamp=time.time(),
            metadata=meta,
        ))

    def log_resolved(
        self,
        token: str,
        provider: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Record that a proxy token was resolved (used to access a real credential)."""
        self._events.append(LedgerEvent(
            token=token,
            event="resolved",
            provider=provider,
            timestamp=time.time(),
            metadata=metadata if metadata is not None else {},
        ))

    def log_revoked(
        self,
        token: str,
        provider: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Record that a proxy token was revoked."""
        self._events.append(LedgerEvent(
            token=token,
            event="revoked",
            provider=provider,
            timestamp=time.time(),
            metadata=metadata if metadata is not None else {},
        ))

    # ── Queries ──────────────────────────────────────────────

    def events(
        self,
        token: Optional[str] = None,
        provider: Optional[str] = None,
        event: Optional[str] = None,
    ) -> List[LedgerEvent]:
        """Return events matching all provided filters (AND logic).

        Args:
            token: Filter by proxy token string.
            provider: Filter by provider name.
            event: Filter by event type ('issued', 'resolved', 'revoked').

        Returns:
            List of matching events in chronological order.
        """
        result = self._events
        if token is not None:
            result = [e for e in result if e.token == token]
        if provider is not None:
            result = [e for e in result if e.provider == provider]
        if event is not None:
            result = [e for e in result if e.event == event]
        return result

    def count(self) -> int:
        """Total number of events in the ledger."""
        return len(self._events)

    # ── Persistence ──────────────────────────────────────────

    def save(self) -> None:
        """Persist events to disk. No-op if no path was configured."""
        if self._path is None:
            return
        self._path.parent.mkdir(parents=True, exist_ok=True)
        data = [e.to_dict() for e in self._events]
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
        tmp.rename(self._path)

    def load(self) -> None:
        """Load events from disk. No-op if file doesn't exist."""
        if self._path is None or not self._path.exists():
            return
        try:
            text = self._path.read_text(encoding="utf-8")
            raw = json.loads(text) if text.strip() else []
            self._events = [LedgerEvent.from_dict(d) for d in raw]
        except (json.JSONDecodeError, OSError):
            self._events = []
