"""
VaultHook — pipeline hook that injects proxy tokens instead of real credentials.

Drop-in replacement for AuthHook. Instead of putting real OAuth tokens
into the Payload, VaultHook issues a ``cup_tok_*`` proxy token via the
TokenVault. Filters see the proxy token; real tokens never leave the vault.

At pipeline end (or on error), all issued proxy tokens are auto-revoked.

Zero external dependencies — stdlib only.
"""

from typing import Optional, TypeVar, List

from ..core.hook import Hook
from ..core.payload import Payload
from ..core.filter import Filter
from .token_vault import TokenVault

__all__ = ["VaultHook"]

T = TypeVar("T")


class VaultHook(Hook):
    """Pipeline hook that injects proxy tokens from the vault.

    Before the pipeline starts (filter=None):
    - Issues a proxy token via the vault
    - Injects it into the Payload under ``token_key``
    - Also injects ``auth_provider``

    After the pipeline ends (filter=None) or on error:
    - Revokes all proxy tokens for the configured provider

    Args:
        vault: TokenVault to issue/resolve/revoke proxy tokens.
        provider: OAuth provider name (e.g. 'google', 'github').
        token_key: Payload key for the proxy token (default: 'access_token').
        ttl: Time-to-live for issued proxy tokens in seconds.
        scope_level: Lifetime scope — 'run', 'session', 'persistent', 'single-use'.
        max_uses: Maximum resolution count (None = unlimited).
        scopes: API scopes for the proxy token.
    """

    def __init__(
        self,
        vault: TokenVault,
        provider: str,
        token_key: str = "access_token",
        ttl: int = 600,
        scope_level: str = "run",
        max_uses: Optional[int] = None,
        scopes: Optional[List[str]] = None,
    ):
        self._vault = vault
        self._provider = provider
        self._token_key = token_key
        self._ttl = ttl
        self._scope_level = scope_level
        self._max_uses = max_uses
        self._scopes = scopes if scopes is not None else []

    async def before(self, filter: Optional[Filter], payload: Payload[T]) -> None:
        """Inject a proxy token at pipeline start."""
        # Only inject at pipeline start (filter=None), not before each filter
        if filter is not None:
            return

        proxy = self._vault.issue(
            provider=self._provider,
            scopes=self._scopes,
            ttl=self._ttl,
            scope_level=self._scope_level,
            max_uses=self._max_uses,
        )

        # Hook.before doesn't return payload, so mutate _data directly.
        # This matches the established pattern in AuthHook.
        payload._data[self._token_key] = proxy.token
        payload._data["auth_provider"] = self._provider

    async def after(self, filter: Optional[Filter], payload: Payload[T]) -> None:
        """Revoke all proxy tokens at pipeline end."""
        if filter is not None:
            return
        self._vault.revoke_all(provider=self._provider)

    async def on_error(self, filter: Optional[Filter], error: Exception, payload: Payload[T]) -> None:
        """Revoke all proxy tokens on pipeline error."""
        self._vault.revoke_all(provider=self._provider)
