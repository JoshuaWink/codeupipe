"""
Filter Components: Reusable Filter Implementations
"""

from codeupipe.core.payload import Payload
from codeupipe.core.filter import Filter

__all__ = ["IdentityFilter", "MathFilter"]


class IdentityFilter(Filter):
    """Pass-through filter that does nothing."""

    async def call(self, payload: Payload) -> Payload:
        return payload


class MathFilter(Filter):
    """Math-focused filter."""

    def __init__(self, operation: str = "sum"):
        self.operation = operation

    async def call(self, payload: Payload) -> Payload:
        numbers = payload.get("numbers")
        if isinstance(numbers, list) and numbers:
            if self.operation == "sum":
                result = sum(numbers)
            elif self.operation == "mean":
                result = sum(numbers) / len(numbers)
            else:
                result = 0
            return payload.insert("result", result)
        return payload.insert("error", "Invalid numbers")
