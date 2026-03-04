"""
Tests for Error Handling Utilities

Testing ErrorHandlingMixin and RetryFilter utilities.
"""

import pytest
from typing import Dict, List, Callable, Tuple
from codeupipe.core.payload import Payload
from codeupipe.utils.error_handling import ErrorHandlingMixin, RetryFilter
from .conftest import MockFilter


class TestErrorHandlingMixin:
    """Test the ErrorHandlingMixin functionality."""

    @pytest.mark.unit
    @pytest.mark.utils
    def test_mixin_initialization(self):
        """Test that mixin initializes correctly."""
        mixin = ErrorHandlingMixin()
        assert hasattr(mixin, 'error_connections')
        assert isinstance(mixin.error_connections, list)
        assert len(mixin.error_connections) == 0

    @pytest.mark.unit
    @pytest.mark.utils
    def test_on_error_registration(self):
        """Test registering error handlers."""
        mixin = ErrorHandlingMixin()

        def error_condition(error: Exception) -> bool:
            return isinstance(error, ValueError)

        mixin.on_error("source_filter", "handler_filter", error_condition)

        assert len(mixin.error_connections) == 1
        source, handler, condition = mixin.error_connections[0]
        assert source == "source_filter"
        assert handler == "handler_filter"
        assert condition == error_condition

    @pytest.mark.unit
    @pytest.mark.utils
    def test_error_handler_execution(self):
        """Test that error handlers are executed correctly."""
        mixin = ErrorHandlingMixin()

        filters = {
            "error_handler": MockFilter("mock", result_data={"error_handled": "processed"})
        }
        mixin.filters = filters  # type: ignore

        def value_error_condition(error: Exception) -> bool:
            return isinstance(error, ValueError)

        mixin.on_error("failing_filter", "error_handler", value_error_condition)

        async def run_test():
            payload = Payload({"input": "test"})
            error = ValueError("Test error")

            result = await mixin._handle_error("failing_filter", error, payload)

            assert result is not None
            assert result.get("error_handled") == "processed"

        import asyncio
        asyncio.run(run_test())

    @pytest.mark.unit
    @pytest.mark.utils
    def test_no_matching_error_handler(self):
        """Test behavior when no error handler matches."""
        mixin = ErrorHandlingMixin()

        def type_error_condition(error: Exception) -> bool:
            return isinstance(error, TypeError)

        mixin.on_error("failing_filter", "error_handler", type_error_condition)

        async def run_test():
            payload = Payload({"input": "test"})
            error = ValueError("Test error")

            result = await mixin._handle_error("failing_filter", error, payload)

            assert result is None

        import asyncio
        asyncio.run(run_test())

    @pytest.mark.unit
    @pytest.mark.utils
    def test_missing_error_handler_filter(self):
        """Test behavior when error handler filter doesn't exist."""
        mixin = ErrorHandlingMixin()

        def error_condition(error: Exception) -> bool:
            return True

        mixin.on_error("failing_filter", "nonexistent_handler", error_condition)

        async def run_test():
            payload = Payload({"input": "test"})
            error = ValueError("Test error")

            result = await mixin._handle_error("failing_filter", error, payload)

            assert result is None

        import asyncio
        asyncio.run(run_test())


