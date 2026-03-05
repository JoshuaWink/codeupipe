"""
AnalyzePipelineFilter: Introspects a CUP Pipeline and extracts its step manifest.
"""

import inspect
from typing import Any, Dict, List
from codeupipe import Payload


class AnalyzePipelineFilter:
    """
    Filter: Analyze a CUP Pipeline instance and extract step metadata.

    Input payload keys:
        - pipeline: A Pipeline instance to analyze

    Output payload adds:
        - steps (list[dict]): Step manifest with name, type, class info
        - hooks (list[dict]): Hook manifest with class info
    """

    def call(self, payload):
        pipeline = payload.get("pipeline")
        if pipeline is None:
            raise ValueError("Payload must contain 'pipeline' key")

        steps = []
        for name, instance in pipeline._steps:
            step_type = pipeline._step_types.get(name, "filter")
            info: Dict[str, Any] = {
                "name": name,
                "type": step_type,
                "class_name": instance.__class__.__name__,
                "is_valve": hasattr(instance, "_predicate"),
            }

            if info["is_valve"]:
                info["type"] = "valve"
                info["inner_class"] = instance._inner.__class__.__name__

            # Try to capture source for export
            try:
                info["source"] = inspect.getsource(instance.__class__)
            except (OSError, TypeError):
                info["source"] = None

            steps.append(info)

        hooks: List[Dict[str, Any]] = []
        for hook in pipeline._hooks:
            hook_info: Dict[str, Any] = {
                "class_name": hook.__class__.__name__,
                "type": "hook",
            }
            try:
                hook_info["source"] = inspect.getsource(hook.__class__)
            except (OSError, TypeError):
                hook_info["source"] = None
            hooks.append(hook_info)

        return payload.insert("steps", steps).insert("hooks", hooks)
