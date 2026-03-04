"""
Tests for Pipeline

Testing the Pipeline orchestrator with filters, valves, taps, and hooks.
"""

import pytest
import asyncio
from typing import Optional
from codeupipe.core.payload import Payload
from codeupipe.core.filter import Filter
from codeupipe.core.pipeline import Pipeline
from codeupipe.core.valve import Valve
from codeupipe.core.hook import Hook


class LoggingHook(Hook):
    """Simple hook for testing that logs execution."""

    def __init__(self):
        super().__init__()
        self.log = []

    async def before(self, filter: Optional[Filter], payload: Payload) -> None:
        filter_name = "pipeline_start" if filter is None else "unknown"
        if filter is not None and hasattr(filter, 'name'):
            filter_name = getattr(filter, 'name')
        self.log.append(f"before_{filter_name}")

    async def after(self, filter: Optional[Filter], payload: Payload) -> None:
        filter_name = "pipeline_end" if filter is None else "unknown"
        if filter is not None and hasattr(filter, 'name'):
            filter_name = getattr(filter, 'name')
        self.log.append(f"after_{filter_name}")

    async def on_error(self, filter: Optional[Filter], error: Exception, payload: Payload) -> None:
        filter_name = "pipeline" if filter is None else "unknown"
        if filter is not None and hasattr(filter, 'name'):
            filter_name = getattr(filter, 'name')
        self.log.append(f"error_{filter_name}_{str(error)}")


class TestSimplePipeline:
    """Test the Pipeline."""

    @pytest.mark.unit
    @pytest.mark.core
    def test_empty_pipeline(self):
        """Test running an empty pipeline."""
        pipeline = Pipeline()

        async def run_test():
            payload = Payload({"input": "test"})
            result = await pipeline.run(payload)
            assert result.get("input") == "test"

        asyncio.run(run_test())

    @pytest.mark.unit
    @pytest.mark.core
    def test_single_filter_pipeline(self):
        """Test pipeline with a single filter."""
        pipeline = Pipeline()

        class TestFilter:
            async def call(self, payload):
                return payload.insert("processed", True)

        pipeline.add_filter(TestFilter(), "test")

        async def run_test():
            payload = Payload({"input": "test"})
            result = await pipeline.run(payload)

            assert result.get("processed") is True
            assert result.get("input") == "test"

        asyncio.run(run_test())

    @pytest.mark.unit
    @pytest.mark.core
    def test_multiple_filters_pipeline(self):
        """Test pipeline with multiple filters."""
        pipeline = Pipeline()

        class Filter1:
            async def call(self, payload):
                return payload.insert("step1", True)

        class Filter2:
            async def call(self, payload):
                return payload.insert("step2", True)

        pipeline.add_filter(Filter1(), "filter1")
        pipeline.add_filter(Filter2(), "filter2")

        async def run_test():
            result = await pipeline.run(Payload())
            assert result.get("step1") is True
            assert result.get("step2") is True

        asyncio.run(run_test())

    @pytest.mark.unit
    @pytest.mark.core
    def test_pipeline_state_tracking(self):
        """Test that pipeline tracks execution state."""
        pipeline = Pipeline()

        class TestFilter:
            async def call(self, payload):
                return payload.insert("done", True)

        pipeline.add_filter(TestFilter(), "step_a")
        pipeline.add_filter(TestFilter(), "step_b")

        async def run_test():
            await pipeline.run(Payload())
            assert "step_a" in pipeline.state.executed
            assert "step_b" in pipeline.state.executed

        asyncio.run(run_test())


