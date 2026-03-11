#!/usr/bin/env python3
"""
cup-metrics — Validate a prototype with product-level metrics.

Usage:
    python prototypes/metrics/run.py http://localhost:8421 --static prototypes/social-login/static
    python prototypes/metrics/run.py http://localhost:8421 --endpoints /health /api/providers
    python prototypes/metrics/run.py http://localhost:8421 --json          # machine-readable
    python prototypes/metrics/run.py http://localhost:8421 --save report.json

Point this at any running server and get a validation report covering:
    • HTTP latency (p50/p95/p99)
    • Static bundle size breakdown
    • Health endpoint uptime percentage
    • Overall grade: PASS / WARN / FAIL
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

# ── Ensure codeupipe is importable from monorepo root ────────────────
_script_dir = Path(__file__).parent
_repo_root = _script_dir.parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from codeupipe import Payload
from prototypes.metrics.pipeline import build_metrics_pipeline


# ── Formatting ───────────────────────────────────────────────────────

_GRADE_COLORS = {
    "pass": "\033[32m",   # green
    "warn": "\033[33m",   # yellow
    "fail": "\033[31m",   # red
}
_RESET = "\033[0m"
_BOLD = "\033[1m"
_DIM = "\033[2m"


def _format_bytes(n: int) -> str:
    """Human-readable byte size."""
    if n < 1024:
        return f"{n} B"
    elif n < 1024 * 1024:
        return f"{n / 1024:.1f} KB"
    else:
        return f"{n / (1024 * 1024):.1f} MB"


def _print_report(report: dict) -> None:
    """Pretty-print the metrics report to stdout."""
    summary = report.get("summary", {})
    grade = summary.get("grade", "fail").upper()
    color = _GRADE_COLORS.get(grade.lower(), "")
    passed = summary.get("checks_passed", 0)
    total = summary.get("checks_total", 0)

    print()
    print(f"{'═' * 60}")
    print(f"  {_BOLD}codeupipe metrics report{_RESET}")
    print(f"  Target: {report.get('target', '?')}")
    print(f"  Time:   {report.get('timestamp', '?')}")
    print(f"{'═' * 60}")

    # ── Grade ─────────────────────────────────────────────
    print(f"\n  Grade: {color}{_BOLD}{grade}{_RESET}  ({passed}/{total} checks passed)")

    # ── Latency ───────────────────────────────────────────
    latency = report.get("latency", {})
    if latency:
        print(f"\n  {_BOLD}Latency{_RESET}")
        for endpoint, stats in latency.items():
            errs = stats.get("error_count", 0)
            err_str = f"  {_GRADE_COLORS['fail']}({errs} errors){_RESET}" if errs else ""
            print(f"    {endpoint:<20}  avg={stats.get('avg_ms', 0):.1f}ms  "
                  f"p95={stats.get('p95_ms', 0):.1f}ms  "
                  f"p99={stats.get('p99_ms', 0):.1f}ms  "
                  f"n={stats.get('count', 0)}{err_str}")

    # ── Bundle ────────────────────────────────────────────
    bundle = report.get("bundle", {})
    if bundle and bundle.get("file_count", 0) > 0:
        print(f"\n  {_BOLD}Bundle{_RESET}")
        print(f"    Total: {_format_bytes(bundle.get('total_bytes', 0))}  "
              f"({bundle.get('file_count', 0)} files)")
        by_ext = bundle.get("by_extension", {})
        if by_ext:
            print(f"    {_DIM}", end="")
            parts = [f"{ext}: {_format_bytes(size)}" for ext, size in sorted(by_ext.items())]
            print("  |  ".join(parts), end="")
            print(f"{_RESET}")
        largest = bundle.get("largest_files", [])
        if largest:
            print(f"    Largest: {largest[0][0]} ({_format_bytes(largest[0][1])})")

    # ── Health ────────────────────────────────────────────
    health = report.get("health", {})
    if health:
        uptime = health.get("uptime_pct", 0)
        up_color = _GRADE_COLORS["pass"] if uptime >= 99 else (_GRADE_COLORS["warn"] if uptime >= 95 else _GRADE_COLORS["fail"])
        print(f"\n  {_BOLD}Health{_RESET}")
        print(f"    Uptime:   {up_color}{uptime}%{_RESET}  "
              f"({health.get('successful_polls', 0)}/{health.get('total_polls', 0)} polls)")
        print(f"    Avg resp: {health.get('avg_response_ms', 0):.1f}ms")

    # ── Check details ─────────────────────────────────────
    checks = summary.get("checks", [])
    if checks:
        print(f"\n  {_BOLD}Checks{_RESET}")
        for check in checks:
            status = check["status"]
            icon = "✅" if status == "pass" else ("⚠️ " if status == "warn" else "❌")
            print(f"    {icon} {check['name']:<25} {_DIM}{check.get('detail', '')}{_RESET}")

    print(f"\n{'═' * 60}\n")


# ── Main ─────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        prog="cup-metrics",
        description="Validate a prototype with product-level metrics.",
    )
    parser.add_argument("url", help="Target URL (e.g. http://localhost:8421)")
    parser.add_argument("--endpoints", nargs="+", default=["/health"],
                        help="Endpoints to probe for latency (default: /health)")
    parser.add_argument("--health-path", default="/health",
                        help="Health check path (default: /health)")
    parser.add_argument("--static", default=None,
                        help="Path to static assets directory for bundle size check")
    parser.add_argument("--requests", type=int, default=10,
                        help="Number of requests per endpoint (default: 10)")
    parser.add_argument("--polls", type=int, default=10,
                        help="Number of health polls (default: 10)")
    parser.add_argument("--poll-interval", type=float, default=0.5,
                        help="Seconds between health polls (default: 0.5)")
    parser.add_argument("--json", action="store_true",
                        help="Output raw JSON instead of formatted report")
    parser.add_argument("--save", default=None,
                        help="Save report to JSON file")

    args = parser.parse_args()

    # Build pipeline
    pipeline = build_metrics_pipeline(
        requests=args.requests,
        polls=args.polls,
        poll_interval=args.poll_interval,
    )

    # Build input payload
    input_data = {
        "target_url": args.url,
        "endpoints": args.endpoints,
        "health_path": args.health_path,
    }
    if args.static:
        input_data["static_dir"] = args.static

    payload = Payload(input_data)

    # Run
    try:
        result = asyncio.run(pipeline.run(payload))
    except Exception as e:
        print(f"\033[31mError: {e}\033[0m", file=sys.stderr)
        sys.exit(1)

    report = result.get("metrics_report")
    if not report:
        print("\033[31mError: No metrics report generated\033[0m", file=sys.stderr)
        sys.exit(1)

    # Output
    if args.json:
        print(json.dumps(report, indent=2, default=str))
    else:
        _print_report(report)

    # Save
    if args.save:
        save_path = Path(args.save)
        save_path.write_text(json.dumps(report, indent=2, default=str))
        print(f"  Saved to {save_path}")

    # Exit code based on grade
    grade = report.get("summary", {}).get("grade", "fail")
    sys.exit(0 if grade == "pass" else (1 if grade == "warn" else 2))


if __name__ == "__main__":
    main()
