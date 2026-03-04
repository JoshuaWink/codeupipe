"""
Valve: Conditional Flow Control

A Valve wraps a Filter with a predicate — the inner filter only executes
when the predicate evaluates to True. Otherwise the payload passes through unchanged.
Valves conform to the Filter protocol, so they compose seamlessly into Pipelines.
"""

from typing import Callable, Generic, TypeVar
from .payload import Payload
from .filter import Filter

__all__ = ["Valve"]

TInput = TypeVar('TInput')
TOutput = TypeVar('TOutput')


class Valve(Generic[TInput, TOutput]):
    """
    Conditional flow control — gates a Filter with a predicate.

    If the predicate returns True, the inner filter processes the payload.
    If False, the payload passes through unchanged.

    Conforms to the Filter protocol so it can be used anywhere a Filter is expected.
    """

    def __init__(
        self,
        name: str,
        inner: Filter[TInput, TOutput],
        predicate: Callable[[Payload[TInput]], bool],
    ):
        self.name = name
        self._inner = inner
        self._predicate = predicate

    async def call(self, payload: Payload[TInput]) -> Payload[TOutput]:
        """Execute the inner filter only if the predicate passes."""
        if self._predicate(payload):
            return await self._inner.call(payload)
        return payload  # type: ignore — pass through unchanged

    def __repr__(self) -> str:
        return f"Valve({self.name!r})"
