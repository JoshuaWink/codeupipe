"""
GenerateExportFilter: Generates standard Python code from classified CUP steps.
"""

import os
from typing import Any, Dict, List
from codeupipe import Payload


class GenerateExportFilter:
    """
    Filter: Generate standard Python files from classified CUP steps.

    Input payload keys:
        - classified (dict[str, list[dict]]): role → steps
        - config (dict): Config with output dirs
        - steps (list[dict]): Original step order (for orchestrator)

    Output payload adds:
        - files (list[dict]): {"path": str, "content": str} for each generated file
    """

    def call(self, payload):
        classified = payload.get("classified", {})
        config = payload.get("config", {})
        steps = payload.get("steps", [])
        hooks = payload.get("hooks", [])

        output = config.get("output", {})
        base = output.get("base", "src/")
        pattern = config.get("pattern", "flat")

        files: List[Dict[str, str]] = []

        # Generate a file for each step
        for role, role_steps in classified.items():
            target_dir = output.get(role, f"{role}/")
            for step in role_steps:
                name = step.get("name", step.get("class_name", "unknown"))
                filename = f"{name}.py"
                filepath = os.path.join(base, target_dir, filename)
                content = _generate_step_file(step)
                files.append({"path": filepath, "content": content})

        # Generate the orchestrator
        orchestrator = _generate_orchestrator(steps, hooks, classified, config)
        # Orchestrator goes in controller dir (MVC) or root (flat)
        orch_dir = output.get("controller", output.get("step", ""))
        orch_path = os.path.join(base, orch_dir, "pipeline.py")
        files.append({"path": orch_path, "content": orchestrator})

        return payload.insert("files", files)


def _generate_step_file(step: Dict[str, Any]) -> str:
    """Generate a standard Python file for one step."""
    name = step.get("name", step.get("class_name", "unknown"))
    step_type = step.get("type", "filter")
    class_name = step.get("class_name", "Unknown")
    source = step.get("source")

    lines = [
        f'"""',
        f"{name} — converted from CUP {class_name}",
        f'"""',
        "",
    ]

    if step_type in ("filter", "valve"):
        lines.extend([
            "",
            f"def {name}(data: dict) -> dict:",
            f'    """Converted from CUP Filter: {class_name}."""',
        ])
        if source:
            lines.append(f"    # Original CUP source:")
            for src_line in source.strip().split("\n"):
                lines.append(f"    # {src_line}")
            lines.append("")
        lines.extend([
            "    # TODO: implement business logic",
            "    return data",
        ])

        # For valves, also emit the predicate
        if step_type == "valve":
            lines.extend([
                "",
                "",
                f"def {name}_predicate(data: dict) -> bool:",
                f'    """Predicate for conditional execution of {name}."""',
                "    # TODO: implement predicate logic",
                "    return True",
            ])

    elif step_type == "tap":
        lines.extend([
            "",
            f"def {name}(data: dict) -> None:",
            f'    """Converted from CUP Tap: {class_name}. Observe only, no modification."""',
        ])
        if source:
            lines.append(f"    # Original CUP source:")
            for src_line in source.strip().split("\n"):
                lines.append(f"    # {src_line}")
            lines.append("")
        lines.extend([
            "    # TODO: implement observation logic (logging, metrics, etc.)",
            "    pass",
        ])

    elif step_type == "hook":
        lines.extend([
            "",
            f"class {class_name}Hook:",
            f'    """Converted from CUP Hook: {class_name}."""',
            "",
            "    def before(self, step_name, data):",
            '        """Called before each step."""',
            "        pass",
            "",
            "    def after(self, step_name, data):",
            '        """Called after each step."""',
            "        pass",
            "",
            "    def on_error(self, step_name, error, data):",
            '        """Called when a step raises."""',
            "        pass",
        ])

    lines.append("")
    return "\n".join(lines)


def _generate_orchestrator(
    steps: List[Dict[str, Any]],
    hooks: List[Dict[str, Any]],
    classified: Dict[str, List[Dict[str, Any]]],
    config: Dict[str, Any],
) -> str:
    """Generate the main orchestrator that calls all steps in sequence."""
    output = config.get("output", {})
    base = output.get("base", "src/")

    lines = [
        '"""',
        "Pipeline orchestrator — calls all steps in sequence.",
        f"Converted from CUP Pipeline. Pattern: {config.get('pattern', 'flat')}",
        '"""',
        "",
    ]

    # Imports
    for role, role_steps in classified.items():
        target_dir = output.get(role, f"{role}/")
        module_base = target_dir.rstrip("/").replace("/", ".")
        for step in role_steps:
            name = step.get("name", step.get("class_name", "unknown"))
            step_type = step.get("type", "filter")
            if step_type == "hook":
                lines.append(f"from {module_base}.{name} import {step.get('class_name', name)}Hook")
            else:
                fn_name = name
                lines.append(f"from {module_base}.{name} import {fn_name}")
                if step_type == "valve":
                    lines.append(f"from {module_base}.{name} import {fn_name}_predicate")

    lines.extend(["", "", "def run_pipeline(data: dict) -> dict:", '    """Execute all steps in order."""'])

    # Step calls in original order
    for step in steps:
        name = step["name"]
        step_type = step["type"]
        if step_type == "valve":
            lines.append(f"    if {name}_predicate(data):")
            lines.append(f"        data = {name}(data)")
        elif step_type == "tap":
            lines.append(f"    {name}(data)")
        else:
            lines.append(f"    data = {name}(data)")

    lines.extend([
        "    return data",
        "",
    ])

    return "\n".join(lines)
