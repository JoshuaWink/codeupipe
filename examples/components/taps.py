"""
Tap Components: Reusable Tap Implementations
"""

from codeupipe.core.payload import Payload

__all__ = ["PrintTap", "CollectorTap"]


class PrintTap:
    """Tap that prints payload data for debugging."""

    def __init__(self, label: str = "TAP"):
        self.label = label

    async def observe(self, payload: Payload) -> None:
        print(f"[{self.label}] {payload.to_dict()}")


class CollectorTap:
    """Tap that collects payload snapshots for later inspection."""

    def __init__(self):
        self.snapshots = []

    async def observe(self, payload: Payload) -> None:
        self.snapshots.append(payload.to_dict())
