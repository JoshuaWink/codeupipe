"""
Starter pipeline — replace with your prototype logic.

Run from the monorepo root so codeupipe is importable:
    python prototypes/PROTOTYPE_NAME/pipeline.py

Or from inside the prototype directory with an editable install:
    pip install -e ../../  # installs codeupipe from source
    python pipeline.py
"""

from codeupipe import Payload, Filter, Pipeline


class Hello(Filter):
    """Example filter — replace me."""

    def process(self, payload: Payload) -> Payload:
        payload["message"] = f"Hello from {payload.get('name', 'prototype')}!"
        return payload


if __name__ == "__main__":
    pipe = Pipeline([Hello()])
    result = pipe.run(Payload(name="customer"))
    print(result["message"])
