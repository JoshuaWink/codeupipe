"""``cup test``, ``cup doctor``, ``cup upgrade``, ``cup publish``, ``cup version`` commands."""

import sys
from pathlib import Path
from typing import List

from .._registry import registry
from .._bundle import bundle


def setup(sub, reg):
    # cup bundle <path>
    bundle_parser = sub.add_parser("bundle", help="Generate __init__.py re-exports for a component directory")
    bundle_parser.add_argument("path", help="Directory to scan and bundle")
    reg.register("bundle", _handle_bundle)

    # cup test [path] [--markers M] [--coverage] [--verbose]
    test_parser = sub.add_parser("test", help="Smart test runner — discover and run project tests")
    test_parser.add_argument("path", nargs="?", default="tests", help="Test directory or file (default: tests/)")
    test_parser.add_argument("--markers", "-m", help="Pytest markers to select")
    test_parser.add_argument("--coverage", action="store_true", help="Run with coverage report")
    test_parser.add_argument("--verbose", "-v", action="store_true", help="Verbose test output")
    reg.register("test", _handle_test)

    # cup doctor [path]
    doctor_parser = sub.add_parser("doctor", help="Project health check — manifest, CI, tests, lint, connectors")
    doctor_parser.add_argument("path", nargs="?", default=".", help="Project directory (default: current dir)")
    reg.register("doctor", _handle_doctor)

    # cup runs → handled by run_cmds

    # cup upgrade [path] [--dry-run]
    upgrade_parser = sub.add_parser("upgrade", help="Regenerate scaffolded files to latest codeupipe templates")
    upgrade_parser.add_argument("path", nargs="?", default=".", help="Project directory (default: current dir)")
    upgrade_parser.add_argument("--dry-run", action="store_true", help="Show what would change without writing")
    reg.register("upgrade", _handle_upgrade)

    # cup publish <directory> [--check-only]
    publish_parser = sub.add_parser("publish", help="Validate and prepare a connector for marketplace publishing")
    publish_parser.add_argument("directory", help="Path to connector package directory")
    publish_parser.add_argument("--check-only", action="store_true", help="Validate only, don't build")
    reg.register("publish", _handle_publish)

    # cup version [--bump LEVEL] [--tag]
    version_parser = sub.add_parser("version", help="Show or bump project version")
    version_parser.add_argument("--bump", choices=["patch", "minor", "major"], help="Bump version level")
    version_parser.add_argument("--tag", action="store_true", help="Create a git tag after bumping")
    reg.register("version", _handle_version)


# ── Handlers ────────────────────────────────────────────────────────

