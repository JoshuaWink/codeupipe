"""``cup distribute`` command with sub-subcommands: checkpoint, remote, worker."""

import json
import sys

from .._registry import registry

_dist_parser = None  # stored for help fallback


def setup(sub, reg):
    global _dist_parser
    dist_parser = sub.add_parser("distribute", help="Manage distributed pipeline components")
    _dist_parser = dist_parser
    dist_sub = dist_parser.add_subparsers(dest="dist_cmd")

    # checkpoint
    cp_parser = dist_sub.add_parser("checkpoint", help="Manage payload checkpoints")
    cp_parser.add_argument("path", help="Checkpoint file path")
    cp_group = cp_parser.add_mutually_exclusive_group(required=True)
    cp_group.add_argument("--save", metavar="JSON", help="Save a payload (JSON string) to checkpoint")
    cp_group.add_argument("--load", action="store_true", help="Load and print the checkpoint")
    cp_group.add_argument("--clear", action="store_true", help="Clear the checkpoint")
    cp_group.add_argument("--status", action="store_true", help="Show checkpoint status")

    # remote
    remote_parser = dist_sub.add_parser("remote", help="Test a remote filter endpoint")
    remote_parser.add_argument("url", help="Remote endpoint URL")
    remote_parser.add_argument("--timeout", type=int, default=10, help="Request timeout in seconds")

    # worker
    worker_parser = dist_sub.add_parser("worker", help="Show worker pool information")
    worker_parser.add_argument("--kind", choices=["thread", "process"], default="thread", help="Pool type (default: thread)")
    worker_parser.add_argument("--max-workers", type=int, default=None, help="Number of workers (default: CPU count)")

    reg.register("distribute", _handle_distribute)


def _handle_distribute(args):
    dist_cmd = getattr(args, "dist_cmd", None)
    if not dist_cmd:
        _dist_parser.print_help()
        return 1

    if dist_cmd == "checkpoint":
        return _handle_checkpoint(args)
    if dist_cmd == "remote":
        return _handle_remote(args)
    if dist_cmd == "worker":
        return _handle_worker(args)
    return 1


def _handle_checkpoint(args):
    try:
        from codeupipe.distribute import Checkpoint
        cp = Checkpoint(args.path)

        if getattr(args, "save", None):
            import codeupipe.core.payload as _payload_mod
            data = json.loads(args.save)
            payload = _payload_mod.Payload(data)
            cp.save(payload)
            print(f"Saved checkpoint → {args.path}")
            return 0

        if getattr(args, "load", False):
            if not cp.exists:
                print("No checkpoint found", file=sys.stderr)
                return 1
            payload = cp.load()
            print(json.dumps(payload.to_dict(), indent=2, default=str))
            return 0

        if getattr(args, "clear", False):
            cp.clear()
            print(f"Cleared checkpoint: {args.path}")
            return 0

        if getattr(args, "status", False):
            if not cp.exists:
                print("No checkpoint at this path")
                return 0
            meta = cp.metadata
            ts = cp.timestamp
            print(f"Checkpoint: {args.path}")
            print(f"  exists: True")
            print(f"  timestamp: {ts}")
            if meta:
                for k, v in meta.items():
                    print(f"  {k}: {v}")
            return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def _handle_remote(args):
    try:
        import urllib.request
        import urllib.error
        url = args.url
        timeout = getattr(args, "timeout", 10)
        req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "codeupipe-cli"})
        try:
            resp = urllib.request.urlopen(req, timeout=timeout)
            print(f"✓ {url} — {resp.status} {resp.reason}")
            return 0
        except urllib.error.HTTPError as he:
            print(f"✗ {url} — HTTP {he.code} {he.reason}")
            return 1
        except urllib.error.URLError as ue:
            print(f"✗ {url} — {ue.reason}")
            return 1
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def _handle_worker(args):
    try:
        import os
        kind = getattr(args, "kind", "thread")
        max_w = getattr(args, "max_workers", None) or os.cpu_count() or 4
        print(f"Worker Pool Configuration:")
        print(f"  kind: {kind}")
        print(f"  max_workers: {max_w}")
        print(f"  cpu_count: {os.cpu_count()}")
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
