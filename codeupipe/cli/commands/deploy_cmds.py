"""``cup deploy``, ``cup recipe``, ``cup init``, ``cup ci`` commands."""

import json
import sys
from pathlib import Path

from .._registry import registry


def setup(sub, reg):
    # cup deploy [target] [config] [--dry-run] [--mode MODE] [--port PORT] [--output-dir DIR]
    deploy_parser = sub.add_parser("deploy", help="Generate deployment artifacts for a pipeline")
    deploy_parser.add_argument("target", nargs="?", default="docker", help="Deployment target (default: docker)")
    deploy_parser.add_argument("config", nargs="?", default="cup.toml", help="Pipeline config or cup.toml manifest (default: cup.toml)")
    deploy_parser.add_argument("--dry-run", action="store_true", help="Validate only — do not generate or deploy")
    deploy_parser.add_argument("--mode", choices=["http", "worker", "cli"], help="Execution mode override")
    deploy_parser.add_argument("--port", type=int, default=8080, help="Port for HTTP mode (default: 8080)")
    deploy_parser.add_argument("--output-dir", default="deploy_output", help="Directory for generated artifacts (default: deploy_output)")
    reg.register("deploy", _handle_deploy)

    # cup recipe [name] [--list] [--dry-run] [--var ...] [--output-dir]
    recipe_parser = sub.add_parser("recipe", help="Apply a recipe template to generate pipeline configs")
    recipe_parser.add_argument("name", nargs="?", help="Recipe name (omit with --list)")
    recipe_parser.add_argument("--list", action="store_true", dest="list_recipes", help="List available recipes")
    recipe_parser.add_argument("--dry-run", action="store_true", help="Show resolved config without writing files")
    recipe_parser.add_argument("--var", action="append", metavar="KEY=VALUE", default=[], help="Set a recipe variable (repeatable)")
    recipe_parser.add_argument("--output-dir", default="pipelines", help="Directory for generated pipeline config (default: pipelines)")
    reg.register("recipe", _handle_recipe)

    # cup init [template] [name] [--list] [--deploy TARGET] [--ci PROVIDER] ...
    init_parser = sub.add_parser("init", help="Scaffold a new codeupipe project from a template")
    init_parser.add_argument("template", nargs="?", help="Project template (saas, api, etl, chatbot). Omit with --list.")
    init_parser.add_argument("name", nargs="?", help="Project name")
    init_parser.add_argument("--list", action="store_true", dest="list_templates", help="List available project templates")
    init_parser.add_argument("--deploy", default="docker", help="Deployment target (default: docker)")
    init_parser.add_argument("--auth", help="Auth provider (e.g. jwt, oauth)")
    init_parser.add_argument("--db", help="Database provider (e.g. postgres, sqlite)")
    init_parser.add_argument("--payments", help="Payment provider (e.g. stripe)")
    init_parser.add_argument("--ai", help="AI provider (e.g. openai)")
    init_parser.add_argument("--email", help="Email provider (e.g. sendgrid)")
    init_parser.add_argument(
        "--frontend", choices=["react", "next", "vite", "remix", "static"],
        help="Frontend framework to scaffold",
    )
    init_parser.add_argument(
        "--ci", default="github",
        help=(
            "CI platform (default: github). Comma-separated for multiple: "
            "github,gitlab. Options: github, gitlab, azure-devops, bitbucket, "
            "circleci, jenkins, forgejo, gitea, buildkite, drone, woodpecker, "
            "travis, aws-codebuild, cloud-build"
        ),
    )
    reg.register("init", _handle_init)

    # cup ci [--detect] [--regenerate] [--provider P] [--deploy T] [--frontend F]
    ci_parser = sub.add_parser("ci", help="Detect, regenerate, or switch CI platform")
    ci_parser.add_argument("--detect", action="store_true", help="Show detected CI configs in the project")
    ci_parser.add_argument("--regenerate", action="store_true", help="Regenerate the current CI config")
    ci_parser.add_argument("--provider", help="Switch to a different CI provider")
    ci_parser.add_argument("--deploy", default="docker", help="Deploy target for CD steps (default: docker)")
    ci_parser.add_argument("--frontend", help="Frontend framework")
    reg.register("ci", _handle_ci)


# ── Handlers ────────────────────────────────────────────────────────

