"""
TokenVault — issues, resolves, and revokes CUP proxy tokens.

The vault is the central authority for token indirection. It maps
opaque ``cup_tok_*`` proxy tokens to real OAuth2 credentials stored
in a CredentialStore. Real tokens never leave the vault boundary.

Works in two modes:
- **Embedded**: In-process, direct access to CredentialStore.
- **Service**: Behind an HTTP API (VaultClient talks to this).

Zero external dependencies — stdlib only.
"""

import time
from typing import List, Optional

from .credential import Credential, CredentialStore
from .proxy_token import ProxyToken
from .token_ledger import TokenLedger

__all__ = ["TokenVault"]


class TokenVault:
    """Central authority for proxy token lifecycle.

    Issues proxy tokens backed by real credentials, resolves them
    at the API boundary, and tracks everything in the audit ledger.

    Args:
        store: CredentialStore containing real OAuth2 credentials.
        ledger: Optional TokenLedger for audit trail. If None, a
                transient in-memory ledger is created.
    """

    def __init__(self, store: CredentialStore, ledger: Optional[TokenLedger] = None):
        self._store = store
        self._ledger = ledger if ledger is not None else TokenLedger()
        self._tokens: dict = {}  # token_string → ProxyToken

    # ── Issue ────────────────────────────────────────────────

    def issue(
        self,
        provider: str,
        scopes: Optional[List[str]] = None,
        ttl: int = 600,
        scope_level: str = "run",
        max_uses: Optional[int] = None,
    ) -> ProxyToken:
        """Issue a proxy token backed by a real credential.

        Args:
            provider: OAuth provider name (must exist in the CredentialStore).
            scopes: Allowed API scopes for this proxy token.
            ttl: Time-to-live in seconds.
            scope_level: Lifetime scope — 'run', 'session', 'persistent', 'single-use'.
            max_uses: Maximum resolution count (None = unlimited).

        Returns:
            A freshly issued ProxyToken.

        Raises:
            RuntimeError: If no valid credential exists for the provider.
        """
        cred = self._store.get(provider, auto_refresh=True)
        if cred is None:
            raise RuntimeError(
                f"No credential for provider '{provider}' in the store. "
                f"Authenticate first (e.g. run the OAuth browser flow)."
            )

        proxy = ProxyToken.issue(
            provider=provider,
            scopes=scopes if scopes is not None else [],
            ttl=ttl,
            scope_level=scope_level,
            max_uses=max_uses,
        )
        self._tokens[proxy.token] = proxy
        self._ledger.log_issued(proxy)
        return proxy

    # ── Resolve ──────────────────────────────────────────────

    def resolve(self, token_string: str) -> Credential:
        """Resolve a proxy token to the real credential.

        This is the only path to the real token. Called at the API
        boundary — right before an HTTP call goes out.

        Args:
            token_string: The ``cup_tok_*`` proxy token string.

        Returns:
            The real Credential for the provider.

        Raises:
            KeyError: If the token is not recognized.
            RuntimeError: If the token is expired, revoked, or exhausted.
        """
        proxy = self._tokens.get(token_string)
        if proxy is None:
            raise KeyError(f"Unknown proxy token: {token_string[:20]}...")

        # Check validity before resolving
        if proxy.expired:
            raise RuntimeError(
                f"Proxy token {token_string[:20]}... has expired. "
                f"Issue a new one."
            )
        if proxy.revoked:
            raise RuntimeError(
                f"Proxy token {token_string[:20]}... has been revoked."
            )
        if proxy.exhausted:
            raise RuntimeError(
                f"Proxy token {token_string[:20]}... is exhausted "
                f"(max_uses={proxy.max_uses} reached)."
            )

        # Increment usage BEFORE fetching real credential
        proxy.record_usage()

        # Fetch the real credential from the store
        cred = self._store.get(proxy.provider, auto_refresh=True)
        if cred is None:
            raise RuntimeError(
                f"Real credential for '{proxy.provider}' has been removed from the store."
            )

        self._ledger.log_resolved(token_string, provider=proxy.provider)
        return cred

    # ── Revoke ───────────────────────────────────────────────

    def revoke(self, token_string: str) -> None:
        """Revoke a single proxy token.

        If the token is not recognized, this is a silent no-op
        (idempotent — safe to call multiple times or on cleanup).
        """
        proxy = self._tokens.get(token_string)
        if proxy is None:
            return
        proxy.revoke()
        self._ledger.log_revoked(token_string, provider=proxy.provider)

    def revoke_all(self, provider: Optional[str] = None) -> int:
        """Revoke all active proxy tokens, optionally filtered by provider.

        Args:
            provider: If set, only revoke tokens for this provider.
                      If None, revoke all active tokens.

        Returns:
            Number of tokens revoked.
        """
        count = 0
        for proxy in list(self._tokens.values()):
            if proxy.revoked:
                continue
            if provider is not None and proxy.provider != provider:
                continue
            proxy.revoke()
            self._ledger.log_revoked(proxy.token, provider=proxy.provider)
            count += 1
        return count

    # ── Queries ──────────────────────────────────────────────

    def active_tokens(self) -> List[ProxyToken]:
        """Return all currently valid (non-expired, non-revoked, non-exhausted) tokens."""
        return [t for t in self._tokens.values() if t.valid]

    def active_count(self) -> int:
        """Count of currently active proxy tokens."""
        return len(self.active_tokens())

    @property
    def ledger(self) -> TokenLedger:
        """Access the audit ledger."""
        return self._ledger
