"""``cup new`` and ``cup list`` commands."""

import sys

from .._registry import registry
from .._scaffold import COMPONENT_TYPES, scaffold


def setup(sub, reg):
    # cup new <component> <name> [path] [--steps ...]
    new_parser = sub.add_parser("new", help="Scaffold a new component")
    new_parser.add_argument(
        "component", choices=COMPONENT_TYPES,
        help="Component type to scaffold",
    )
    new_parser.add_argument("name", help="Component name (snake_case or PascalCase)")
    new_parser.add_argument(
        "path", nargs="?", default=".",
        help="Directory to create the component in (default: current dir)",
    )
    new_parser.add_argument(
        "--steps", nargs="+", metavar="NAME[:TYPE]",
        help=(
            "Compose a pipeline from steps (pipeline only). "
            "Format: name or name:type. Default type is 'filter'. "
            "Types: filter, async-filter, stream-filter, tap, async-tap, "
            "hook, valve, retry-filter. "
            "Example: --steps validate_cart calc_total audit_log:tap"
        ),
    )
    reg.register("new", _handle_new)

    # cup list
    sub.add_parser("list", help="List available component types")
    reg.register("list", _handle_list)


def _handle_new(args):
    try:
        steps = getattr(args, "steps", None)
        if steps and args.component != "pipeline":
            print(
                "Error: --steps can only be used with 'pipeline' component type.",
                file=sys.stderr,
            )
            return 1
        result = scaffold(args.component, args.name, args.path, steps=steps)
        print(f"Created {args.component}:")
        print(f"  {result['component_file']}")
        print(f"  {result['test_file']}")
        return 0
    except (FileExistsError, Exception) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def _handle_list(args):
    print("Available component types:")
    for ct in COMPONENT_TYPES:
        print(f"  {ct}")
    return 0
