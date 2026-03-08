"""``cup auth`` command with sub-subcommands: login, status, revoke, list."""

import datetime
import sys

from .._registry import registry

_auth_parser = None  # stored for help fallback


def setup(sub, reg):
    global _auth_parser
    auth_parser = sub.add_parser("auth", help="Manage OAuth2 credentials for pipeline connectors")
    _auth_parser = auth_parser
    auth_sub = auth_parser.add_subparsers(dest="auth_cmd")

    # login
    login_parser = auth_sub.add_parser("login", help="Authenticate with an OAuth2 provider")
    login_parser.add_argument("provider", help="Provider name: google, github")
    login_parser.add_argument("--client-id", help="OAuth client ID (or set CUP_AUTH_CLIENT_ID env)")
    login_parser.add_argument("--client-secret", help="OAuth client secret (or set CUP_AUTH_CLIENT_SECRET env)")
    login_parser.add_argument("--scopes", nargs="+", help="OAuth scopes to request")
    login_parser.add_argument("--port", type=int, default=0, help="Local callback port (default: auto)")
    login_parser.add_argument("--no-browser", action="store_true", help="Print URL instead of opening browser")
    login_parser.add_argument("--store", default=None, help="Credentials file path")

    # status
    status_parser = auth_sub.add_parser("status", help="Show credential status")
    status_parser.add_argument("provider", nargs="?", help="Show status for specific provider")
    status_parser.add_argument("--store", default=None, help="Credentials file path")

    # revoke
    revoke_parser = auth_sub.add_parser("revoke", help="Remove stored credentials")
    revoke_parser.add_argument("provider", help="Provider to revoke")
    revoke_parser.add_argument("--store", default=None, help="Credentials file path")

    # list
    auth_sub.add_parser("list", help="List all stored providers")

    reg.register("auth", _handle_auth)


def _print_credential_status(cred):
    """Print formatted credential status."""
    status = "✓ valid" if cred.valid else "✗ expired"
    print(f"  {cred.provider}: {status}")
    print(f"    token_type: {cred.token_type}")
    print(f"    scopes: {', '.join(cred.scopes)}")
    if cred.expiry:
        exp = datetime.datetime.fromtimestamp(cred.expiry)
        print(f"    expires: {exp.isoformat()}")
    if cred.refresh_token:
        print(f"    refresh_token: {'present' if cred.refresh_token else 'none'}")


def _handle_auth(args):
    auth_cmd = getattr(args, "auth_cmd", None)
    if not auth_cmd:
        _auth_parser.print_help()
        return 1

    if auth_cmd == "login":
        return _handle_login(args)
    if auth_cmd == "status":
        return _handle_status(args)
    if auth_cmd == "revoke":
        return _handle_revoke(args)
    if auth_cmd == "list":
        return _handle_list(args)
    return 1


def _handle_login(args):
    try:
        import os
        from codeupipe.auth import CredentialStore, GoogleOAuth, GitHubOAuth
        from codeupipe.auth._server import run_oauth_flow

        provider_name = args.provider.lower()
        store = CredentialStore(args.store)

        client_id = getattr(args, "client_id", None) or os.environ.get("CUP_AUTH_CLIENT_ID")
        client_secret = getattr(args, "client_secret", None) or os.environ.get("CUP_AUTH_CLIENT_SECRET")

        if not client_id or not client_secret:
            print(
                f"Error: --client-id and --client-secret are required\n"
                f"  (or set CUP_AUTH_CLIENT_ID and CUP_AUTH_CLIENT_SECRET env vars)",
                file=sys.stderr,
            )
            return 1

        scopes = getattr(args, "scopes", None)

        if provider_name == "google":
            provider = GoogleOAuth(client_id, client_secret, scopes=scopes)
        elif provider_name == "github":
            provider = GitHubOAuth(client_id, client_secret, scopes=scopes)
        else:
            print(f"Error: Unknown provider '{provider_name}'. Supported: google, github", file=sys.stderr)
            return 1

        port = getattr(args, "port", 0) or 0
        no_browser = getattr(args, "no_browser", False)

        code, redirect_uri = run_oauth_flow(provider, port=port, open_browser=not no_browser)

        cred = provider.exchange_code(code, redirect_uri)
        store.save(cred)
        store.register_provider(provider_name, provider)

        print(f"\n✓ Authenticated with {provider_name}")
        print(f"  scopes: {', '.join(cred.scopes)}")
        print(f"  stored: {store.path}")
        if cred.expiry:
            exp = datetime.datetime.fromtimestamp(cred.expiry)
            print(f"  expires: {exp.isoformat()}")
        return 0
    except TimeoutError as e:
        print(f"✗ {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def _handle_status(args):
    try:
        from codeupipe.auth import CredentialStore

        store = CredentialStore(getattr(args, "store", None))
        provider_name = getattr(args, "provider", None)

        if provider_name:
            cred = store.get(provider_name, auto_refresh=False)
            if cred is None:
                print(f"No credentials stored for '{provider_name}'")
                return 0
            _print_credential_status(cred)
        else:
            providers = store.list_providers()
            if not providers:
                print("No stored credentials")
                return 0
            for name in providers:
                cred = store.get(name, auto_refresh=False)
                if cred:
                    _print_credential_status(cred)
                    print()
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def _handle_revoke(args):
    try:
        from codeupipe.auth import CredentialStore

        store = CredentialStore(getattr(args, "store", None))
        removed = store.remove(args.provider)
        if removed:
            print(f"✓ Revoked credentials for '{args.provider}'")
        else:
            print(f"No credentials stored for '{args.provider}'")
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def _handle_list(args):
    try:
        from codeupipe.auth import CredentialStore

        store = CredentialStore()
        providers = store.list_providers()
        if not providers:
            print("No stored credentials")
        else:
            print("Stored providers:")
            for name in providers:
                cred = store.get(name, auto_refresh=False)
                status = "valid" if cred and cred.valid else "expired"
                print(f"  {name} ({status})")
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
