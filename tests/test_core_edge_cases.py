"""
QA edge-case tests for codeupipe core framework.

Covers gaps identified during independent review:
- RetryFilter sync inner filter support (was a bug)
- Payload constructor fallback paths
- Valve predicate exceptions
- Hook exceptions in lifecycle methods
- Multiple hooks execution order
- Duplicate step names
- Pipeline reuse (run twice)
- Filter returning None
- RetryFilter boundary values (negative, 1)
- Nested Valve
- MutablePayload empty dict
- Streaming: chained StreamFilters, Tap errors, reuse
"""

import asyncio
from typing import AsyncIterator

import pytest

from codeupipe import (
    Hook,
    MutablePayload,
    Payload,
    Pipeline,
    RetryFilter,
    State,
    Valve,
)


def run(coro):
    return asyncio.run(coro)


async def collect(aiter):
    results = []
    async for item in aiter:
        results.append(item)
    return results


async def make_source(*dicts):
    for d in dicts:
        yield Payload(d)


# ===========================================================================
# Payload constructor fallback paths
# ===========================================================================


class TestPayloadConstructorEdgeCases:
    """Test the non-dict constructor paths in Payload.__init__."""

    def test_list_of_tuples_becomes_dict(self):
        """dict() can convert list-of-tuples; Payload should handle it."""
        p = Payload([("key", "value"), ("num", 42)])
        assert p.get("key") == "value"
        assert p.get("num") == 42

    def test_non_convertible_falls_back_to_empty(self):
        """Passing something dict() can't convert -> empty payload."""
        p = Payload("not_a_dict")
        assert p.to_dict() == {}

    def test_integer_falls_back_to_empty(self):
        p = Payload(123)
        assert p.to_dict() == {}

    def test_explicit_empty_dict(self):
        """Payload({}) should produce an empty dict, not None logic."""
        p = Payload({})
        assert p.to_dict() == {}

    def test_none_produces_empty(self):
        p = Payload(None)
        assert p.to_dict() == {}

    def test_merge_with_self(self):
        """Merging a payload with itself should be safe."""
        p = Payload({"x": 1})
        merged = p.merge(p)
        assert merged.get("x") == 1
        assert merged is not p


# ===========================================================================
# MutablePayload edge cases
# ===========================================================================


class TestMutablePayloadEdgeCases:
    def test_empty_dict_works(self):
        """MutablePayload({}) -- empty dict is falsy but should still work."""
        m = MutablePayload({})
        m.set("key", "val")
        assert m.get("key") == "val"

    def test_none_produces_empty(self):
        m = MutablePayload(None)
        assert m.get("anything") is None
        m.set("x", 1)
        assert m.get("x") == 1


# ===========================================================================
# RetryFilter: sync support (BUG FIX VERIFICATION)
# ===========================================================================


class TestRetryFilterSyncSupport:
    """RetryFilter must work with sync inner filters (same as Valve/Pipeline)."""

    def test_sync_inner_filter_success(self):
        class SyncFilter:
            def call(self, payload: Payload) -> Payload:
                return payload.insert("ran", True)

        retry = RetryFilter(SyncFilter(), max_retries=3)
        result = run(retry.call(Payload({})))
        assert result.get("ran") is True

    def test_sync_inner_filter_retry_then_succeed(self):
        count = {"n": 0}

        class SyncFlaky:
            def call(self, payload: Payload) -> Payload:
                count["n"] += 1
                if count["n"] < 3:
                    raise ValueError("not yet")
                return payload.insert("attempt", count["n"])

        retry = RetryFilter(SyncFlaky(), max_retries=5)
        result = run(retry.call(Payload({})))
        assert result.get("attempt") == 3

    def test_sync_inner_filter_exhausted(self):
        class SyncFail:
            def call(self, payload: Payload) -> Payload:
                raise RuntimeError("always fails")

        retry = RetryFilter(SyncFail(), max_retries=2)
        result = run(retry.call(Payload({})))
        assert "always fails" in result.get("error", "")

    def test_sync_inner_filter_zero_retries(self):
        class SyncFail:
            def call(self, payload: Payload) -> Payload:
                raise RuntimeError("boom")

        retry = RetryFilter(SyncFail(), max_retries=0)
        result = run(retry.call(Payload({})))
        assert "boom" in result.get("error", "")


