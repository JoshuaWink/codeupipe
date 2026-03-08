"""Tests for codeupipe.auth.vault_hook — VaultHook pipeline integration.

Covers:
- Injects proxy token into payload at pipeline start
- Does NOT inject before individual filters
- Auto-revokes all tokens at pipeline end
- Auto-revokes on error
- Configurable token_key
- Configurable TTL and scope_level
- Integration with Pipeline (end-to-end)
"""

import asyncio
import time
import tempfile
from pathlib import Path
from typing import Optional
from unittest.mock import MagicMock

import pytest

from codeupipe.core.payload import Payload
from codeupipe.core.pipeline import Pipeline
from codeupipe.core.filter import Filter
from codeupipe.core.hook import Hook
from codeupipe.auth.credential import Credential, CredentialStore
from codeupipe.auth.token_vault import TokenVault
from codeupipe.auth.token_ledger import TokenLedger
from codeupipe.auth.vault_hook import VaultHook


# ── Helpers ──────────────────────────────────────────────────


def _make_vault(tmp_path, provider="google", access_token="ya29.REAL_TOKEN"):
    """Create a vault with a fake credential."""
    store = CredentialStore(str(tmp_path / "creds.json"))
    store.save(Credential(
        provider=provider,
        access_token=access_token,
        refresh_token="1//REFRESH",
        expiry=time.time() + 3600,
        scopes=["email"],
    ))
    ledger = TokenLedger()
    vault = TokenVault(store, ledger=ledger)
    return vault, ledger


class EchoFilter(Filter):
    """Filter that copies the token key into echo_token for test verification."""
    def __init__(self, token_key="access_token"):
        self._key = token_key

    async def call(self, payload: Payload) -> Payload:
        val = payload.get(self._key) or "missing"
        return payload.insert("echo_token", val)


class FailingFilter(Filter):
    """Filter that always raises."""
    async def call(self, payload: Payload) -> Payload:
        raise RuntimeError("intentional failure")


# ── Before (injection) ───────────────────────────────────────


class TestVaultHookBefore:
    """VaultHook.before() injects a proxy token into the payload."""

    def test_injects_proxy_token_at_pipeline_start(self, tmp_path):
        """When filter=None (pipeline start), a cup_tok_ is injected."""
        vault, _ = _make_vault(tmp_path)
        hook = VaultHook(vault, "google")
        payload = Payload({"input": "data"})

        asyncio.run(hook.before(None, payload))

        token = payload.get("access_token")
        assert token is not None
        assert token.startswith("cup_tok_")

    def test_does_not_inject_before_individual_filter(self, tmp_path):
        """When filter is provided (before a specific filter), no injection."""
        vault, _ = _make_vault(tmp_path)
        hook = VaultHook(vault, "google")
        payload = Payload({"input": "data"})
        mock_filter = MagicMock()

        asyncio.run(hook.before(mock_filter, payload))

        assert payload.get("access_token") is None

    def test_custom_token_key(self, tmp_path):
        """Token is injected under the configured key."""
        vault, _ = _make_vault(tmp_path)
        hook = VaultHook(vault, "google", token_key="google_token")
        payload = Payload({"input": "data"})

        asyncio.run(hook.before(None, payload))

        assert payload.get("google_token", "").startswith("cup_tok_")
        assert payload.get("access_token") is None

    def test_injects_provider_name(self, tmp_path):
        """Provider name is injected alongside the token."""
        vault, _ = _make_vault(tmp_path)
        hook = VaultHook(vault, "google")
        payload = Payload({})

        asyncio.run(hook.before(None, payload))

        assert payload.get("auth_provider") == "google"

    def test_configurable_ttl(self, tmp_path):
        """Proxy token uses the configured TTL."""
        vault, _ = _make_vault(tmp_path)
        hook = VaultHook(vault, "google", ttl=120)
        payload = Payload({})

        asyncio.run(hook.before(None, payload))

        token_str = payload.get("access_token")
        # Verify the vault issued with that TTL
        proxy = vault._tokens.get(token_str)
        assert proxy is not None
        assert proxy.ttl == 120

    def test_configurable_scope_level(self, tmp_path):
        """Proxy token uses the configured scope level."""
        vault, _ = _make_vault(tmp_path)
        hook = VaultHook(vault, "google", scope_level="single-use", max_uses=1)
        payload = Payload({})

        asyncio.run(hook.before(None, payload))

        token_str = payload.get("access_token")
        proxy = vault._tokens.get(token_str)
        assert proxy.scope_level == "single-use"
        assert proxy.max_uses == 1


