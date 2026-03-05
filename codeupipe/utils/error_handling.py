"""
Error Handling: The Resilience Layer

Handle errors comprehensively, with retry logic and proper error propagation.
"""

import inspect
from typing import Callable, Optional, List, Tuple
from codeupipe.core.payload import Payload
from codeupipe.core.filter import Filter

__all__ = ["ErrorHandlingMixin", "RetryFilter"]


class ErrorHandlingMixin:
    """
    Mixin for pipelines to handle errors with routing.
    """

    def __init__(self):
        self.error_connections: List[Tuple[str, str, Callable[[Exception], bool]]] = []

    def on_error(self, source: str, handler: str, condition: Callable[[Exception], bool]) -> None:
        """Add error routing."""
        self.error_connections.append((source, handler, condition))

    async def _handle_error(self, filter_name: str, error: Exception, payload: Payload) -> Optional[Payload]:
        """Find and call the matching error handler."""
        for src, hdl, cond in self.error_connections:
            if src == filter_name and cond(error):
                handler = getattr(self, 'filters', {}).get(hdl)
                if handler and hasattr(handler, 'call'):
                    result = handler.call(payload.insert("error", str(error)))
                    if inspect.isawaitable(result):
                        result = await result
                    return result
        return None


class RetryFilter:
    """Retry wrapper — wraps a filter with retry logic for resilience."""

    def __init__(self, inner_filter: Filter, max_retries: int = 3):
        self.inner = inner_filter
        self.max_retries = max(0, max_retries)

    @staticmethod
    async def _invoke(fn, *args):
        """Call fn(*args), awaiting the result only if it is a coroutine."""
        result = fn(*args)
        if inspect.isawaitable(result):
            result = await result
        return result

    async def call(self, payload: Payload) -> Payload:
        if self.max_retries == 0:
            try:
                return await self._invoke(self.inner.call, payload)
            except Exception as e:
                return payload.insert("error", f"Max retries: {e}")

        for attempt in range(self.max_retries):
            try:
                return await self._invoke(self.inner.call, payload)
            except Exception as e:
                if attempt == self.max_retries - 1:
                    return payload.insert("error", f"Max retries: {e}")
        return payload