# ===========================================================================
# RetryFilter: boundary values
# ===========================================================================


class TestRetryFilterBoundary:
    def test_negative_max_retries_treated_as_zero(self):
        """Negative max_retries should not silently do nothing."""

        class FailFilter:
            async def call(self, payload: Payload) -> Payload:
                raise RuntimeError("fail")

        retry = RetryFilter(FailFilter(), max_retries=-5)
        result = run(retry.call(Payload({})))
        assert result.get("error") is not None

    def test_max_retries_one_succeeds(self):
        class OkFilter:
            async def call(self, payload: Payload) -> Payload:
                return payload.insert("ok", True)

        result = run(RetryFilter(OkFilter(), max_retries=1).call(Payload({})))
        assert result.get("ok") is True

    def test_max_retries_one_fails(self):
        class FailFilter:
            async def call(self, payload: Payload) -> Payload:
                raise RuntimeError("one shot")

        result = run(RetryFilter(FailFilter(), max_retries=1).call(Payload({})))
        assert "one shot" in result.get("error", "")


# ===========================================================================
# Valve: predicate exceptions
# ===========================================================================


class TestValvePredicateException:
    def test_predicate_raise_propagates(self):
        """If the predicate itself raises, the exception should propagate."""

        class InnerFilter:
            async def call(self, payload: Payload) -> Payload:
                return payload.insert("ran", True)

        def bad_predicate(p):
            raise TypeError("predicate exploded")

        valve = Valve("bad_valve", InnerFilter(), bad_predicate)

        with pytest.raises(TypeError, match="predicate exploded"):
            run(valve.call(Payload({})))

    def test_predicate_raise_in_pipeline_triggers_on_error(self):
        """Predicate exception in a pipeline should trigger hook.on_error."""
        errors = []

        class ErrHook(Hook):
            async def on_error(self, f, error, payload):
                errors.append(str(error))

        class Inner:
            async def call(self, payload):
                return payload

        valve = Valve("explode", Inner(), lambda p: 1 / 0)
        pipeline = Pipeline()
        pipeline.use_hook(ErrHook())
        pipeline.add_filter(valve, "explode")

        with pytest.raises(ZeroDivisionError):
            run(pipeline.run(Payload({})))

        assert len(errors) == 1


# ===========================================================================
# Nested Valve
# ===========================================================================


class TestNestedValve:
    def test_valve_wrapping_valve(self):
        """Valve(outer_pred, Valve(inner_pred, filter)) -- both must pass."""

        class AddTag:
            async def call(self, payload):
                return payload.insert("tagged", True)

        inner_valve = Valve("inner", AddTag(), lambda p: p.get("role") == "admin")
        outer_valve = Valve("outer", inner_valve, lambda p: p.get("active") is True)

        # Both pass
        result = run(outer_valve.call(Payload({"active": True, "role": "admin"})))
        assert result.get("tagged") is True

        # Outer blocks
        result = run(outer_valve.call(Payload({"active": False, "role": "admin"})))
        assert result.get("tagged") is None

        # Inner blocks
        result = run(outer_valve.call(Payload({"active": True, "role": "user"})))
        assert result.get("tagged") is None


# ===========================================================================
# Hook exceptions
# ===========================================================================