# ── After (cleanup) ─────────────────────────────────────────


class TestVaultHookAfter:
    """VaultHook.after() revokes all tokens at pipeline end."""

    def test_revokes_all_at_pipeline_end(self, tmp_path):
        """When filter=None (pipeline end), all tokens for this provider are revoked."""
        vault, _ = _make_vault(tmp_path)
        hook = VaultHook(vault, "google")
        payload = Payload({})

        # Simulate pipeline lifecycle
        asyncio.run(hook.before(None, payload))
        assert vault.active_count() == 1

        asyncio.run(hook.after(None, payload))
        assert vault.active_count() == 0

    def test_does_not_revoke_after_individual_filter(self, tmp_path):
        """When filter is provided, no revocation happens."""
        vault, _ = _make_vault(tmp_path)
        hook = VaultHook(vault, "google")
        payload = Payload({})

        asyncio.run(hook.before(None, payload))
        assert vault.active_count() == 1

        mock_filter = MagicMock()
        asyncio.run(hook.after(mock_filter, payload))
        assert vault.active_count() == 1  # still active


# ── On Error (cleanup) ──────────────────────────────────────


class TestVaultHookOnError:
    """VaultHook.on_error() revokes tokens on pipeline failure."""

    def test_revokes_on_error(self, tmp_path):
        """Tokens are revoked when the pipeline hits an error."""
        vault, _ = _make_vault(tmp_path)
        hook = VaultHook(vault, "google")
        payload = Payload({})

        asyncio.run(hook.before(None, payload))
        assert vault.active_count() == 1

        asyncio.run(hook.on_error(None, RuntimeError("boom"), payload))
        assert vault.active_count() == 0


# ── Pipeline Integration ────────────────────────────────────


class TestVaultHookPipelineIntegration:
    """VaultHook works end-to-end inside a real Pipeline."""

    def test_filter_sees_proxy_token(self, tmp_path):
        """A filter in the pipeline sees the proxy token, not the real one."""
        vault, _ = _make_vault(tmp_path, access_token="ya29.SECRET_REAL_TOKEN")
        hook = VaultHook(vault, "google")

        pipe = Pipeline()
        pipe.use_hook(hook)
        pipe.add_filter(EchoFilter(), "echo")

        result = asyncio.run(pipe.run(Payload({"input": "test"})))

        echoed = result.get("echo_token")
        assert echoed.startswith("cup_tok_")
        assert "ya29" not in echoed
        assert "SECRET" not in echoed

    def test_tokens_revoked_after_pipeline_completes(self, tmp_path):
        """All proxy tokens are revoked after the pipeline finishes."""
        vault, _ = _make_vault(tmp_path)
        hook = VaultHook(vault, "google")

        pipe = Pipeline()
        pipe.use_hook(hook)
        pipe.add_filter(EchoFilter(), "echo")

        asyncio.run(pipe.run(Payload({})))

        assert vault.active_count() == 0

    def test_tokens_revoked_after_pipeline_error(self, tmp_path):
        """Proxy tokens are revoked even when the pipeline fails."""
        vault, _ = _make_vault(tmp_path)
        hook = VaultHook(vault, "google")

        pipe = Pipeline()
        pipe.use_hook(hook)
        pipe.add_filter(FailingFilter(), "fail")

        with pytest.raises(RuntimeError, match="intentional"):
            asyncio.run(pipe.run(Payload({})))

        assert vault.active_count() == 0

    def test_ledger_records_full_lifecycle(self, tmp_path):
        """Ledger captures issued + revoked events for a complete pipeline run."""
        vault, ledger = _make_vault(tmp_path)
        hook = VaultHook(vault, "google")

        pipe = Pipeline()
        pipe.use_hook(hook)
        pipe.add_filter(EchoFilter(), "echo")

        asyncio.run(pipe.run(Payload({})))

        issued = ledger.events(event="issued")
        revoked = ledger.events(event="revoked")
        assert len(issued) == 1
        assert len(revoked) == 1
        assert issued[0].token == revoked[0].token
