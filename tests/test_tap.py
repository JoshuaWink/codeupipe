"""
Tests for Tap

Testing non-modifying observation points.
"""

import pytest
import asyncio
from codeupipe.core.payload import Payload
from codeupipe.core.tap import Tap


class TestTapProtocol:
    """Test the Tap protocol interface."""

    @pytest.mark.unit
    @pytest.mark.core
    def test_tap_is_protocol(self):
        """Test that Tap is a protocol."""
        from typing import Protocol
        assert issubclass(Tap, Protocol)


class LoggingTap:
    """Concrete Tap for testing — records observations."""

    def __init__(self):
        self.observations = []

    async def observe(self, payload: Payload) -> None:
        self.observations.append(payload.to_dict())


class CountingTap:
    """Tap that counts how many times it's been observed."""

    def __init__(self):
        self.count = 0

    async def observe(self, payload: Payload) -> None:
        self.count += 1


class TestLoggingTap:
    """Test the LoggingTap implementation."""

    @pytest.mark.unit
    @pytest.mark.core
    def test_observe_records_data(self):
        """Test that observe records payload data."""
        tap = LoggingTap()

        async def run_test():
            payload = Payload({"value": 42, "status": "ok"})
            await tap.observe(payload)

            assert len(tap.observations) == 1
            assert tap.observations[0] == {"value": 42, "status": "ok"}

        asyncio.run(run_test())

    @pytest.mark.unit
    @pytest.mark.core
    def test_multiple_observations(self):
        """Test multiple observations."""
        tap = LoggingTap()

        async def run_test():
            await tap.observe(Payload({"step": 1}))
            await tap.observe(Payload({"step": 2}))
            await tap.observe(Payload({"step": 3}))

            assert len(tap.observations) == 3
            assert tap.observations[0]["step"] == 1
            assert tap.observations[2]["step"] == 3

        asyncio.run(run_test())


class TestCountingTap:
    """Test the CountingTap implementation."""

    @pytest.mark.unit
    @pytest.mark.core
    def test_counting(self):
        """Test that counting tap increments correctly."""
        tap = CountingTap()

        async def run_test():
            for _ in range(5):
                await tap.observe(Payload())
            assert tap.count == 5

        asyncio.run(run_test())