class TestHookExceptions:
    def test_hook_before_raises_on_pipeline_start(self):
        """Hook.before(filter=None) raises OUTSIDE try/except -- propagates raw."""

        class BombHook(Hook):
            async def before(self, f, payload):
                if f is None:
                    raise RuntimeError("hook before exploded")

        pipeline = Pipeline()
        pipeline.use_hook(BombHook())

        class PassFilter:
            async def call(self, payload):
                return payload

        pipeline.add_filter(PassFilter(), "pass")

        with pytest.raises(RuntimeError, match="hook before exploded"):
            run(pipeline.run(Payload({})))

    def test_hook_after_raises_on_pipeline_end(self):
        """Hook.after(filter=None) raises OUTSIDE try/except -- propagates raw."""

        class BombHook(Hook):
            async def after(self, f, payload):
                if f is None:
                    raise RuntimeError("hook after exploded")

        pipeline = Pipeline()
        pipeline.use_hook(BombHook())

        class PassFilter:
            async def call(self, payload):
                return payload

        pipeline.add_filter(PassFilter(), "pass")

        with pytest.raises(RuntimeError, match="hook after exploded"):
            run(pipeline.run(Payload({})))

    def test_hook_before_filter_raises_triggers_on_error(self):
        """Hook.before inside filter loop IS inside try/except -- on_error fires."""
        errors = []

        class ExplodingHook(Hook):
            async def before(self, f, payload):
                if f is not None:
                    raise RuntimeError("hook mid-pipeline")

            async def on_error(self, f, error, payload):
                errors.append(str(error))

        pipeline = Pipeline()
        pipeline.use_hook(ExplodingHook())

        class PassFilter:
            async def call(self, payload):
                return payload

        pipeline.add_filter(PassFilter(), "pass")

        with pytest.raises(RuntimeError, match="hook mid-pipeline"):
            run(pipeline.run(Payload({})))

        assert "hook mid-pipeline" in errors

    def test_hook_on_error_raises_masks_original(self):
        """If on_error itself raises, the original error is lost."""

        class DoubleExplosion(Hook):
            async def on_error(self, f, error, payload):
                raise RuntimeError("on_error exploded")

        class BoomFilter:
            async def call(self, payload):
                raise ValueError("original error")

        pipeline = Pipeline()
        pipeline.use_hook(DoubleExplosion())
        pipeline.add_filter(BoomFilter(), "boom")

        # The on_error exception masks the original ValueError
        with pytest.raises(RuntimeError, match="on_error exploded"):
            run(pipeline.run(Payload({})))


# ===========================================================================
# Multiple hooks -- execution order
# ===========================================================================


class TestMultipleHooks:
    def test_hooks_fire_in_registration_order(self):
        log = []

        class OrderHook(Hook):
            def __init__(self, name):
                self._name = name

            async def before(self, f, payload):
                label = "pipeline" if f is None else "filter"
                log.append(f"before:{self._name}:{label}")

            async def after(self, f, payload):
                label = "pipeline" if f is None else "filter"
                log.append(f"after:{self._name}:{label}")

        class PassFilter:
            async def call(self, payload):
                return payload

        pipeline = Pipeline()
        pipeline.use_hook(OrderHook("A"))
        pipeline.use_hook(OrderHook("B"))
        pipeline.add_filter(PassFilter(), "pass")

        run(pipeline.run(Payload({})))

        # Both hooks fire, A before B, for each lifecycle event
        assert log == [
            "before:A:pipeline",
            "before:B:pipeline",
            "before:A:filter",
            "before:B:filter",
            "after:A:filter",
            "after:B:filter",
            "after:A:pipeline",
            "after:B:pipeline",
        ]


# ===========================================================================
# Duplicate step names
# ===========================================================================


class TestDuplicateStepNames:
    def test_duplicate_names_both_execute(self):
        """Two filters with the same name -- both should execute and appear in state."""

        class AddOne:
            async def call(self, payload):
                return payload.insert("n", payload.get("n", 0) + 1)

        pipeline = Pipeline()
        pipeline.add_filter(AddOne(), "step")
        pipeline.add_filter(AddOne(), "step")

        result = run(pipeline.run(Payload({"n": 0})))
        # Both filters run -- n incremented twice
        assert result.get("n") == 2
        # State records both executions
        assert pipeline.state.executed.count("step") == 2


# ===========================================================================
# Pipeline reuse -- run twice
# ===========================================================================


