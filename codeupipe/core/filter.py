"""
Filter Protocol: The Processing Unit

The Filter protocol defines the interface for payload processors.
Each Filter takes a Payload in, processes it, and returns a (potentially transformed) Payload out.
Enhanced with generic typing for type-safe workflows.
"""

from typing import Protocol, TypeVar
from .payload import Payload

__all__ = ["Filter"]

TInput = TypeVar('TInput')
TOutput = TypeVar('TOutput')


class Filter(Protocol[TInput, TOutput]):
    """
    Processing unit — takes a payload in, returns a transformed payload out.
    The core protocol that all filter implementations must follow.
    Enhanced with generic typing for type-safe workflows.
    """

    async def call(self, payload: Payload[TInput]) -> Payload[TOutput]:
        """Process the payload and return a transformed result."""
        ...
