"""``cup vault`` command with sub-subcommands: issue, resolve, revoke, revoke-all, list, status.

Manages proxy token lifecycle from the terminal. Real credentials
never appear in CLI output — only opaque ``cup_tok_*`` references.

Vault state (issued proxy tokens) is persisted to a JSON file
alongside the credential store so that tokens survive across
invocations.
"""

import datetime
import json
import sys
from pathlib import Path
from typing import Optional

from .._registry import registry

_vault_parser = None  # stored for help fallback


# ── Vault State Persistence ──────────────────────────────────

def _vault_state_path(store_path: Optional[str]) -> Path:
    """Derive the vault state file from the credential store path."""
    if store_path:
        p = Path(store_path).expanduser()
        return p.parent / ".vault_state.json"
    return Path.home() / ".codeupipe" / ".vault_state.json"


def _load_vault(store_path: Optional[str]):
    """Build a TokenVault and restore persisted proxy tokens.

    Returns (vault, state_path) so the caller can persist after mutations.
    """
    from codeupipe.auth.credential import CredentialStore
    from codeupipe.auth.proxy_token import ProxyToken
    from codeupipe.auth.token_vault import TokenVault

    store = CredentialStore(store_path)
    vault = TokenVault(store)
    state_file = _vault_state_path(store_path)

    if state_file.exists():
        try:
            data = json.loads(state_file.read_text(encoding="utf-8"))
            for tok_data in data.get("tokens", []):
                proxy = ProxyToken.from_dict(tok_data)
                vault._tokens[proxy.token] = proxy
        except (json.JSONDecodeError, KeyError, OSError):
            pass  # corrupted state — start fresh

    return vault, state_file


def _save_vault(vault, state_file: Path) -> None:
    """Persist vault token registry to disk."""
    state_file.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "tokens": [t.to_dict() for t in vault._tokens.values()],
    }
    state_file.write_text(json.dumps(data, indent=2), encoding="utf-8")


# ── Parser Setup ─────────────────────────────────────────────

def setup(sub, reg):
    global _vault_parser
    vault_parser = sub.add_parser(
        "vault",
        help="Manage proxy token vault — issue, resolve, revoke opaque tokens",
    )
    _vault_parser = vault_parser
    vault_sub = vault_parser.add_subparsers(dest="vault_cmd")

    # ── issue ─────────────────────────────────────────────
    issue_parser = vault_sub.add_parser(
        "issue", help="Issue a proxy token for a provider",
    )
    issue_parser.add_argument("provider", help="OAuth provider (e.g. google, github)")
    issue_parser.add_argument("--ttl", type=int, default=600, help="Time-to-live in seconds (default: 600)")
    issue_parser.add_argument("--scope-level", default="run", help="Lifetime scope: run, session, persistent, single-use")
    issue_parser.add_argument("--max-uses", type=int, default=None, help="Maximum resolution count (default: unlimited)")
    issue_parser.add_argument("--scopes", nargs="+", default=None, help="Allowed API scopes")
    issue_parser.add_argument("--store", default=None, help="Credentials file path")
    issue_parser.add_argument("--json", action="store_true", dest="json_output", help="Output as JSON")

    # ── resolve ───────────────────────────────────────────
    resolve_parser = vault_sub.add_parser(
        "resolve", help="Resolve a proxy token (verify it is valid)",
    )
    resolve_parser.add_argument("token", help="Proxy token string (cup_tok_*)")
    resolve_parser.add_argument("--store", default=None, help="Credentials file path")
    resolve_parser.add_argument("--json", action="store_true", dest="json_output", help="Output as JSON")

    # ── revoke ────────────────────────────────────────────
    revoke_parser = vault_sub.add_parser(
        "revoke", help="Revoke a single proxy token",
    )
    revoke_parser.add_argument("token", help="Proxy token string (cup_tok_*)")
    revoke_parser.add_argument("--store", default=None, help="Credentials file path")

    # ── revoke-all ────────────────────────────────────────
    revoke_all_parser = vault_sub.add_parser(
        "revoke-all", help="Revoke all active proxy tokens",
    )
    revoke_all_parser.add_argument("--provider", default=None, help="Only revoke tokens for this provider")
    revoke_all_parser.add_argument("--store", default=None, help="Credentials file path")

    # ── list ──────────────────────────────────────────────
    list_parser = vault_sub.add_parser(
        "list", help="List all active proxy tokens",
    )
    list_parser.add_argument("--store", default=None, help="Credentials file path")
    list_parser.add_argument("--json", action="store_true", dest="json_output", help="Output as JSON")

    # ── status ────────────────────────────────────────────
    status_parser = vault_sub.add_parser(
        "status", help="Show detailed status of a proxy token",
    )
    status_parser.add_argument("token", help="Proxy token string (cup_tok_*)")
    status_parser.add_argument("--store", default=None, help="Credentials file path")
    status_parser.add_argument("--json", action="store_true", dest="json_output", help="Output as JSON")

    reg.register("vault", _handle_vault)


# ── Router ───────────────────────────────────────────────────