class TestPipelineReuse:
    def test_state_reset_between_runs(self):
        """Running a pipeline twice should give fresh state each time."""

        class AddOne:
            async def call(self, payload):
                return payload.insert("n", payload.get("n", 0) + 1)

        pipeline = Pipeline()
        pipeline.add_filter(AddOne(), "add")

        run(pipeline.run(Payload({"n": 10})))
        assert "add" in pipeline.state.executed

        run(pipeline.run(Payload({"n": 20})))
        # State should be from second run only, not accumulated
        assert pipeline.state.executed == ["add"]
        assert pipeline.state.executed.count("add") == 1

    def test_results_independent_between_runs(self):
        class Double:
            async def call(self, payload):
                return payload.insert("n", payload.get("n", 0) * 2)

        pipeline = Pipeline()
        pipeline.add_filter(Double(), "double")

        r1 = run(pipeline.run(Payload({"n": 5})))
        r2 = run(pipeline.run(Payload({"n": 100})))

        assert r1.get("n") == 10
        assert r2.get("n") == 200


# ===========================================================================
# Filter returning None
# ===========================================================================


class TestFilterReturnsNone:
    def test_none_payload_causes_attribute_error_on_next_filter(self):
        """If a filter returns None, the next filter crashes on NoneType."""

        class ReturnNone:
            async def call(self, payload):
                return None  # Bad behavior

        class NeedPayload:
            async def call(self, payload):
                return payload.insert("step2", True)

        pipeline = Pipeline()
        pipeline.add_filter(ReturnNone(), "bad")
        pipeline.add_filter(NeedPayload(), "needs_payload")

        with pytest.raises(AttributeError):
            run(pipeline.run(Payload({"x": 1})))


# ===========================================================================
# Streaming edge cases
# ===========================================================================


class TestStreamingChainedStreamFilters:
    def test_fanout_into_fanout(self):
        """StreamFilter1 yields N, StreamFilter2 yields M each -> N*M total."""

        class Duplicate:
            async def stream(self, chunk: Payload) -> AsyncIterator[Payload]:
                yield chunk.insert("copy", 1)
                yield chunk.insert("copy", 2)

        class AddTag:
            async def stream(self, chunk: Payload) -> AsyncIterator[Payload]:
                yield chunk.insert("tagged", True)

        async def go():
            pipeline = Pipeline()
            pipeline.add_filter(Duplicate(), name="dup")
            pipeline.add_filter(AddTag(), name="tag")
            return await collect(pipeline.stream(make_source({"id": "a"})))

        results = run(go())
        # 1 input -> 2 from dup -> 2 from tag (1:1) = 2 total
        assert len(results) == 2
        assert all(r.get("tagged") is True for r in results)

    def test_fanout_then_fanout(self):
        """Both StreamFilters fan out: 1 -> 2 -> 4."""

        class Dup:
            async def stream(self, chunk: Payload) -> AsyncIterator[Payload]:
                yield chunk
                yield chunk

        async def go():
            pipeline = Pipeline()
            pipeline.add_filter(Dup(), name="dup1")
            pipeline.add_filter(Dup(), name="dup2")
            return await collect(pipeline.stream(make_source({"x": 1})))

        results = run(go())
        assert len(results) == 4


class TestStreamingTapError:
    def test_tap_raises_mid_stream_propagates(self):
        class BoomTap:
            def __init__(self):
                self.count = 0

            async def observe(self, payload):
                self.count += 1
                if self.count == 2:
                    raise RuntimeError("tap exploded")

        async def go():
            pipeline = Pipeline()
            pipeline.add_tap(BoomTap(), name="boom_tap")
            return await collect(pipeline.stream(
                make_source({"n": 1}, {"n": 2}, {"n": 3})
            ))

        with pytest.raises(RuntimeError, match="tap exploded"):
            run(go())


class TestStreamingPipelineReuse:
    def test_stream_state_reset_between_runs(self):
        class PassFilter:
            def call(self, payload):
                return payload

        async def go():
            pipeline = Pipeline()
            pipeline.add_filter(PassFilter(), name="pass")

            _ = await collect(pipeline.stream(make_source({"a": 1}, {"a": 2})))
            chunks_first = pipeline.state.chunks_processed.get("pass", 0)

            _ = await collect(pipeline.stream(make_source({"b": 1})))
            chunks_second = pipeline.state.chunks_processed.get("pass", 0)

            return chunks_first, chunks_second

        first, second = run(go())
        assert first == 2
        assert second == 1  # Not accumulated
