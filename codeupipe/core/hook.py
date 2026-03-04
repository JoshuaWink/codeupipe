"""
Hook ABC: The Enhancement Layer

The Hook ABC defines optional lifecycle hooks for pipeline execution.
Subclasses can override any combination of before(), after(), and on_error().
"""

from abc import ABC
from typing import Optional, TypeVar
from .payload import Payload
from .filter import Filter

__all__ = ["Hook"]

T = TypeVar('T')


class Hook(ABC):
    """
    Lifecycle hook for pipeline execution.
    Subclasses can override any combination of before(), after(), and on_error().
    """

    async def before(self, filter: Optional[Filter], payload: Payload[T]) -> None:
        """Called before a filter executes, or before the pipeline starts (filter=None)."""
        pass

    async def after(self, filter: Optional[Filter], payload: Payload[T]) -> None:
        """Called after a filter executes, or after the pipeline ends (filter=None)."""
        pass

    async def on_error(self, filter: Optional[Filter], error: Exception, payload: Payload[T]) -> None:
        """Called when an error occurs."""
        pass