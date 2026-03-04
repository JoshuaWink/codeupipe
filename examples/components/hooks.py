"""
Hook Components: Reusable Hook Implementations
"""

from typing import Optional
from codeupipe.core.payload import Payload
from codeupipe.core.filter import Filter
from codeupipe.core.hook import Hook

__all__ = ["LoggingHook", "TimingHook", "BeforeOnlyHook"]


class BeforeOnlyHook(Hook):
    """Hook that only implements before — demonstrates flexibility."""

    async def before(self, filter: Optional[Filter], payload: Payload) -> None:
        print(f"Starting execution with payload: {payload}")


class LoggingHook(Hook):
    """Logging hook for pipeline observation."""

    async def before(self, filter: Optional[Filter], payload: Payload) -> None:
        print(f"Before filter {filter}: {payload}")

    async def after(self, filter: Optional[Filter], payload: Payload) -> None:
        print(f"After filter {filter}: {payload}")


class TimingHook(Hook):
    """Timing hook for performance observation."""

    def __init__(self):
        self.start_times = {}

    async def before(self, filter: Optional[Filter], payload: Payload) -> None:
        import time
        if filter:
            self.start_times[id(filter)] = time.time()

    async def after(self, filter: Optional[Filter], payload: Payload) -> None:
        import time
        if filter and id(filter) in self.start_times:
            duration = time.time() - self.start_times[id(filter)]
            print(f"Filter {filter} took {duration:.2f}s")
            del self.start_times[id(filter)]

    async def on_error(self, filter: Optional[Filter], error: Exception, payload: Payload) -> None:
        import time
        if filter and id(filter) in self.start_times:
            duration = time.time() - self.start_times[id(filter)]
            print(f"Error in filter {filter} after {duration:.2f}s: {error}")
            del self.start_times[id(filter)]