class TestValveInPipeline:
    """Test Valves providing conditional execution in pipelines."""

    @pytest.mark.unit
    @pytest.mark.core
    def test_valve_allows_when_predicate_true(self):
        """Test that a Valve executes its filter when predicate is True."""
        pipeline = Pipeline()

        class SetValueFilter:
            async def call(self, payload):
                return payload.insert("value", 42)

        class GatedFilter:
            async def call(self, payload):
                return payload.insert("gated_ran", True)

        pipeline.add_filter(SetValueFilter(), "set_value")
        pipeline.add_filter(
            Valve("gated", GatedFilter(), lambda p: p.get("value") == 42),
            "gated"
        )

        async def run_test():
            result = await pipeline.run(Payload())
            assert result.get("gated_ran") is True

        asyncio.run(run_test())

    @pytest.mark.unit
    @pytest.mark.core
    def test_valve_blocks_when_predicate_false(self):
        """Test that a Valve skips its filter when predicate is False."""
        pipeline = Pipeline()
        executed = []

        class FirstFilter:
            async def call(self, payload):
                executed.append("first")
                return payload.insert("first_ran", True)

        class GatedFilter:
            async def call(self, payload):
                executed.append("gated")
                return payload.insert("gated_ran", True)

        pipeline.add_filter(FirstFilter(), "first")
        pipeline.add_filter(
            Valve("gated", GatedFilter(), lambda p: False),
            "gated"
        )

        async def run_test():
            result = await pipeline.run(Payload())
            assert "first" in executed
            assert "gated" not in executed
            assert result.get("first_ran") is True
            assert result.get("gated_ran") is None

        asyncio.run(run_test())

    @pytest.mark.unit
    @pytest.mark.core
    def test_valve_conditional_branching(self):
        """Test conditional execution — success path runs, failure path skipped."""
        pipeline = Pipeline()

        class SuccessFilter:
            async def call(self, payload):
                return payload.insert("success", True)

        class FailureFilter:
            async def call(self, payload):
                return payload.insert("failure", True)

        pipeline.add_filter(SuccessFilter(), "validate")
        pipeline.add_filter(
            Valve("success_path", SuccessFilter(), lambda p: p.get("success") is True),
            "success_path"
        )
        pipeline.add_filter(
            Valve("failure_path", FailureFilter(), lambda p: p.get("success") is not True),
            "failure_path"
        )

        async def run_test():
            result = await pipeline.run(Payload())
            assert result.get("success") is True
            assert result.get("failure") is None

        asyncio.run(run_test())


class TestTapInPipeline:
    """Test Taps providing observation in pipelines."""

    @pytest.mark.unit
    @pytest.mark.core
    def test_tap_observes_without_modifying(self):
        """Test that a Tap observes payload without modifying it."""
        pipeline = Pipeline()
        observed_values = []

        class ObserverTap:
            async def observe(self, payload):
                observed_values.append(payload.get("value"))

        class SetFilter:
            async def call(self, payload):
                return payload.insert("value", 42)

        pipeline.add_filter(SetFilter(), "set_value")
        pipeline.add_tap(ObserverTap(), "observer")

        async def run_test():
            result = await pipeline.run(Payload())
            assert result.get("value") == 42
            assert observed_values == [42]

        asyncio.run(run_test())

    @pytest.mark.unit
    @pytest.mark.core
    def test_tap_tracked_in_state(self):
        """Test that taps are tracked in pipeline state."""
        pipeline = Pipeline()

        class NoopTap:
            async def observe(self, payload):
                pass

        pipeline.add_tap(NoopTap(), "audit")

        async def run_test():
            await pipeline.run(Payload())
            assert "audit" in pipeline.state.executed

        asyncio.run(run_test())


class TestPipelineWithHook:
    """Test pipelines with hooks."""

    @pytest.mark.unit
    @pytest.mark.core
    def test_hook_execution(self):
        """Test that hooks are called."""
        pipeline = Pipeline()
        hook = LoggingHook()

        class TestFilter:
            def __init__(self, name):
                self.name = name
            async def call(self, payload):
                return payload

        pipeline.use_hook(hook)
        pipeline.add_filter(TestFilter("test_filter"), "test")

        async def run_test():
            await pipeline.run(Payload())

            assert "before_pipeline_start" in hook.log
            assert "before_test_filter" in hook.log
            assert "after_test_filter" in hook.log
            assert "after_pipeline_end" in hook.log

        asyncio.run(run_test())

    @pytest.mark.unit
    @pytest.mark.core
    def test_hook_error_handling(self):
        """Test hook error handling."""
        pipeline = Pipeline()
        hook = LoggingHook()

        class FailingFilter:
            async def call(self, payload):
                raise ValueError("Test error")

        pipeline.use_hook(hook)
        pipeline.add_filter(FailingFilter(), "failing")

        async def run_test():
            with pytest.raises(ValueError):
                await pipeline.run(Payload())

            assert any("error" in entry for entry in hook.log)

        asyncio.run(run_test())


class TestPipelineIntegration:
    """Integration tests for pipeline functionality."""

    @pytest.mark.integration
    @pytest.mark.core
    def test_complete_workflow(self):
        """Test a complete workflow with validation, processing, and hooks."""
        pipeline = Pipeline()
        hook = LoggingHook()

        class ValidationFilter:
            async def call(self, payload):
                data = payload.get("data")
                if not data:
                    raise ValueError("No data provided")
                return payload.insert("validated", True)

        class ProcessingFilter:
            async def call(self, payload):
                data = payload.get("data")
                processed = f"processed_{data}"
                return payload.insert("result", processed)

        pipeline.use_hook(hook)
        pipeline.add_filter(ValidationFilter(), "validate")
        pipeline.add_filter(ProcessingFilter(), "process")

        async def run_test():
            payload = Payload({"data": "test_input"})
            result = await pipeline.run(payload)

            assert result.get("validated") is True
            assert result.get("result") == "processed_test_input"
            assert result.get("data") == "test_input"

        asyncio.run(run_test())