def _handle_deploy(args):
    try:
        from codeupipe.deploy.discovery import find_adapters
        from codeupipe.deploy.manifest import load_manifest

        adapters = find_adapters()
        target_name = args.target
        if target_name not in adapters:
            available = ", ".join(adapters.keys())
            print(f"Error: unknown target '{target_name}'. Available: {available}", file=sys.stderr)
            return 1

        adapter = adapters[target_name]
        config_path = args.config
        if config_path.endswith(".toml"):
            pipeline_config = load_manifest(config_path)
        else:
            config_text = Path(config_path).read_text()
            pipeline_config = json.loads(config_text)

        mode = getattr(args, "mode", None)
        port = getattr(args, "port", 8080)
        output_dir = Path(getattr(args, "output_dir", "deploy_output"))

        opts = {}
        if mode:
            opts["mode"] = mode
        opts["port"] = port

        issues = adapter.validate(pipeline_config, **opts)
        if issues:
            print("Validation failed:", file=sys.stderr)
            for issue in issues:
                print(f"  ✗ {issue}", file=sys.stderr)
            return 1

        if getattr(args, "dry_run", False):
            print(f"✓ {target_name}: validation passed (dry run)")
            return 0

        files = adapter.generate(pipeline_config, output_dir, **opts)
        print(f"Generated {target_name} artifacts in {output_dir}/:")
        for f in files:
            print(f"  {f}")
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def _handle_recipe(args):
    try:
        from codeupipe.deploy.recipe import list_recipes as _list_recipes, resolve_recipe

        if getattr(args, "list_recipes", False):
            recipes = _list_recipes()
            if not recipes:
                print("No recipes available.")
                return 0
            print("Available recipes:")
            for r in recipes:
                print(f"  {r['name']:20s} {r['description']}")
            return 0

        if not args.name:
            print("Error: recipe name required (or use --list)", file=sys.stderr)
            return 1

        variables = {}
        for v in getattr(args, "var", []):
            if "=" not in v:
                print(f"Error: --var must be KEY=VALUE, got '{v}'", file=sys.stderr)
                return 1
            key, value = v.split("=", 1)
            variables[key] = value

        resolved, deps = resolve_recipe(args.name, variables)

        if getattr(args, "dry_run", False):
            print(json.dumps(resolved, indent=2))
            if deps:
                print(f"\nDependencies: {', '.join(deps)}")
            return 0

        output_dir = Path(getattr(args, "output_dir", "pipelines"))
        output_dir.mkdir(parents=True, exist_ok=True)
        out_file = output_dir / f"{args.name}.json"
        out_file.write_text(json.dumps(resolved, indent=2) + "\n")
        print(f"Created {out_file}")
        if deps:
            print(f"  Dependencies: {', '.join(deps)}")
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def _handle_init(args):
    try:
        from codeupipe.deploy.init import init_project, list_templates as _list_templates

        if getattr(args, "list_templates", False):
            templates = _list_templates()
            print("Available project templates:")
            for t in templates:
                print(f"  {t['name']:12s} {t['description']}")
            return 0

        if not args.template or not args.name:
            print("Error: template and name required (or use --list)", file=sys.stderr)
            return 1

        options = {}
        for key in ("auth", "db", "payments", "ai", "email"):
            val = getattr(args, key, None)
            if val:
                options[key] = val

        result = init_project(
            args.template, args.name,
            deploy_target=getattr(args, "deploy", "docker"),
            ci_provider=getattr(args, "ci", "github"),
            frontend=getattr(args, "frontend", None),
            options=options,
        )

        print(f"Created project '{args.name}' ({args.template}):")
        for f in result["files"]:
            print(f"  {f}")
        for w in result.get("warnings", []):
            print(f"  Warning: {w}", file=sys.stderr)
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def _handle_ci(args):
    try:
        from codeupipe.deploy.init import detect_ci, regenerate_ci

        if getattr(args, "detect", False):
            found = detect_ci(".")
            if not found:
                print("No CI configs detected.")
            else:
                print("Detected CI configs:")
                for entry in found:
                    print(f"  {entry['provider']:20s} {entry['path']}")
            return 0

        provider = getattr(args, "provider", None)
        regenerate = getattr(args, "regenerate", False)

        if regenerate or provider:
            result = regenerate_ci(
                ".", ci_provider=provider,
                deploy_target=getattr(args, "deploy", "docker"),
                frontend=getattr(args, "frontend", None),
            )
            action = "Switched to" if provider else "Regenerated"
            print(f"{action} {result['provider']} CI config: {result['file']}")
            for removed in result.get("removed", []):
                print(f"  Removed old config: {removed}")
            for w in result.get("warnings", []):
                print(f"  Warning: {w}", file=sys.stderr)
            return 0

        found = detect_ci(".")
        if not found:
            print("No CI configs detected. Use --provider to add one.")
        else:
            print("Current CI configs:")
            for entry in found:
                print(f"  {entry['provider']:20s} {entry['path']}")
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