def _handle_vault(args):
    vault_cmd = getattr(args, "vault_cmd", None)
    if not vault_cmd:
        _vault_parser.print_help()
        return 1

    handler_map = {
        "issue": _handle_issue,
        "resolve": _handle_resolve,
        "revoke": _handle_revoke,
        "revoke-all": _handle_revoke_all,
        "list": _handle_list,
        "status": _handle_status,
    }
    handler = handler_map.get(vault_cmd)
    if handler is None:
        _vault_parser.print_help()
        return 1
    return handler(args)


# ── Handlers ─────────────────────────────────────────────────

def _handle_issue(args):
    try:
        store_path = getattr(args, "store", None)
        vault, state_file = _load_vault(store_path)

        proxy = vault.issue(
            provider=args.provider,
            scopes=getattr(args, "scopes", None),
            ttl=args.ttl,
            scope_level=getattr(args, "scope_level", "run"),
            max_uses=getattr(args, "max_uses", None),
        )

        _save_vault(vault, state_file)

        if getattr(args, "json_output", False):
            print(json.dumps(proxy.to_dict(), indent=2))
        else:
            print(f"✓ Issued proxy token for '{args.provider}'")
            print(f"  token: {proxy.token}")
            print(f"  ttl: {proxy.ttl}s")
            print(f"  scope_level: {proxy.scope_level}")
            if proxy.max_uses is not None:
                print(f"  max_uses: {proxy.max_uses}")
            if proxy.scopes:
                print(f"  scopes: {', '.join(proxy.scopes)}")
        return 0

    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def _handle_resolve(args):
    try:
        store_path = getattr(args, "store", None)
        vault, state_file = _load_vault(store_path)

        cred = vault.resolve(args.token)

        _save_vault(vault, state_file)

        if getattr(args, "json_output", False):
            print(json.dumps({
                "provider": cred.provider,
                "valid": cred.valid,
                "scopes": cred.scopes,
                "token_type": getattr(cred, "token_type", "Bearer"),
                "has_refresh": cred.refresh_token is not None,
            }, indent=2))
        else:
            status = "✓ valid" if cred.valid else "✗ expired"
            print(f"Resolved → {cred.provider} ({status})")
            print(f"  token_type: {getattr(cred, 'token_type', 'Bearer')}")
            print(f"  scopes: {', '.join(cred.scopes)}")
            if cred.expiry:
                exp = datetime.datetime.fromtimestamp(cred.expiry)
                print(f"  expires: {exp.isoformat()}")
        return 0

    except (KeyError, RuntimeError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def _handle_revoke(args):
    try:
        store_path = getattr(args, "store", None)
        vault, state_file = _load_vault(store_path)

        vault.revoke(args.token)
        _save_vault(vault, state_file)

        print(f"✓ Revoked proxy token {args.token[:20]}...")
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def _handle_revoke_all(args):
    try:
        store_path = getattr(args, "store", None)
        vault, state_file = _load_vault(store_path)

        provider = getattr(args, "provider", None)
        count = vault.revoke_all(provider=provider)
        _save_vault(vault, state_file)

        if provider:
            print(f"✓ Revoked {count} proxy token(s) for '{provider}'")
        else:
            print(f"✓ Revoked {count} proxy token(s)")
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def _handle_list(args):
    try:
        store_path = getattr(args, "store", None)
        vault, _state_file = _load_vault(store_path)

        active = vault.active_tokens()

        if getattr(args, "json_output", False):
            print(json.dumps([t.to_dict() for t in active], indent=2))
        else:
            if not active:
                print("No active proxy tokens")
            else:
                print(f"Active proxy tokens ({len(active)}):")
                for t in active:
                    preview = t.token[:20] + "..."
                    print(f"  {preview}  provider={t.provider}  scope_level={t.scope_level}  uses={t.usage_count}")
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def _handle_status(args):
    try:
        store_path = getattr(args, "store", None)
        vault, _state_file = _load_vault(store_path)

        proxy = vault._tokens.get(args.token)
        if proxy is None:
            print(f"Error: Unknown proxy token — not found in vault", file=sys.stderr)
            return 1

        status_str = "valid" if proxy.valid else (
            "revoked" if proxy.revoked else (
                "exhausted" if proxy.exhausted else "expired"
            )
        )

        if getattr(args, "json_output", False):
            data = proxy.to_dict()
            data["status"] = status_str
            data["valid"] = proxy.valid
            print(json.dumps(data, indent=2))
        else:
            exp = datetime.datetime.fromtimestamp(proxy.expires_at)
            print(f"Proxy Token Status: {status_str}")
            print(f"  token: {proxy.token[:20]}...")
            print(f"  provider: {proxy.provider}")
            print(f"  scope_level: {proxy.scope_level}")
            print(f"  ttl: {proxy.ttl}s")
            print(f"  expires: {exp.isoformat()}")
            print(f"  usage_count: {proxy.usage_count}")
            if proxy.max_uses is not None:
                print(f"  max_uses: {proxy.max_uses}")
            if proxy.scopes:
                print(f"  scopes: {', '.join(proxy.scopes)}")
            if proxy.revoked:
                print(f"  revoked: yes")
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
