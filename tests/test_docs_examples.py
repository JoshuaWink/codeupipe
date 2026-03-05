"""
Tests that verify every code example in CONCEPTS.md is authentic and correct.

Each test mirrors an exact code block from the docs so that a failing test
means the documentation is wrong or the implementation changed.

Run with:  pytest tests/test_docs_examples.py -v
"""

import asyncio
import pytest
from codeupipe import (
    Payload,
    MutablePayload,
    Pipeline,
    Valve,
    Hook,
    RetryFilter,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


# ===========================================================================
# PAYLOAD
# ===========================================================================

class TestPayloadDocs:
    def test_construction_and_get(self):
        p = Payload({"user_id": 42, "role": "admin"})
        assert p.get("user_id") == 42
        assert p.get("missing", "n/a") == "n/a"

    def test_insert_returns_new_payload_original_unchanged(self):
        p = Payload({"user_id": 42})
        p2 = p.insert("verified", True)
        assert p.get("verified") is None      # original untouched
        assert p2.get("verified") is True

    def test_merge_other_wins_on_conflict(self):
        base     = Payload({"x": 1, "y": 2})
        override = Payload({"y": 99, "z": 3})
        merged = base.merge(override)
        assert merged.get("x") == 1
        assert merged.get("y") == 99          # override wins
        assert merged.get("z") == 3

    def test_to_dict(self):
        p = Payload({"x": 1, "y": 99, "z": 3})
        assert p.to_dict() == {"x": 1, "y": 99, "z": 3}

    def test_with_mutation_returns_mutable_payload(self):
        p = Payload({"n": 5})
        m = p.with_mutation()
        assert isinstance(m, MutablePayload)
        assert m.get("n") == 5


# ===========================================================================
# MUTABLE PAYLOAD
# ===========================================================================

class TestMutablePayloadDocs:
    def test_set_edits_in_place(self):
        m = MutablePayload({"count": 0})
        m.set("count", 1)
        m.set("flag", True)
        assert m.get("count") == 1
        assert m.get("flag") is True

    def test_to_immutable_returns_payload(self):
        m = MutablePayload({"count": 1, "flag": True})
        p = m.to_immutable()
        assert isinstance(p, Payload)
        assert p.get("count") == 1

    def test_normalize_pattern(self):
        # Mirrors the with_mutation() pattern shown in docs
        async def normalize(payload):
            m = payload.with_mutation()
            m.set("name", payload.get("name", "").strip().lower())
            m.set("normalized", True)
            return m.to_immutable()

        result = run(normalize(Payload({"name": "  Alice  "})))
        assert result.get("name") == "alice"
        assert result.get("normalized") is True


# ===========================================================================
# FILTER
# ===========================================================================

class TestFilterDocs:
    def test_uppercase_filter(self):
        class UppercaseFilter:
            async def call(self, payload: Payload) -> Payload:
                name = payload.get("name", "")
                return payload.insert("name", name.upper())

        result = run(UppercaseFilter().call(Payload({"name": "alice"})))
        assert result.get("name") == "ALICE"

    def test_validation_filter_raises_on_bad_email(self):
        class RequireEmailFilter:
            async def call(self, payload: Payload) -> Payload:
                email = payload.get("email", "")
                if "@" not in email:
                    raise ValueError(f"Invalid email: {email!r}")
                return payload.insert("email_valid", True)

        with pytest.raises(ValueError, match="Invalid email"):
            run(RequireEmailFilter().call(Payload({"email": "notanemail"})))

    def test_validation_filter_passes_on_valid_email(self):
        class RequireEmailFilter:
            async def call(self, payload: Payload) -> Payload:
                email = payload.get("email", "")
                if "@" not in email:
                    raise ValueError(f"Invalid email: {email!r}")
                return payload.insert("email_valid", True)

        result = run(RequireEmailFilter().call(Payload({"email": "user@example.com"})))
        assert result.get("email_valid") is True

    def test_normalize_filter_uses_mutable(self):
        class NormalizeFilter:
            async def call(self, payload: Payload) -> Payload:
                m = payload.with_mutation()
                m.set("name",  payload.get("name", "").strip().lower())
                m.set("email", payload.get("email", "").strip().lower())
                return m.to_immutable()

        result = run(NormalizeFilter().call(Payload({"name": "  BOB  ", "email": "  BOB@EXAMPLE.COM  "})))
        assert result.get("name") == "bob"
        assert result.get("email") == "bob@example.com"


# ===========================================================================
# PIPELINE
# ===========================================================================

class TestPipelineDocs:
    def test_sequence_of_two_filters(self):
        class DoubleFilter:
            async def call(self, payload: Payload) -> Payload:
                return payload.insert("value", payload.get("value", 0) * 2)

        class AddTenFilter:
            async def call(self, payload: Payload) -> Payload:
                return payload.insert("value", payload.get("value", 0) + 10)

        async def run_pipeline():
            pipeline = Pipeline()
            pipeline.add_filter(DoubleFilter(), name="double")
            pipeline.add_filter(AddTenFilter(), name="add_ten")
            return await pipeline.run(Payload({"value": 5}))

        result = run(run_pipeline())
        assert result.get("value") == 20    # (5 * 2) + 10

    def test_state_tracks_executed_names(self):
        class PassFilter:
            async def call(self, payload: Payload) -> Payload:
                return payload

        async def run_pipeline():
            pipeline = Pipeline()
            pipeline.add_filter(PassFilter(), name="step_one")
            pipeline.add_filter(PassFilter(), name="step_two")
            await pipeline.run(Payload({}))
            return pipeline.state

        state = run(run_pipeline())
        assert "step_one" in state.executed
        assert "step_two" in state.executed


# ===========================================================================
# VALVE
# ===========================================================================

class TestValveDocs:
    def _make_discount_valve(self):
        class DiscountFilter:
            async def call(self, payload: Payload) -> Payload:
                total = payload.get("total", 0)
                return payload.insert("total", total * 0.9)

        def is_premium(payload: Payload) -> bool:
            return payload.get("tier") == "premium"

        return Valve(name="premium_discount", inner=DiscountFilter(), predicate=is_premium)

    def test_valve_applies_filter_when_predicate_true(self):
        async def run_pipeline():
            pipeline = Pipeline()
            pipeline.add_filter(self._make_discount_valve(), name="premium_discount")
            return await pipeline.run(Payload({"tier": "premium", "total": 100}))

        result = run(run_pipeline())
        assert result.get("total") == pytest.approx(90.0)

    def test_valve_passthrough_when_predicate_false(self):
        async def run_pipeline():
            pipeline = Pipeline()
            pipeline.add_filter(self._make_discount_valve(), name="premium_discount")
            return await pipeline.run(Payload({"tier": "standard", "total": 100}))

        result = run(run_pipeline())
        assert result.get("total") == 100        # unchanged

    def test_valve_skipped_recorded_in_state(self):
        async def run_pipeline():
            pipeline = Pipeline()
            pipeline.add_filter(self._make_discount_valve(), name="premium_discount")
            await pipeline.run(Payload({"tier": "standard", "total": 100}))
            return pipeline.state

        state = run(run_pipeline())
        assert "premium_discount" in state.skipped
        assert "premium_discount" not in state.executed

    def test_valve_executed_recorded_in_state(self):
        async def run_pipeline():
            pipeline = Pipeline()
            pipeline.add_filter(self._make_discount_valve(), name="premium_discount")
            await pipeline.run(Payload({"tier": "premium", "total": 100}))
            return pipeline.state

        state = run(run_pipeline())
        assert "premium_discount" in state.executed
        assert "premium_discount" not in state.skipped


# ===========================================================================
# TAP
# ===========================================================================

class TestTapDocs:
    def test_print_tap_does_not_modify_payload(self):
        class PrintTap:
            async def observe(self, payload: Payload) -> None:
                pass  # suppress actual output in tests

        async def run_pipeline():
            pipeline = Pipeline()
            pipeline.add_tap(PrintTap(), name="print")
            return await pipeline.run(Payload({"x": 1}))

        result = run(run_pipeline())
        assert result.get("x") == 1      # payload unchanged

    def test_metrics_tap_captures_snapshots(self):
        class MetricsTap:
            def __init__(self):
                self.snapshots = []

            async def observe(self, payload: Payload) -> None:
                self.snapshots.append(payload.to_dict().copy())

        class AddYFilter:
            async def call(self, payload: Payload) -> Payload:
                return payload.insert("y", 2)

        async def run_pipeline():
            metrics = MetricsTap()
            pipeline = Pipeline()
            pipeline.add_tap(metrics, name="before_add_y")
            pipeline.add_filter(AddYFilter(), name="add_y")
            pipeline.add_tap(metrics, name="after_add_y")
            await pipeline.run(Payload({"x": 1}))
            return metrics

        metrics = run(run_pipeline())
        assert len(metrics.snapshots) == 2
        assert "y" not in metrics.snapshots[0]   # snapshot before AddYFilter
        assert metrics.snapshots[1]["y"] == 2    # snapshot after AddYFilter

    def test_tap_recorded_in_state(self):
        class NopTap:
            async def observe(self, payload: Payload) -> None:
                pass

        async def run_pipeline():
            pipeline = Pipeline()
            pipeline.add_tap(NopTap(), name="my_tap")
            await pipeline.run(Payload({}))
            return pipeline.state

        state = run(run_pipeline())
        assert "my_tap" in state.executed


# ===========================================================================
# STATE
# ===========================================================================

class TestStateDocs:
    def test_executed_skipped_tracking(self):
        class StepA:
            async def call(self, payload: Payload) -> Payload:
                return payload.insert("a", True)

        class StepB:
            async def call(self, payload: Payload) -> Payload:
                return payload.insert("b", True)

        async def run_pipeline():
            always_false = Valve(
                name="gated_b",
                inner=StepB(),
                predicate=lambda p: False,
            )
            pipeline = Pipeline()
            pipeline.add_filter(StepA(), name="step_a")
            pipeline.add_filter(always_false, name="gated_b")
            await pipeline.run(Payload({}))
            return pipeline.state

        state = run(run_pipeline())
        assert state.executed == ["step_a"]
        assert state.skipped  == ["gated_b"]
        assert state.has_errors is False

    def test_state_metadata_set_get(self):
        from codeupipe import State
        s = State()
        s.set("batch_id", "abc123")
        assert s.get("batch_id") == "abc123"
        assert s.get("missing", "default") == "default"

    def test_state_reset_clears_all(self):
        from codeupipe import State
        s = State()
        s.mark_executed("a")
        s.mark_skipped("b")
        s.record_error("c", RuntimeError("boom"))
        s.set("x", 1)
        s.reset()
        assert s.executed == []
        assert s.skipped  == []
        assert s.errors   == []
        assert s.metadata == {}

    def test_last_error_returns_most_recent(self):
        from codeupipe import State
        s = State()
        err1 = ValueError("first")
        err2 = RuntimeError("second")
        s.record_error("a", err1)
        s.record_error("b", err2)
        assert s.last_error is err2

    def test_last_error_none_when_empty(self):
        from codeupipe import State
        s = State()
        assert s.last_error is None


# ===========================================================================
# HOOK
# ===========================================================================

class TestHookDocs:
    def test_logging_hook_records_lifecycle_calls(self):
        class LoggingHook(Hook):
            def __init__(self):
                self.log = []

            async def before(self, filter, payload: Payload) -> None:
                name = filter.__class__.__name__ if filter else "pipeline"
                self.log.append(f"before:{name}")

            async def after(self, filter, payload: Payload) -> None:
                name = filter.__class__.__name__ if filter else "pipeline"
                self.log.append(f"after:{name}")

            async def on_error(self, filter, error: Exception, payload: Payload) -> None:
                name = filter.__class__.__name__ if filter else "pipeline"
                self.log.append(f"error:{name}:{error}")

        class SquareFilter:
            async def call(self, payload: Payload) -> Payload:
                return payload.insert("n", payload.get("n", 0) ** 2)

        async def run_pipeline():
            hook = LoggingHook()
            pipeline = Pipeline()
            pipeline.use_hook(hook)
            pipeline.add_filter(SquareFilter(), name="square")
            await pipeline.run(Payload({"n": 4}))
            return hook.log

        log = run(run_pipeline())
        assert log == [
            "before:pipeline",
            "before:SquareFilter",
            "after:SquareFilter",
            "after:pipeline",
        ]

    def test_hook_on_error_called_when_filter_raises(self):
        class ErrorHook(Hook):
            def __init__(self):
                self.errors = []

            async def on_error(self, filter, error: Exception, payload: Payload) -> None:
                self.errors.append(str(error))

        class BoomFilter:
            async def call(self, payload: Payload) -> Payload:
                raise RuntimeError("kaboom")

        async def run_pipeline():
            hook = ErrorHook()
            pipeline = Pipeline()
            pipeline.use_hook(hook)
            pipeline.add_filter(BoomFilter(), name="boom")
            try:
                await pipeline.run(Payload({}))
            except RuntimeError:
                pass
            return hook.errors

        errors = run(run_pipeline())
        assert "kaboom" in errors[0]

    def test_hook_default_noop_methods_do_not_raise(self):
        # A Hook subclass with no overrides should work without error
        class NoOpHook(Hook):
            pass

        class PassFilter:
            async def call(self, payload: Payload) -> Payload:
                return payload

        async def run_pipeline():
            pipeline = Pipeline()
            pipeline.use_hook(NoOpHook())
            pipeline.add_filter(PassFilter(), name="pass")
            return await pipeline.run(Payload({"x": 1}))

        result = run(run_pipeline())
        assert result.get("x") == 1


# ===========================================================================
# RETRY FILTER
# ===========================================================================

class TestRetryFilterDocs:
    def test_retry_succeeds_on_third_attempt(self):
        attempts = {"count": 0}

        class FlakyFilter:
            async def call(self, payload: Payload) -> Payload:
                attempts["count"] += 1
                if attempts["count"] < 3:
                    raise ConnectionError("not ready")
                return payload.insert("connected", True)

        result = run(RetryFilter(FlakyFilter(), max_retries=3).call(Payload({})))
        assert result.get("connected") is True
        assert attempts["count"] == 3

    def test_retry_exhausted_returns_error_key(self):
        class AlwaysFailsFilter:
            async def call(self, payload: Payload) -> Payload:
                raise RuntimeError("down")

        result = run(RetryFilter(AlwaysFailsFilter(), max_retries=2).call(Payload({})))
        assert result.get("error") is not None
        assert "down" in result.get("error", "")

    def test_retry_zero_max_retries_returns_error_immediately(self):
        class AlwaysFailsFilter:
            async def call(self, payload: Payload) -> Payload:
                raise RuntimeError("gone")

        result = run(RetryFilter(AlwaysFailsFilter(), max_retries=0).call(Payload({})))
        assert "gone" in result.get("error", "")


# ===========================================================================
# COMPLETE WORKFLOW  (mirrors the end-to-end example in CONCEPTS.md)
# ===========================================================================

class TestCompleteWorkflowDocs:
    def _build_pipeline(self):
        class ValidateOrderFilter:
            async def call(self, payload: Payload) -> Payload:
                qty = payload.get("quantity", 0)
                if qty <= 0:
                    raise ValueError("quantity must be positive")
                return payload.insert("valid", True)

        class ApplyDiscountFilter:
            async def call(self, payload: Payload) -> Payload:
                price = payload.get("price", 0.0)
                return payload.insert("price", round(price * 0.85, 2))

        class ChargeFilter:
            async def call(self, payload: Payload) -> Payload:
                price = payload.get("price", 0.0)
                qty   = payload.get("quantity", 0)
                return payload.insert("charged", round(price * qty, 2))

        class AuditTap:
            def __init__(self):
                self.snapshots = []

            async def observe(self, payload: Payload) -> None:
                self.snapshots.append(payload.to_dict())

        class TimingHook(Hook):
            def __init__(self):
                self.calls = []

            async def before(self, filter, payload: Payload) -> None:
                if filter:
                    self.calls.append(f"start:{filter.__class__.__name__}")

            async def after(self, filter, payload: Payload) -> None:
                if filter:
                    self.calls.append(f"end:{filter.__class__.__name__}")

        audit   = AuditTap()
        timing  = TimingHook()
        is_bulk = lambda p: p.get("quantity", 0) >= 10

        pipeline = Pipeline()
        pipeline.use_hook(timing)
        pipeline.add_filter(RetryFilter(ValidateOrderFilter(), max_retries=1), name="validate")
        pipeline.add_tap(audit, name="after_validate")
        pipeline.add_filter(
            Valve("bulk_discount", ApplyDiscountFilter(), predicate=is_bulk),
            name="bulk_discount",
        )
        pipeline.add_filter(ChargeFilter(), name="charge")

        return pipeline, audit, timing

    def test_bulk_order_applies_discount_and_charges(self):
        pipeline, audit, timing = self._build_pipeline()

        async def go():
            return await pipeline.run(Payload({"quantity": 20, "price": 50.0}))

        result = run(go())
        # 50.0 * 0.85 = 42.5, then * 20 = 850.0
        assert result.get("charged") == pytest.approx(850.0)
        assert result.get("valid") is True

    def test_bulk_order_state_records_correct_steps(self):
        pipeline, audit, timing = self._build_pipeline()

        async def go():
            await pipeline.run(Payload({"quantity": 20, "price": 50.0}))
            return pipeline.state

        state = run(go())
        assert "validate" in state.executed
        assert "after_validate" in state.executed
        assert "bulk_discount" in state.executed    # qty=20 >= 10, valve fires
        assert "charge" in state.executed
        assert state.skipped == []

    def test_small_order_skips_discount_valve(self):
        pipeline, audit, timing = self._build_pipeline()

        async def go():
            await pipeline.run(Payload({"quantity": 2, "price": 50.0}))
            return pipeline.state

        state = run(go())
        assert "bulk_discount" in state.skipped
        assert "bulk_discount" not in state.executed

    def test_audit_tap_captures_snapshot_after_validate(self):
        pipeline, audit, timing = self._build_pipeline()

        async def go():
            await pipeline.run(Payload({"quantity": 5, "price": 10.0}))

        run(go())
        assert len(audit.snapshots) >= 1
        assert audit.snapshots[0].get("valid") is True

    def test_invalid_order_sets_error_key(self):
        # ValidateOrderFilter raises ValueError, but it is wrapped in
        # RetryFilter(max_retries=1) which exhausts retries and returns
        # the payload with an "error" key instead of re-raising.
        # The pipeline continues; ChargeFilter computes price*qty = 0.0
        # because quantity=0 despite the validation failure.
        pipeline, audit, timing = self._build_pipeline()

        async def go():
            return await pipeline.run(Payload({"quantity": 0, "price": 10.0}))

        result = run(go())
        assert result.get("error") is not None
        assert "quantity must be positive" in result.get("error", "")
        assert result.get("charged") == 0.0   # price * qty = 10.0 * 0 = 0.0
