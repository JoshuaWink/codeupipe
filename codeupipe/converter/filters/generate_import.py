"""
GenerateImportFilter: Generates CUP code from standard Python project files.
"""

import re
from typing import Any, Dict, List
from codeupipe import Payload


class GenerateImportFilter:
    """
    Filter: Generate CUP Filter/Tap/Valve/Pipeline code from standard Python files.

    Input payload keys:
        - source_files (list[dict]): Files from ScanProjectFilter
        - config (dict): Config with output dirs and roles
        - classified_files (dict[str, list[dict]]): role → files (from ClassifyFilesFilter)

    Output payload adds:
        - cup_files (list[dict]): {"path": str, "content": str} for generated CUP code
        - cup_pipeline (str): Generated Pipeline composition code
    """

    def call(self, payload):
        classified_files = payload.get("classified_files", {})
        config = payload.get("config", {})

        cup_files: List[Dict[str, str]] = []
        pipeline_steps: List[Dict[str, str]] = []

        for role, files in classified_files.items():
            cup_type = _role_to_cup_type(role, config.get("pattern", "flat"))

            for file_info in files:
                name = file_info["name"]
                functions = _extract_functions(file_info["content"])

                if not functions:
                    continue

                for fn_name, fn_sig, fn_body, returns_value in functions:
                    if cup_type == "tap" or not returns_value:
                        cup_code = _generate_tap_class(fn_name, fn_body)
                        pipeline_steps.append({"name": fn_name, "type": "tap"})
                    else:
                        cup_code = _generate_filter_class(fn_name, fn_body)
                        pipeline_steps.append({"name": fn_name, "type": "filter"})

                    cup_files.append({
                        "path": f"filters/{fn_name}.py",
                        "content": cup_code,
                    })

        # Generate pipeline composition
        pipeline_code = _generate_pipeline(pipeline_steps)

        return (
            payload
            .insert("cup_files", cup_files)
            .insert("cup_pipeline", pipeline_code)
            .insert("cup_steps", pipeline_steps)
        )


def _role_to_cup_type(role: str, pattern: str) -> str:
    """Map an architectural role back to a CUP type."""
    tap_roles = {"middleware", "observability", "infrastructure", "framework"}
    if role in tap_roles:
        return "tap"
    return "filter"


def _extract_functions(source: str) -> List[tuple]:
    """
    Extract top-level function definitions from Python source.

    Returns list of (name, signature, body, returns_value).
    """
    functions = []
    # Match def function_name(args): with body
    pattern = re.compile(
        r'^def\s+(\w+)\s*\(([^)]*)\)\s*(?:->\s*[\w\[\], ]+)?\s*:',
        re.MULTILINE,
    )

    for match in pattern.finditer(source):
        fn_name = match.group(1)
        fn_sig = match.group(2)
        start = match.end()

        # Find the body (indented block after the def)
        body_lines = []
        for line in source[start:].split("\n"):
            if line.strip() == "":
                body_lines.append("")
                continue
            if line and not line[0].isspace():
                break
            body_lines.append(line)

        # Strip leading/trailing empty lines
        while body_lines and not body_lines[0].strip():
            body_lines.pop(0)
        while body_lines and not body_lines[-1].strip():
            body_lines.pop()

        body = "\n".join(body_lines)
        returns_value = "return " in body and ("return data" in body.lower() or "return {" in body)

        functions.append((fn_name, fn_sig, body, returns_value))

    return functions


def _generate_filter_class(name: str, body: str) -> str:
    """Generate a CUP Filter class wrapping a standard function."""
    class_name = "".join(w.capitalize() for w in name.split("_")) + "Filter"
    indented_body = _indent_body(body)

    return f'''"""
{class_name}: Imported from standard Python function '{name}'.
"""

from codeupipe import Payload


class {class_name}:
    """Filter wrapping the '{name}' function."""

    def call(self, payload):
        data = payload.to_dict()
{indented_body}
        return Payload(data)
'''


def _generate_tap_class(name: str, body: str) -> str:
    """Generate a CUP Tap class wrapping a standard observation function."""
    class_name = "".join(w.capitalize() for w in name.split("_")) + "Tap"
    indented_body = _indent_body(body)

    return f'''"""
{class_name}: Imported from standard Python function '{name}'.
"""

from codeupipe import Payload


class {class_name}:
    """Tap wrapping the '{name}' function."""

    def observe(self, payload):
        data = payload.to_dict()
{indented_body}
'''


def _generate_pipeline(steps: List[Dict[str, str]]) -> str:
    """Generate Pipeline composition code."""
    lines = [
        '"""',
        "Pipeline: Auto-generated from standard Python project import.",
        '"""',
        "",
        "from codeupipe import Pipeline, Payload",
        "",
    ]

    # Import each filter/tap
    for step in steps:
        name = step["name"]
        class_name = "".join(w.capitalize() for w in name.split("_"))
        if step["type"] == "tap":
            class_name += "Tap"
            lines.append(f"from filters.{name} import {class_name}")
        else:
            class_name += "Filter"
            lines.append(f"from filters.{name} import {class_name}")

    lines.extend([
        "",
        "",
        "def build_pipeline() -> Pipeline:",
        '    """Build the pipeline from imported components."""',
        "    pipeline = Pipeline()",
    ])

    for step in steps:
        name = step["name"]
        class_name = "".join(w.capitalize() for w in name.split("_"))
        if step["type"] == "tap":
            class_name += "Tap"
            lines.append(f'    pipeline.add_tap({class_name}(), name="{name}")')
        else:
            class_name += "Filter"
            lines.append(f'    pipeline.add_filter({class_name}(), name="{name}")')

    lines.extend([
        "    return pipeline",
        "",
    ])

    return "\n".join(lines)


def _indent_body(body: str) -> str:
    """Indent body to 8 spaces (inside a class method), preserving relative indentation."""
    lines = body.split("\n")

    # Find the minimum indentation of non-empty lines
    min_indent = float("inf")
    for line in lines:
        stripped = line.rstrip()
        if stripped:
            leading = len(line) - len(line.lstrip())
            min_indent = min(min_indent, leading)
    if min_indent == float("inf"):
        min_indent = 0

    result = []
    for line in lines:
        stripped = line.rstrip()
        if stripped:
            # Preserve relative indent: strip min_indent, add 8 spaces
            relative = line[min_indent:] if len(line) > min_indent else line.lstrip()
            result.append(f"        {relative}")
        else:
            result.append("")
    return "\n".join(result)
