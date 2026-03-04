"""
Tests for State (Pipeline Execution Metadata)

Testing the State class that tracks pipeline execution.
"""

import pytest
from codeupipe.core.state import State


class TestState:
    """Test the State execution metadata tracker."""

    @pytest.mark.unit
    @pytest.mark.core
    def test_initial_state(self):
        """Test that State starts empty."""
        state = State()
        assert state.executed == []
        assert state.skipped == []
        assert state.errors == []
        assert state.metadata == {}
        assert state.has_errors is False
        assert state.last_error is None

    @pytest.mark.unit
    @pytest.mark.core
    def test_mark_executed(self):
        """Test marking filters as executed."""
        state = State()
        state.mark_executed("filter_a")
        state.mark_executed("filter_b")
        assert state.executed == ["filter_a", "filter_b"]

    @pytest.mark.unit
    @pytest.mark.core
    def test_mark_skipped(self):
        """Test marking filters as skipped."""
        state = State()
        state.mark_skipped("gated_filter")
        assert state.skipped == ["gated_filter"]

    @pytest.mark.unit
    @pytest.mark.core
    def test_record_error(self):
        """Test recording errors."""
        state = State()
        err = ValueError("something broke")
        state.record_error("bad_filter", err)

        assert state.has_errors is True
        assert state.last_error is err
        assert len(state.errors) == 1
        assert state.errors[0] == ("bad_filter", err)

    @pytest.mark.unit
    @pytest.mark.core
    def test_metadata(self):
        """Test arbitrary metadata storage."""
        state = State()
        state.set("duration_ms", 42)
        assert state.get("duration_ms") == 42
        assert state.get("missing") is None
        assert state.get("missing", "default") == "default"

    @pytest.mark.unit
    @pytest.mark.core
    def test_reset(self):
        """Test resetting state."""
        state = State()
        state.mark_executed("a")
        state.mark_skipped("b")
        state.record_error("c", RuntimeError("err"))
        state.set("key", "val")

        state.reset()

        assert state.executed == []
        assert state.skipped == []
        assert state.errors == []
        assert state.metadata == {}

    @pytest.mark.unit
    @pytest.mark.core
    def test_repr(self):
        """Test string representation."""
        state = State()
        state.mark_executed("a")
        state.mark_skipped("b")
        repr_str = repr(state)
        assert "State" in repr_str
        assert "a" in repr_str
        assert "b" in repr_str
