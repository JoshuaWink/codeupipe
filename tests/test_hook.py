"""
Tests for Hook ABC

Testing the Hook abstract base class with concrete implementations.
"""

import pytest
from abc import ABC
from codeupipe.core.payload import Payload
from codeupipe.core.filter import Filter
from codeupipe.core.hook import Hook


class TestHookProtocol:
    """Test the Hook ABC interface."""

    @pytest.mark.unit
    @pytest.mark.core
    def test_hook_is_abc(self):
        """Test that Hook is an abstract base class."""
        assert issubclass(Hook, ABC)

    @pytest.mark.unit
    @pytest.mark.core
    def test_hook_abstract_methods(self):
        """Test that Hook has the expected methods."""
        assert hasattr(Hook, 'before')
        assert hasattr(Hook, 'after')
        assert hasattr(Hook, 'on_error')


class LoggingHook(Hook):
    """Concrete hook implementation for testing."""

    def __init__(self):
        self.before_calls = []
        self.after_calls = []
        self.error_calls = []

    async def before(self, filter, payload: Payload) -> None:
        self.before_calls.append((filter, payload.get("step")))

    async def after(self, filter, payload: Payload) -> None:
        self.after_calls.append((filter, payload.get("step")))

    async def on_error(self, filter, error: Exception, payload: Payload) -> None:
        self.error_calls.append((filter, str(error), payload.get("step")))


class TimingHook(Hook):
    """Hook that tracks execution timing."""

    def __init__(self):
        self.timings = {}
        self.start_times = {}

    async def before(self, filter, payload: Payload) -> None:
        import time
        filter_id = "pipeline" if filter is None else id(filter)
        self.start_times[filter_id] = time.time()

    async def after(self, filter, payload: Payload) -> None:
        import time
        filter_id = "pipeline" if filter is None else id(filter)
        if filter_id in self.start_times:
            duration = time.time() - self.start_times[filter_id]
            self.timings[filter_id] = duration

    async def on_error(self, filter, error: Exception, payload: Payload) -> None:
        filter_id = "pipeline" if filter is None else id(filter)
        if filter_id in self.start_times:
            del self.start_times[filter_id]


class TestLoggingHook:
    """Test the LoggingHook implementation."""

    @pytest.mark.unit
    @pytest.mark.core
    def test_before_hook(self):
        """Test the before hook logging."""
        hook = LoggingHook()

        async def run_test():
            payload = Payload({"step": "init"})
            await hook.before(None, payload)

            assert len(hook.before_calls) == 1
            assert hook.before_calls[0] == (None, "init")

        import asyncio
        asyncio.run(run_test())

    @pytest.mark.unit
    @pytest.mark.core
    def test_after_hook(self):
        """Test the after hook logging."""
        hook = LoggingHook()

        async def run_test():
            payload = Payload({"step": "complete"})
            await hook.after(None, payload)

            assert len(hook.after_calls) == 1
            assert hook.after_calls[0] == (None, "complete")

        import asyncio
        asyncio.run(run_test())

    @pytest.mark.unit
    @pytest.mark.core
    def test_error_hook(self):
        """Test the error hook logging."""
        hook = LoggingHook()

        async def run_test():
            payload = Payload({"step": "error"})
            error = ValueError("Test error")
            await hook.on_error(None, error, payload)

            assert len(hook.error_calls) == 1
            assert hook.error_calls[0] == (None, "Test error", "error")

        import asyncio
        asyncio.run(run_test())


class TestTimingHook:
    """Test the TimingHook implementation."""

    @pytest.mark.unit
    @pytest.mark.core
    def test_timing_measurement(self):
        """Test that timing hook measures execution time."""
        hook = TimingHook()

        async def run_test():
            import asyncio

            payload = Payload({"step": "test"})

            await hook.before(None, payload)
            await asyncio.sleep(0.01)
            await hook.after(None, payload)

            pipeline_id = "pipeline"
            assert pipeline_id in hook.timings
            assert hook.timings[pipeline_id] >= 0.01

        import asyncio
        asyncio.run(run_test())

    @pytest.mark.unit
    @pytest.mark.core
    def test_error_cleanup(self):
        """Test that timing is cleaned up on error."""
        hook = TimingHook()

        async def run_test():
            payload = Payload({"step": "test"})

            await hook.before(None, payload)
            pipeline_id = "pipeline"
            assert pipeline_id in hook.start_times

            error = RuntimeError("Test error")
            await hook.on_error(None, error, payload)

            assert pipeline_id not in hook.start_times

        import asyncio
        asyncio.run(run_test())
