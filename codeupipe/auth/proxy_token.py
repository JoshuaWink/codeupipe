"""
ProxyToken — opaque reference token issued by the CUP vault.

A ProxyToken is a short-lived, scoped, revocable token that replaces
real OAuth2 credentials inside Payload. Filters never see the actual
Google/GitHub/etc. token — they see a ``cup_tok_*`` reference that the
vault resolves at the API boundary.

This is a pure value object — no I/O, no dependencies beyond stdlib.
"""

import secrets
import time
from typing import Any, Dict, List, Optional

__all__ = ["ProxyToken"]

_VALID_SCOPE_LEVELS = frozenset({"run", "session", "persistent", "single-use"})
_TOKEN_PREFIX = "cup_tok_"


class ProxyToken:
    """Opaque proxy token — maps to a real credential inside the vault.

    Attributes:
        token: The opaque token string (cup_tok_<random>).
        provider: Which OAuth provider this proxies (e.g. 'google', 'github').
        scopes: Allowed API scopes.
        ttl: Time-to-live in seconds.
        scope_level: Lifetime scope — 'run', 'session', 'persistent', 'single-use'.
        max_uses: Maximum resolution count (None = unlimited).
        issued_at: Unix timestamp when the token was created.
        usage_count: How many times the token has been resolved.
        revoked: Whether the token has been explicitly revoked.
    """

    __slots__ = (
        "token", "provider", "scopes", "ttl", "scope_level",
        "max_uses", "issued_at", "_usage_count", "_revoked",
    )

    def __init__(
        self,
        token: str,
        provider: str,
        scopes: List[str],
        ttl: int,
        scope_level: str,
        max_uses: Optional[int],
        issued_at: float,
        usage_count: int = 0,
        revoked: bool = False,
    ):
        self.token = token
        self.provider = provider
        self.scopes = list(scopes)
        self.ttl = ttl
        self.scope_level = scope_level
        self.max_uses = max_uses
        self.issued_at = issued_at
        self._usage_count = usage_count
        self._revoked = revoked

    # ── Factory ──────────────────────────────────────────────

    @classmethod
    def issue(
        cls,
        provider: str,
        scopes: List[str],
        ttl: int,
        scope_level: str = "run",
        max_uses: Optional[int] = None,
    ) -> "ProxyToken":
        """Issue a new proxy token.

        Args:
            provider: OAuth provider name (e.g. 'google', 'github').
            scopes: Allowed API scopes for this token.
            ttl: Time-to-live in seconds (0 = immediately expired).
            scope_level: Lifetime scope — 'run', 'session', 'persistent', 'single-use'.
            max_uses: Maximum number of resolutions (None = unlimited).

        Returns:
            A freshly issued ProxyToken.

        Raises:
            ValueError: If scope_level is not one of the valid levels.
        """
        if scope_level not in _VALID_SCOPE_LEVELS:
            raise ValueError(
                f"Invalid scope_level {scope_level!r}. "
                f"Must be one of: {', '.join(sorted(_VALID_SCOPE_LEVELS))}"
            )
        token_id = secrets.token_urlsafe(24)
        return cls(
            token=f"{_TOKEN_PREFIX}{token_id}",
            provider=provider,
            scopes=scopes,
            ttl=ttl,
            scope_level=scope_level,
            max_uses=max_uses,
            issued_at=time.time(),
        )

    # ── Expiry ───────────────────────────────────────────────

    @property
    def expires_at(self) -> float:
        """Unix timestamp when this token expires."""
        return self.issued_at + self.ttl

    @property
    def expired(self) -> bool:
        """True if the token's TTL has elapsed."""
        return time.time() >= self.expires_at

    # ── Usage ────────────────────────────────────────────────

    @property
    def usage_count(self) -> int:
        """How many times this token has been resolved."""
        return self._usage_count

    def record_usage(self) -> None:
        """Increment the usage counter (called on each resolution)."""
        self._usage_count += 1

    @property
    def exhausted(self) -> bool:
        """True if the token has reached its max_uses limit."""
        if self.max_uses is None:
            return False
        return self._usage_count >= self.max_uses

    # ── Revocation ───────────────────────────────────────────

    @property
    def revoked(self) -> bool:
        """True if this token has been explicitly revoked."""
        return self._revoked

    def revoke(self) -> None:
        """Mark this token as revoked. Irreversible."""
        self._revoked = True

    # ── Validity ─────────────────────────────────────────────

    @property
    def valid(self) -> bool:
        """True only if not expired, not revoked, and not exhausted."""
        return not self.expired and not self.revoked and not self.exhausted

    # ── Serialization ────────────────────────────────────────

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict for ledger storage."""
        return {
            "token": self.token,
            "provider": self.provider,
            "scopes": self.scopes,
            "ttl": self.ttl,
            "scope_level": self.scope_level,
            "max_uses": self.max_uses,
            "issued_at": self.issued_at,
            "usage_count": self._usage_count,
            "revoked": self._revoked,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProxyToken":
        """Deserialize from dict."""
        return cls(
            token=data["token"],
            provider=data["provider"],
            scopes=data.get("scopes", []),
            ttl=data.get("ttl", 0),
            scope_level=data.get("scope_level", "run"),
            max_uses=data.get("max_uses"),
            issued_at=data.get("issued_at", 0),
            usage_count=data.get("usage_count", 0),
            revoked=data.get("revoked", False),
        )

    # ── Display ──────────────────────────────────────────────

    def __repr__(self) -> str:
        status = "valid" if self.valid else ("revoked" if self.revoked else "expired")
        preview = self.token[:16] + "..." if len(self.token) > 16 else self.token
        return f"ProxyToken({preview}, provider={self.provider!r}, status={status})"
