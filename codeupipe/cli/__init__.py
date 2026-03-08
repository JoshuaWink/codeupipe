"""
codeupipe CLI — scaffold components with zero boilerplate.

Usage:
    cup new <component> <name> [path]
    cup new pipeline <name> [path] --steps step1 step2:type ...
    cup bundle <path>
    cup lint <path>
    cup coverage <path> [--tests-dir DIR]
    cup report <path> [--tests-dir DIR] [--json] [--detail] [--verbose]
    cup doc-check [path] [--json] [--fix] [--all] [--auto-fix]
    cup run <config> [--discover DIR] [--input JSON] [--json]
    cup deploy [target] [config] [--dry-run] [--mode MODE] [--port PORT] [--output-dir DIR]
    cup recipe [name] [--list] [--dry-run] [--var KEY=VALUE ...]
    cup init [template] [name] [--list] [--deploy TARGET] [--ci PROVIDER] [--auth PROVIDER] ...
    cup marketplace search <query> [--category CAT] [--provider PROV]
    cup marketplace info <package>
    cup marketplace install <package>
    cup auth login <provider> [--client-id ID] [--client-secret SECRET] [--scopes ...]
    cup auth status [provider]
    cup auth revoke <provider>
    cup auth list
    cup vault issue <provider> [--ttl SEC] [--scope-level LEVEL] [--max-uses N] [--json]
    cup vault resolve <token> [--json]
    cup vault revoke <token>
    cup vault revoke-all [--provider PROVIDER]
    cup vault list [--json]
    cup vault status <token> [--json]

Components:
    filter          Filter (sync def call) — Pipeline handles awaiting
    async-filter    Filter (async def call) — native coroutine
    stream-filter   StreamFilter (async def stream → yields 0..N chunks)
    tap             Tap (sync def observe) — Pipeline handles awaiting
    async-tap       Tap (async def observe) — native coroutine
    hook            Lifecycle hook (before/after/on_error)
    valve           Conditional flow control (filter + predicate)
    pipeline        Pipeline orchestrator
    retry-filter    RetryFilter wrapper

Step Types (for --steps):
    name            Defaults to 'filter'
    name:filter     Explicit filter
    name:tap        Observation point
    name:hook       Lifecycle hook
    name:valve      Conditional gate
    name:stream-filter  Streaming (0..N output)

Bundle:
    Scans a directory for codeupipe components and generates
    __init__.py with re-exports for clean imports.

Examples:
    cup new filter validate_email
    cup new filter validate_email src/filters
    cup new pipeline checkout_flow src/pipelines
    cup new pipeline checkout_flow src/pipelines --steps validate_cart calc_total charge_payment
    cup new pipeline data_etl src/pipelines --steps parse:filter fan_out:stream-filter audit:tap
    cup new hook audit_logger src/hooks
    cup new stream-filter log_parser src/streams
    cup bundle src/signup
"""

import argparse
import sys

from ._registry import registry
from .commands import setup_all


# ── Entry Point ─────────────────────────────────────────────────────

def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="cup",
        description="codeupipe CLI — scaffold pipeline components instantly.",
    )
    parser.add_argument(
        "--json", action="store_true", dest="json_output",
        help="Output results as JSON (machine-readable)",
    )
    sub = parser.add_subparsers(dest="command")

    # Register every command module's parsers + handlers
    setup_all(sub, registry)

    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return 1

    result = registry.dispatch(args)
    if result is None:
        parser.print_help()
        return 1
    return result


if __name__ == "__main__":
    sys.exit(main())
