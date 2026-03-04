"""
Tests for Filter Protocol

Testing the Filter protocol with concrete implementations.
"""

import pytest
from codeupipe.core.payload import Payload
from codeupipe.core.filter import Filter


class TestFilterProtocol:
    """Test the Filter protocol interface."""

    @pytest.mark.unit
    @pytest.mark.core
    def test_filter_is_protocol(self):
        """Test that Filter is a protocol."""
        from typing import Protocol
        assert issubclass(Filter, Protocol)


class SimpleProcessingFilter:
    """Concrete Filter implementation for testing."""

    def __init__(self, name: str = "test"):
        self.name = name

    async def call(self, payload: Payload) -> Payload:
        """Simple processing: add a 'processed' field."""
        return payload.insert("processed", True).insert("processor", self.name)


class DataTransformationFilter:
    """Filter that transforms data."""

    async def call(self, payload: Payload) -> Payload:
        """Transform data by doubling numbers and uppercasing strings."""
        data = payload.get("data")
        if isinstance(data, list):
            transformed = []
            for item in data:
                if isinstance(item, bool):
                    transformed.append(item)
                elif isinstance(item, (int, float)):
                    transformed.append(item * 2)
                elif isinstance(item, str):
                    transformed.append(item.upper())
                else:
                    transformed.append(item)
            return payload.insert("transformed", transformed)
        return payload.insert("transformed", data)


class ValidationFilter:
    """Filter that validates input data."""

    def __init__(self, required_fields: list):
        self.required_fields = required_fields

    async def call(self, payload: Payload) -> Payload:
        """Validate required fields exist."""
        for field in self.required_fields:
            if payload.get(field) is None:
                return payload.insert("error", f"Missing required field: {field}")
        return payload.insert("validated", True)


class FailingFilter:
    """Filter that always fails for testing error handling."""

    async def call(self, payload: Payload) -> Payload:
        """Always raise an exception."""
        raise ValueError("Intentional failure for testing")


class TestSimpleProcessingFilter:
    """Test the SimpleProcessingFilter implementation."""

    @pytest.mark.unit
    @pytest.mark.core
    def test_simple_processing(self):
        """Test basic processing functionality."""
        f = SimpleProcessingFilter("test_processor")

        async def run_test():
            payload = Payload({"input": "test_data"})
            result = await f.call(payload)

            assert result.get("processed") is True
            assert result.get("processor") == "test_processor"
            assert result.get("input") == "test_data"

        import asyncio
        asyncio.run(run_test())

    @pytest.mark.unit
    @pytest.mark.core
    def test_empty_payload_processing(self):
        """Test processing with empty payload."""
        f = SimpleProcessingFilter()

        async def run_test():
            payload = Payload()
            result = await f.call(payload)

            assert result.get("processed") is True
            assert result.get("processor") == "test"

        import asyncio
        asyncio.run(run_test())


class TestDataTransformationFilter:
    """Test the DataTransformationFilter implementation."""

    @pytest.mark.unit
    @pytest.mark.core
    def test_numeric_transformation(self):
        """Test transforming numeric data."""
        f = DataTransformationFilter()

        async def run_test():
            payload = Payload({"data": [1, 2, 3, 4.5]})
            result = await f.call(payload)

            transformed = result.get("transformed")
            assert transformed == [2, 4, 6, 9.0]

        import asyncio
        asyncio.run(run_test())

    @pytest.mark.unit
    @pytest.mark.core
    def test_string_transformation(self):
        """Test transforming string data."""
        f = DataTransformationFilter()

        async def run_test():
            payload = Payload({"data": ["hello", "world"]})
            result = await f.call(payload)

            transformed = result.get("transformed")
            assert transformed == ["HELLO", "WORLD"]

        import asyncio
        asyncio.run(run_test())

    @pytest.mark.unit
    @pytest.mark.core
    def test_mixed_data_transformation(self):
        """Test transforming mixed data types."""
        f = DataTransformationFilter()

        async def run_test():
            payload = Payload({"data": ["hello", 42, True]})
            result = await f.call(payload)

            transformed = result.get("transformed")
            assert transformed == ["HELLO", 84, True]

        import asyncio
        asyncio.run(run_test())

    @pytest.mark.unit
    @pytest.mark.core
    def test_non_list_data(self):
        """Test with non-list data."""
        f = DataTransformationFilter()

        async def run_test():
            payload = Payload({"data": "single_value"})
            result = await f.call(payload)

            assert result.get("transformed") == "single_value"

        import asyncio
        asyncio.run(run_test())


class TestValidationFilter:
    """Test the ValidationFilter implementation."""

    @pytest.mark.unit
    @pytest.mark.core
    def test_successful_validation(self):
        """Test validation with all required fields present."""
        f = ValidationFilter(["name", "email"])

        async def run_test():
            payload = Payload({"name": "Alice", "email": "alice@example.com", "age": 30})
            result = await f.call(payload)

            assert result.get("validated") is True
            assert result.get("error") is None

        import asyncio
        asyncio.run(run_test())

    @pytest.mark.unit
    @pytest.mark.core
    def test_failed_validation(self):
        """Test validation with missing required fields."""
        f = ValidationFilter(["name", "email"])

        async def run_test():
            payload = Payload({"name": "Alice"})
            result = await f.call(payload)

            assert result.get("error") == "Missing required field: email"
            assert result.get("validated") is None

        import asyncio
        asyncio.run(run_test())


class TestFailingFilter:
    """Test the FailingFilter for error testing."""

    @pytest.mark.unit
    @pytest.mark.core
    def test_filter_raises_exception(self):
        """Test that FailingFilter raises ValueError."""
        f = FailingFilter()

        async def run_test():
            payload = Payload({"input": "test"})
            with pytest.raises(ValueError, match="Intentional failure"):
                await f.call(payload)

        import asyncio
        asyncio.run(run_test())


class TestFilterIntegration:
    """Integration test: filter chaining."""

    @pytest.mark.integration
    @pytest.mark.core
    def test_filter_chaining(self):
        """Test chaining multiple filters together manually."""
        process = SimpleProcessingFilter("proc")
        validate = ValidationFilter(["processed"])

        async def run_test():
            payload = Payload({"input": "data"})
            mid = await process.call(payload)
            result = await validate.call(mid)

            assert result.get("processed") is True
            assert result.get("validated") is True

        import asyncio
        asyncio.run(run_test())
