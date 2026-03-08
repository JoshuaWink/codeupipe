"""
codeupipe.auth: OAuth2 credential management for pipelines.

Provides browser-based OAuth2 flows, persistent token storage,
automatic credential injection, and proxy token vaulting.
Zero external dependencies — stdlib only.

Core types:
- Credential: Token container (access_token, refresh_token, expiry, scopes)
- CredentialStore: Persist + refresh credentials — file-backed JSON
- AuthProvider: Protocol for OAuth2 flows (authorize_url, exchange_code, refresh)
- AuthHook: Pipeline Hook — injects fresh tokens into Payload before each run

Vault types (proxy token indirection):
- ProxyToken: Opaque reference token (cup_tok_*) — never exposes real credentials
- TokenLedger: Audit trail — issued, resolved, revoked events
- TokenVault: Central authority — issues, resolves, revokes proxy tokens
- VaultHook: Pipeline Hook — injects proxy tokens instead of real credentials

Built-in providers:
- GoogleOAuth: Google OAuth2 (Calendar, Drive, Gmail, etc.)
- GitHubOAuth: GitHub OAuth2 (repos, issues, actions, etc.)
"""

from .credential import Credential, CredentialStore
from .hook import AuthHook
from .provider import AuthProvider, GitHubOAuth, GoogleOAuth
from .proxy_token import ProxyToken
from .token_ledger import LedgerEvent, TokenLedger
from .token_vault import TokenVault
from .vault_hook import VaultHook

__all__ = [
    "AuthHook",
    "AuthProvider",
    "Credential",
    "CredentialStore",
    "GitHubOAuth",
    "GoogleOAuth",
    "LedgerEvent",
    "ProxyToken",
    "TokenLedger",
    "TokenVault",
    "VaultHook",
]
