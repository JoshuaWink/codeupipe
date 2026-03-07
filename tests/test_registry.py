"""Tests for Registry — Ring 2: Composability Layer."""

import pytest

from codeupipe import Payload


# ── Helpers ──────────────────────────────────────────────────

class DummyFilter:
    """A simple filter for testing."""
    def call(self, payload: Payload) -> Payload:
        return payload.insert("filtered", True)


class DummyTap:
    """A simple tap for testing."""
    def observe(self, payload: Payload) -> None:
        pass


class DummyStreamFilter:
    """A stream filter for testing."""
    async def stream(self, chunk: Payload):
        yield chunk


def dummy_factory(**kwargs):
    """Factory that returns a configured filter."""
    f = DummyFilter()
    f.config = kwargs
    return f


# ── Registration ─────────────────────────────────────────────

class TestRegistryBasics:
    """Core registration and retrieval."""

    def test_register_class_with_explicit_name(self):
        from codeupipe.registry import Registry
        reg = Registry()
        reg.register("my-filter", DummyFilter)
        instance = reg.get("my-filter")
        assert isinstance(instance, DummyFilter)

    def test_register_class_auto_name(self):
        """Passing just a class uses its __name__ as the key."""
        from codeupipe.registry import Registry
        reg = Registry()
        reg.register(DummyFilter)
        instance = reg.get("DummyFilter")
        assert isinstance(instance, DummyFilter)

    def test_register_factory_with_name(self):
        from codeupipe.registry import Registry
        reg = Registry()
        reg.register("custom", dummy_factory)
        instance = reg.get("custom", max_retries=3)
        assert instance.config == {"max_retries": 3}

    def test_register_factory_auto_name(self):
        from codeupipe.registry import Registry
        reg = Registry()
        reg.register(dummy_factory)
        instance = reg.get("dummy_factory")
        assert isinstance(instance, DummyFilter)

    def test_get_unknown_raises(self):
        from codeupipe.registry import Registry
        reg = Registry()
        with pytest.raises(KeyError, match="not-registered"):
            reg.get("not-registered")

    def test_register_duplicate_raises(self):
        from codeupipe.registry import Registry
        reg = Registry()
        reg.register("x", DummyFilter)
        with pytest.raises(ValueError, match="already registered"):
            reg.register("x", DummyFilter)

    def test_register_duplicate_force(self):
        """force=True allows overwriting."""
        from codeupipe.registry import Registry
        reg = Registry()
        reg.register("x", DummyFilter)
        reg.register("x", DummyTap, force=True)
        assert isinstance(reg.get("x"), DummyTap)

    def test_get_with_kwargs_passes_to_constructor(self):
        from codeupipe.registry import Registry
        reg = Registry()
        reg.register("factory", dummy_factory)
        inst = reg.get("factory", backoff=2.0)
        assert inst.config == {"backoff": 2.0}

    def test_get_fresh_instance_each_call(self):
        from codeupipe.registry import Registry
        reg = Registry()
        reg.register(DummyFilter)
        a = reg.get("DummyFilter")
        b = reg.get("DummyFilter")
        assert a is not b

    def test_list_names(self):
        from codeupipe.registry import Registry
        reg = Registry()
        reg.register(DummyFilter)
        reg.register(DummyTap)
        names = reg.list()
        assert set(names) == {"DummyFilter", "DummyTap"}

    def test_has(self):
        from codeupipe.registry import Registry
        reg = Registry()
        reg.register(DummyFilter)
        assert reg.has("DummyFilter")
        assert not reg.has("Nope")

    def test_unregister(self):
        from codeupipe.registry import Registry
        reg = Registry()
        reg.register(DummyFilter)
        reg.unregister("DummyFilter")
        assert not reg.has("DummyFilter")

    def test_unregister_unknown_raises(self):
        from codeupipe.registry import Registry
        reg = Registry()
        with pytest.raises(KeyError):
            reg.unregister("ghost")

    def test_len(self):
        from codeupipe.registry import Registry
        reg = Registry()
        assert len(reg) == 0
        reg.register(DummyFilter)
        assert len(reg) == 1


# ── Decorator ────────────────────────────────────────────────

class TestCupComponent:
    """The @cup_component decorator."""

    def test_decorator_with_explicit_name(self):
        from codeupipe.registry import cup_component, Registry
        reg = Registry()

        @cup_component("sanitize", registry=reg)
        class Sanitize:
            def call(self, payload):
                return payload

        assert reg.has("sanitize")
        assert isinstance(reg.get("sanitize"), Sanitize)

    def test_decorator_auto_name(self):
        from codeupipe.registry import cup_component, Registry
        reg = Registry()

        @cup_component(registry=reg)
        class ValidateEmail:
            def call(self, payload):
                return payload

        assert reg.has("ValidateEmail")

    def test_decorator_preserves_class(self):
        """The decorator should return the original class unchanged."""
        from codeupipe.registry import cup_component, Registry
        reg = Registry()

        @cup_component(registry=reg)
        class MyFilter:
            def call(self, payload):
                return payload

        assert MyFilter.__name__ == "MyFilter"
        inst = MyFilter()
        assert hasattr(inst, "call")

    def test_decorator_with_kind_metadata(self):
        from codeupipe.registry import cup_component, Registry
        reg = Registry()

        @cup_component("logger", kind="tap", registry=reg)
        class Logger:
            def observe(self, payload):
                pass

        info = reg.info("logger")
        assert info["kind"] == "tap"

    def test_decorator_auto_detects_kind(self):
        from codeupipe.registry import cup_component, Registry
        reg = Registry()

        @cup_component(registry=reg)
        class AutoFilter:
            def call(self, payload):
                return payload

        info = reg.info("AutoFilter")
        assert info["kind"] == "filter"

    def test_decorator_auto_detects_tap(self):
        from codeupipe.registry import cup_component, Registry
        reg = Registry()

        @cup_component(registry=reg)
        class AutoTap:
            def observe(self, payload):
                pass

        info = reg.info("AutoTap")
        assert info["kind"] == "tap"


# ── Default Registry ─────────────────────────────────────────

class TestDefaultRegistry:
    """Module-level default_registry for convenience."""

    def test_default_registry_exists(self):
        from codeupipe.registry import default_registry, Registry
        assert isinstance(default_registry, Registry)

    def test_default_registry_is_singleton(self):
        from codeupipe.registry import default_registry as a
        from codeupipe.registry import default_registry as b
        assert a is b
