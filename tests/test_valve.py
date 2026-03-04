"""
Tests for Valve

Testing conditional flow control with Valve.
"""

import pytest
import asyncio
from codeupipe.core.payload import Payload
from codeupipe.core.valve import Valve


class TestValve:
    """Test the Valve condtional flow control."""

    @pytest.mark.unit
    @pytest.mark.core
    def test_valve_passes_when_true(self):
        """Test that Valve executes inner filter when predicate is True."""

        class InnerFilter:
            async def call(self, payload):
                return payload.insert("ran", True)

        valve = Valve("test_valve", InnerFilter(), lambda p: True)

        async def run_test():
            result = await valve.call(Payload())
            assert result.get("ran") is True

        asyncio.run(run_test())

    @pytest.mark.unit
    @pytest.mark.core
    def test_valve_blocks_when_false(self):
        """Test that Valve passes through unchanged when predicate is False."""

        class InnerFilter:
            async def call(self, payload):
                return payload.insert("ran", True)

        valve = Valve("test_valve", InnerFilter(), lambda p: False)

        async def run_test():
            payload = Payload({"original": "data"})
            result = await valve.call(payload)
            assert result.get("ran") is None
            assert result.get("original") == "data"

        asyncio.run(run_test())

    @pytest.mark.unit
    @pytest.mark.core
    def test_valve_predicate_uses_payload(self):
        """Test that Valve predicate receives the payload."""

        class InnerFilter:
            async def call(self, payload):
                return payload.insert("processed", True)

        valve = Valve("age_check", InnerFilter(), lambda p: (p.get("age") or 0) >= 18)

        async def run_test():
            # Should pass
            result = await valve.call(Payload({"age": 20}))
            assert result.get("processed") is True

            # Should block
            result = await valve.call(Payload({"age": 15}))
            assert result.get("processed") is None

        asyncio.run(run_test())

    @pytest.mark.unit
    @pytest.mark.core
    def test_valve_repr(self):
        """Test Valve string representation."""

        class Dummy:
            async def call(self, payload):
                return payload

        valve = Valve("my_valve", Dummy(), lambda p: True)
        assert "my_valve" in repr(valve)

    @pytest.mark.unit
    @pytest.mark.core
    def test_valve_conforms_to_filter_protocol(self):
        """Test that Valve has the same call() interface as Filter."""
        class Dummy:
            async def call(self, payload):
                return payload

        valve = Valve("test", Dummy(), lambda p: True)
        assert hasattr(valve, 'call')
        assert callable(valve.call)
