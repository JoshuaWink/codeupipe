"""
Tests for Payload Classes

Testing immutable Payload and mutable MutablePayload functionality.
"""

import pytest
from codeupipe.core.payload import Payload, MutablePayload


class TestPayload:
    """Test the immutable Payload class."""

    @pytest.mark.unit
    @pytest.mark.core
    def test_empty_payload(self):
        """Test creating an empty payload."""
        p = Payload()
        assert p.get("nonexistent") is None
        assert p.to_dict() == {}

    @pytest.mark.unit
    @pytest.mark.core
    def test_payload_with_data(self):
        """Test creating payload with initial data."""
        data = {"name": "Alice", "age": 30}
        p = Payload(data)
        assert p.get("name") == "Alice"
        assert p.get("age") == 30
        assert p.get("nonexistent") is None

    @pytest.mark.unit
    @pytest.mark.core
    def test_insert_immutability(self):
        """Test that insert returns new payload without modifying original."""
        p1 = Payload({"name": "Alice"})
        p2 = p1.insert("age", 30)

        assert p1.get("age") is None
        assert p1.get("name") == "Alice"
        assert p2.get("age") == 30
        assert p2.get("name") == "Alice"
        assert p1 is not p2

    @pytest.mark.unit
    @pytest.mark.core
    def test_merge_payloads(self):
        """Test merging two payloads."""
        p1 = Payload({"name": "Alice", "age": 30})
        p2 = Payload({"city": "Wonderland", "age": 25})

        merged = p1.merge(p2)

        assert merged.get("name") == "Alice"
        assert merged.get("city") == "Wonderland"
        assert merged.get("age") == 25  # from p2

        assert p1.get("age") == 30
        assert p2.get("city") == "Wonderland"

    @pytest.mark.unit
    @pytest.mark.core
    def test_to_dict(self):
        """Test converting payload to dictionary."""
        data = {"name": "Alice", "age": 30}
        p = Payload(data)
        dict_result = p.to_dict()

        assert dict_result == data
        assert dict_result is not data

        dict_result["new_key"] = "new_value"
        assert p.get("new_key") is None

    @pytest.mark.unit
    @pytest.mark.core
    def test_with_mutation(self):
        """Test converting to mutable payload."""
        p = Payload({"name": "Alice"})
        mutable = p.with_mutation()

        assert isinstance(mutable, MutablePayload)
        assert mutable.get("name") == "Alice"

        mutable.set("name", "Bob")
        assert p.get("name") == "Alice"
        assert mutable.get("name") == "Bob"

    @pytest.mark.unit
    @pytest.mark.core
    def test_repr(self):
        """Test string representation."""
        p = Payload({"name": "Alice"})
        repr_str = repr(p)
        assert "Payload" in repr_str
        assert "Alice" in repr_str

    @pytest.mark.unit
    @pytest.mark.core
    def test_get_with_default_value(self):
        """Test get() method with default parameter."""
        p = Payload({"name": "Alice", "age": 30})

        assert p.get("name", "default") == "Alice"
        assert p.get("age", 0) == 30
        assert p.get("missing", "default_value") == "default_value"
        assert p.get("missing", 0) == 0
        assert p.get("missing", False) is False
        assert p.get("missing", []) == []
        assert p.get("missing", {}) == {}
        assert p.get("missing") is None

    @pytest.mark.unit
    @pytest.mark.core
    def test_get_with_falsy_values(self):
        """Test that default parameter works correctly with falsy stored values."""
        p = Payload({
            "zero": 0,
            "false": False,
            "empty_string": "",
            "empty_list": [],
            "none": None
        })

        assert p.get("zero", 999) == 0
        assert p.get("false", True) is False
        assert p.get("empty_string", "default") == ""
        assert p.get("empty_list", ["default"]) == []
        assert p.get("none", "default") is None


class TestMutablePayload:
    """Test the mutable MutablePayload class."""

    @pytest.mark.unit
    @pytest.mark.core
    def test_mutable_payload_creation(self):
        """Test creating mutable payload."""
        data = {"name": "Alice"}
        mutable = MutablePayload(data)
        assert mutable.get("name") == "Alice"

    @pytest.mark.unit
    @pytest.mark.core
    def test_set_value(self):
        """Test setting values in mutable payload."""
        mutable = MutablePayload({})
        mutable.set("name", "Alice")
        mutable.set("age", 30)

        assert mutable.get("name") == "Alice"
        assert mutable.get("age") == 30

    @pytest.mark.unit
    @pytest.mark.core
    def test_to_immutable(self):
        """Test converting mutable payload to immutable."""
        mutable = MutablePayload({"name": "Alice"})
        mutable.set("age", 30)

        immutable = mutable.to_immutable()

        assert isinstance(immutable, Payload)
        assert immutable.get("name") == "Alice"
        assert immutable.get("age") == 30

        mutable.set("name", "Bob")
        assert immutable.get("name") == "Alice"
        assert mutable.get("name") == "Bob"

    @pytest.mark.unit
    @pytest.mark.core
    def test_mutable_repr(self):
        """Test string representation of mutable payload."""
        mutable = MutablePayload({"name": "Alice"})
        repr_str = repr(mutable)
        assert "MutablePayload" in repr_str
        assert "Alice" in repr_str
