"""
Adapter discovery via Python entry points.

External deploy adapters register under the 'codeupipe.deploy' entry point
group. This module discovers them at runtime using stdlib importlib.metadata.
"""

import importlib.metadata
from typing import Dict

from .adapter import DeployAdapter

__all__ = ["find_adapters"]

_ENTRY_POINT_GROUP = "codeupipe.deploy"


def find_adapters() -> Dict[str, DeployAdapter]:
    """Discover all installed deploy adapters via entry points.

    Returns a dict mapping target name → adapter instance.
    The built-in DockerAdapter is always included.
    """
    from .docker import DockerAdapter

    adapters: Dict[str, DeployAdapter] = {}

    # Built-in adapter — always available
    docker = DockerAdapter()
    adapters[docker.target().name] = docker

    # External adapters via entry points
    try:
        eps = importlib.metadata.entry_points()
        # Python 3.9/3.10: eps is a dict; 3.12+: eps has .select()
        if hasattr(eps, "select"):
            entries = eps.select(group=_ENTRY_POINT_GROUP)
        else:
            entries = eps.get(_ENTRY_POINT_GROUP, [])

        for ep in entries:
            try:
                adapter_cls = ep.load()
                adapter = adapter_cls()
                adapters[ep.name] = adapter
            except Exception:
                pass  # Skip broken adapters silently
    except Exception:
        pass  # Entry point discovery failed; built-in still available

    return adapters
