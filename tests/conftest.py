"""
Pytest configuration and shared fixtures for codeupipe tests.
"""

import pytest
import asyncio
from typing import Dict, Any, Optional, AsyncGenerator
from codeupipe.core.payload import Payload, MutablePayload


@pytest.fixture
def sample_payload() -> Payload:
    """Fixture providing a sample payload with test data."""
    return Payload({
        "user_id": 123,
        "name": "Alice",
        "email": "alice@example.com",
        "active": True
    })


@pytest.fixture
def empty_payload() -> Payload:
    """Fixture providing an empty payload."""
    return Payload()


@pytest.fixture
def mutable_payload() -> MutablePayload:
    """Fixture providing a mutable payload with test data."""
    return MutablePayload({
        "counter": 0,
        "status": "init"
    })


@pytest.fixture
def event_loop():
    """Fixture providing an event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def async_payload() -> AsyncGenerator[Payload, None]:
    """Async fixture providing a payload for async tests."""
    payload = Payload({"async_test": True, "step": "setup"})
    yield payload


class MockFilter:
    """Mock filter for testing."""

    def __init__(self, name: str = "mock", result_data: Optional[Dict[str, Any]] = None):
        self.name = name
        self._result_data = result_data or {}

    async def call(self, payload: Payload) -> Payload:
        result = payload
        for key, value in self._result_data.items():
            result = result.insert(key, value)
        return result


@pytest.fixture
def mock_filter():
    """Fixture providing a basic mock filter."""
    return MockFilter("test_filter")


@pytest.fixture
def failing_filter():
    """Fixture providing a mock filter that always fails."""
    return MockFilter("failing_filter")


@pytest.fixture
def processing_filter():
    """Fixture providing a mock filter that adds processing results."""
    return MockFilter("processor", result_data={"processed_data": "result", "status": "complete"})


def run_async(coro):
    """Helper to run async functions in sync tests."""
    return asyncio.run(coro)


def assert_payload_contains(payload: Payload, expected_data: dict):
    """Assert that payload contains all expected key-value pairs."""
    for key, expected_value in expected_data.items():
        actual_value = payload.get(key)
        assert actual_value == expected_value, f"Expected {key}={expected_value}, got {actual_value}"


def assert_payload_immutable(original: Payload, modified: Payload):
    """Assert that original payload was not modified when creating modified version."""
    assert original is not modified, "Payloads should be different objects"