"""``cup connect`` and ``cup marketplace`` commands."""

import json
import sys

from .._registry import registry


def setup(sub, reg):
    # cup connect [--list] [--health [NAME]] [--manifest PATH]
    connect_parser = sub.add_parser("connect", help="Manage service connectors")
    connect_parser.add_argument("--list", action="store_true", dest="list_connectors", help="List connectors configured in cup.toml")
    connect_parser.add_argument(
        "--health", nargs="?", const="__all__", default=None, dest="health_check",
        help="Run health checks on connectors (optionally specify one)",
    )
    connect_parser.add_argument("--manifest", default="cup.toml", help="Path to cup.toml manifest (default: cup.toml)")
    reg.register("connect", _handle_connect)

    # cup marketplace search|info|install
    mp_parser = sub.add_parser("marketplace", help="Discover and install community connectors")
    mp_sub = mp_parser.add_subparsers(dest="marketplace_cmd")

    mp_search = mp_sub.add_parser("search", help="Search for connectors")
    mp_search.add_argument("query", nargs="?", default="", help="Keyword to search for")
    mp_search.add_argument("--category", default=None, help="Filter by category")
    mp_search.add_argument("--provider", default=None, help="Filter by provider")

    mp_info = mp_sub.add_parser("info", help="Show details for a connector package")
    mp_info.add_argument("package", help="Package name (e.g. codeupipe-stripe or stripe)")

    mp_install = mp_sub.add_parser("install", help="Install a connector package via pip")
    mp_install.add_argument("package", help="Package name to install")
    reg.register("marketplace", _handle_marketplace)


# ── Handlers ────────────────────────────────────────────────────────

def _handle_connect(args):
    try:
        from codeupipe.connect import load_connector_configs, check_health as _check_health
        from codeupipe.connect import discover_connectors, HttpConnector
        from codeupipe.deploy.manifest import load_manifest

        use_json = getattr(args, "json_output", False)
        manifest_path = getattr(args, "manifest", "cup.toml")

        if getattr(args, "list_connectors", False):
            try:
                manifest = load_manifest(manifest_path)
            except FileNotFoundError:
                if use_json:
                    print(json.dumps({"connectors": [], "note": "No cup.toml found"}))
                else:
                    print("No cup.toml found. Create one with 'cup init'.")
                return 0

            configs = load_connector_configs(manifest)
            if use_json:
                items = [{"name": c.name, "provider": c.provider} for c in configs]
                print(json.dumps({"connectors": items}, indent=2))
            else:
                if not configs:
                    print("No connectors configured in cup.toml.")
                else:
                    print("Connectors:")
                    for c in configs:
                        print(f"  {c.name:20s} provider={c.provider}")
            return 0

        if getattr(args, "health_check", None) is not None:
            try:
                manifest = load_manifest(manifest_path)
            except FileNotFoundError:
                print("Error: No cup.toml found", file=sys.stderr)
                return 1

            from codeupipe.registry import Registry
            reg = Registry()
            configs = load_connector_configs(manifest)
            discover_connectors(configs, reg)

            target = args.health_check
            names = None if target == "__all__" else [target]
            results = _check_health(reg, names)

            if use_json:
                print(json.dumps({"health": results}, indent=2))
            else:
                if not results:
                    print("No connectors to check.")
                else:
                    for name, healthy in results.items():
                        status = "OK" if healthy else "FAIL"
                        print(f"  {name:20s} {status}")
            all_ok = all(results.values()) if results else True
            return 0 if all_ok else 2

        print("Usage: cup connect --list | cup connect --health [name]")
        return 1
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def _handle_marketplace(args):
    try:
        from codeupipe.marketplace import fetch_index, search as mp_search_fn, info as mp_info_fn
        from codeupipe.marketplace import MarketplaceError

        use_json = getattr(args, "json_output", False)
        subcmd = getattr(args, "marketplace_cmd", None)

        if subcmd == "search":
            try:
                index = fetch_index()
            except MarketplaceError as exc:
                print(f"Error: {exc}", file=sys.stderr)
                return 1
            results = mp_search_fn(
                index, args.query or "",
                category=getattr(args, "category", None),
                provider=getattr(args, "provider", None),
            )
            if use_json:
                print(json.dumps({"results": results}, indent=2))
            else:
                if not results:
                    print("No connectors found.")
                else:
                    for r in results:
                        trust_badge = {"verified": "\u2705", "community": "\U0001f537"}.get(r.get("trust", ""), "")
                        print(
                            f"  {r['name']} {trust_badge} (v{r.get('latest', '?')}) "
                            f"\u2014 {r.get('description', '')}"
                        )
                        cats = ", ".join(r.get("categories", []))
                        if cats:
                            print(f"    Categories: {cats}")
                        filters = ", ".join(r.get("filters", []))
                        if filters:
                            print(f"    Filters: {filters}")
                        print(f"    pip install {r.get('pypi', r['name'])}")
                        print()
            return 0

        if subcmd == "info":
            try:
                index = fetch_index()
            except MarketplaceError as exc:
                print(f"Error: {exc}", file=sys.stderr)
                return 1
            entry = mp_info_fn(index, args.package)
            if entry is None:
                print(f"Package '{args.package}' not found in marketplace.", file=sys.stderr)
                return 1
            if use_json:
                print(json.dumps(entry, indent=2))
            else:
                trust_badge = {"verified": "\u2705", "community": "\U0001f537"}.get(entry.get("trust", ""), "")
                print(f"Name:        {entry['name']}")
                print(f"Provider:    {entry.get('provider', '?')}")
                print(f"Trust:       {trust_badge} {entry.get('trust', 'unknown')}")
                print(f"Version:     {entry.get('latest', '?')}")
                print(f"Description: {entry.get('description', '')}")
                print(f"Categories:  {', '.join(entry.get('categories', []))}")
                print(f"Filters:     {', '.join(entry.get('filters', []))}")
                print(f"Requires:    codeupipe >= {entry.get('min_codeupipe', '?')}")
                print(f"Repo:        {entry.get('repo', '?')}")
                print(f"Install:     pip install {entry.get('pypi', entry['name'])}")
            return 0

        if subcmd == "install":
            try:
                index = fetch_index()
            except MarketplaceError:
                index = None
            pkg = args.package
            if index is not None:
                entry = mp_info_fn(index, pkg)
                if entry:
                    pkg = entry.get("pypi", pkg)
            import subprocess
            print(f"Installing {pkg}...")
            ret = subprocess.run([sys.executable, "-m", "pip", "install", pkg], check=False)
            return ret.returncode

        print("Usage: cup marketplace search|info|install")
        return 1
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