class TestRetryFilter:
    """Test the RetryFilter functionality."""

    @pytest.mark.unit
    @pytest.mark.utils
    def test_successful_first_attempt(self):
        """Test that successful execution doesn't retry."""
        inner = MockFilter("success", result_data={"result": "success"})
        retry = RetryFilter(inner, max_retries=3)

        async def run_test():
            payload = Payload({"input": "test"})
            result = await retry.call(payload)

            assert result.get("result") == "success"
            assert result.get("input") == "test"

        import asyncio
        asyncio.run(run_test())

    @pytest.mark.unit
    @pytest.mark.utils
    def test_retry_on_failure(self):
        """Test retry behavior when inner filter fails."""
        call_count = 0

        class FailingThenSuccessFilter:
            async def call(self, payload: Payload) -> Payload:
                nonlocal call_count
                call_count += 1
                if call_count < 3:
                    raise ValueError(f"Attempt {call_count} failed")
                return payload.insert("result", f"success_on_attempt_{call_count}")

        inner = FailingThenSuccessFilter()
        retry = RetryFilter(inner, max_retries=5)

        async def run_test():
            payload = Payload({"input": "test"})
            result = await retry.call(payload)

            assert call_count == 3
            assert result.get("result") == "success_on_attempt_3"

        import asyncio
        asyncio.run(run_test())

    @pytest.mark.unit
    @pytest.mark.utils
    def test_max_retries_exceeded(self):
        """Test behavior when max retries is exceeded."""
        call_count = 0

        class AlwaysFailingFilter:
            async def call(self, payload: Payload) -> Payload:
                nonlocal call_count
                call_count += 1
                raise ValueError(f"Attempt {call_count} failed")

        inner = AlwaysFailingFilter()
        retry = RetryFilter(inner, max_retries=2)

        async def run_test():
            payload = Payload({"input": "test"})
            result = await retry.call(payload)

            assert call_count == 2
            assert result.get("error") == "Max retries: Attempt 2 failed"
            assert result.get("input") == "test"

        import asyncio
        asyncio.run(run_test())

    @pytest.mark.unit
    @pytest.mark.utils
    def test_zero_max_retries(self):
        """Test behavior with zero max retries."""
        call_count = 0

        class FailingFilter:
            async def call(self, payload: Payload) -> Payload:
                nonlocal call_count
                call_count += 1
                raise ValueError("Failed")

        inner = FailingFilter()
        retry = RetryFilter(inner, max_retries=0)

        async def run_test():
            payload = Payload({"input": "test"})
            result = await retry.call(payload)

            assert call_count == 1
            assert result.get("error") == "Max retries: Failed"
            assert result.get("input") == "test"

        import asyncio
        asyncio.run(run_test())


class TestErrorHandlingIntegration:
    """Integration tests for error handling functionality."""

    @pytest.mark.integration
    @pytest.mark.utils
    def test_retry_with_error_handling_pipeline(self):
        """Test combining retry logic with error handling."""

        class SimpleErrorHandlingPipeline(ErrorHandlingMixin):
            def __init__(self):
                super().__init__()
                self.filters = {}

            def add_filter(self, name: str, filter):
                self.filters[name] = filter

            async def run_with_error_handling(self, filter_name: str, payload: Payload) -> Payload:
                f = self.filters.get(filter_name)
                if not f:
                    raise ValueError(f"Filter {filter_name} not found")

                try:
                    return await f.call(payload)
                except Exception as e:
                    error_payload = await self._handle_error(filter_name, e, payload)
                    if error_payload:
                        return error_payload
                    raise

        pipeline = SimpleErrorHandlingPipeline()

        call_count = 0

        class IntermittentFailingFilter:
            async def call(self, payload: Payload) -> Payload:
                nonlocal call_count
                call_count += 1
                if call_count < 2:
                    raise ConnectionError("Temporary network error")
                return payload.insert("result", "success")

        retry_filter = RetryFilter(IntermittentFailingFilter(), max_retries=3)
        pipeline.add_filter("unreliable_service", retry_filter)

        class ErrorHandlerFilter:
            async def call(self, payload: Payload) -> Payload:
                return payload.insert("error_handled", True).insert("fallback_result", "default")

        pipeline.add_filter("error_handler", ErrorHandlerFilter())

        def connection_error_condition(error: Exception) -> bool:
            return isinstance(error, ConnectionError)

        pipeline.on_error("unreliable_service", "error_handler", connection_error_condition)

        async def run_test():
            payload = Payload({"input": "test"})
            result = await pipeline.run_with_error_handling("unreliable_service", payload)

            assert result.get("result") == "success"
            assert call_count == 2

        import asyncio
        asyncio.run(run_test())

    @pytest.mark.integration
    @pytest.mark.utils
    def test_complex_error_handling_scenario(self):
        """Test complex error handling with multiple handlers and conditions."""
        mixin = ErrorHandlingMixin()

        filters = {
            "validation_handler": MockFilter("validation_error_handled", result_data={"result": "validation_error_handled"}),
            "network_handler": MockFilter("network_error_handled", result_data={"result": "network_error_handled"}),
            "generic_handler": MockFilter("generic_error_handled", result_data={"result": "generic_error_handled"})
        }
        mixin.filters = filters  # type: ignore

        mixin.on_error("process", "validation_handler", lambda e: isinstance(e, ValueError))
        mixin.on_error("process", "network_handler", lambda e: isinstance(e, ConnectionError))
        mixin.on_error("process", "generic_handler", lambda e: True)

        async def run_test():
            payload = Payload({"input": "test"})

            result = await mixin._handle_error("process", ValueError("bad"), payload)
            assert result is not None
            assert result.get("result") == "validation_error_handled"

            result = await mixin._handle_error("process", ConnectionError("down"), payload)
            assert result is not None
            assert result.get("result") == "network_error_handled"

        import asyncio
        asyncio.run(run_test())