def _handle_bundle(args):
    try:
        result = bundle(args.path)
        print(f"Bundled {result['init_file']}:")
        for module, symbol in result["exports"]:
            print(f"  {module} → {symbol}")
        return 0
    except (FileNotFoundError, ValueError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def _handle_test(args):
    try:
        import subprocess
        test_path = getattr(args, "path", "tests")
        cmd = [sys.executable, "-m", "pytest", test_path, "-q"]
        markers = getattr(args, "markers", None)
        if markers:
            cmd.extend(["-m", markers])
        if getattr(args, "verbose", False):
            cmd.append("-v")
        if getattr(args, "coverage", False):
            cmd.extend(["--cov=.", "--cov-report=term-missing"])
        ret = subprocess.run(cmd, check=False)
        return ret.returncode
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def _handle_doctor(args):
    try:
        from codeupipe.doctor import diagnose
        project_path = getattr(args, "path", ".")
        results = diagnose(project_path)
        summary = results.pop("_summary", {})

        for check_name, result in results.items():
            ok = result.get("ok", False)
            icon = "\u2705" if ok else "\u274c"
            msg = result.get("message", "")
            print(f"  {icon} {check_name:14s} {msg}")

        print()
        total = summary.get("total", 0)
        passing = summary.get("passing", 0)
        if summary.get("healthy"):
            print(f"\u2705 Project healthy ({passing}/{total} checks passed)")
        else:
            failing = summary.get("failing", 0)
            print(f"\u274c {failing} issue(s) found ({passing}/{total} checks passed)")
        return 0 if summary.get("healthy") else 1
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def _handle_upgrade(args):
    try:
        from codeupipe.upgrade import upgrade_project
        project_path = getattr(args, "path", ".")
        dry_run = getattr(args, "dry_run", False)
        result = upgrade_project(project_path, dry_run=dry_run)

        prefix = "[DRY RUN] " if dry_run else ""
        for f in result.get("updated", []):
            print(f"  {prefix}Updated: {f}")
        for f in result.get("skipped", []):
            print(f"  Unchanged: {f}")
        for w in result.get("warnings", []):
            print(f"  Warning: {w}", file=sys.stderr)

        updated = len(result.get("updated", []))
        skipped = len(result.get("skipped", []))
        if updated:
            print(f"\n{prefix}{updated} file(s) updated, {skipped} unchanged")
        else:
            print("Everything up to date.")
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def _handle_publish(args):
    try:
        pkg_dir = Path(args.directory)
        check_only = getattr(args, "check_only", False)
        issues: List[str] = []

        if not pkg_dir.is_dir():
            print(f"Error: '{pkg_dir}' is not a directory", file=sys.stderr)
            return 1

        pyproject = pkg_dir / "pyproject.toml"
        setup_py = pkg_dir / "setup.py"
        if not pyproject.exists() and not setup_py.exists():
            issues.append("No pyproject.toml or setup.py found")

        if not any(pkg_dir.rglob("__init__.py")):
            issues.append("No __init__.py found — not a valid Python package")
        if not any(pkg_dir.rglob("test_*.py")):
            issues.append("No test files found")
        if not (pkg_dir / "README.md").exists():
            issues.append("No README.md found")

        if issues:
            print("Publish validation failed:")
            for issue in issues:
                print(f"  \u274c {issue}")
            return 1

        print("\u2705 Package structure valid")
        if check_only:
            print("(check-only mode — skipping build)")
            return 0

        import subprocess
        print("Building package...")
        ret = subprocess.run([sys.executable, "-m", "build", str(pkg_dir)], check=False)
        if ret.returncode == 0:
            print("\u2705 Package built. Upload with: twine upload dist/*")
        return ret.returncode
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def _handle_version(args):
    try:
        bump_level = getattr(args, "bump", None)
        do_tag = getattr(args, "tag", False)

        pyproject_path = Path("pyproject.toml")
        if not pyproject_path.exists():
            print("Error: No pyproject.toml found", file=sys.stderr)
            return 1

        text = pyproject_path.read_text()
        current = None
        for line in text.splitlines():
            if line.strip().startswith("version"):
                parts = line.split("=", 1)
                if len(parts) == 2:
                    current = parts[1].strip().strip('"').strip("'")
                    break

        if current is None:
            print("Error: Could not find version in pyproject.toml", file=sys.stderr)
            return 1

        if bump_level is None:
            print(current)
            return 0

        parts = current.split(".")
        if len(parts) != 3:
            print(f"Error: Version '{current}' is not semver", file=sys.stderr)
            return 1

        major, minor, patch = int(parts[0]), int(parts[1]), int(parts[2])
        if bump_level == "patch":
            patch += 1
        elif bump_level == "minor":
            minor += 1
            patch = 0
        elif bump_level == "major":
            major += 1
            minor = 0
            patch = 0

        new_version = f"{major}.{minor}.{patch}"
        new_text = text.replace(f'version = "{current}"', f'version = "{new_version}"')
        if new_text == text:
            new_text = text.replace(f"version = '{current}'", f'version = "{new_version}"')
        pyproject_path.write_text(new_text)
        print(f"{current} → {new_version}")

        if do_tag:
            import subprocess
            tag = f"v{new_version}"
            subprocess.run(["git", "tag", tag], check=True)
            print(f"Tagged: {tag}")
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
