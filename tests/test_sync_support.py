"""
Tests confirming that sync (non-async) filters, taps, hooks, and valve
inner-filters all work correctly alongside their async equivalents.
"""

import asyncio
from codeupipe import Payload, Pipeline, Valve, Hook

# ---------------------------------------------------------------------------

def run(coro):
    return asyncio.run(coro)


# ===========================================================================
# Sync Filters
# ===========================================================================

class TestSyncFilter:
    def test_sync_filter_executes(self):
        class SyncDouble:
            def call(self, payload: Payload) -> Payload:      # no async
                return payload.insert("value", payload.get("value", 0) * 2)

        async def go():
            pipeline = Pipeline()
            pipeline.add_filter(SyncDouble(), name="double")
            return await pipeline.run(Payload({"value": 5}))

        assert run(go()).get("value") == 10

    def test_sync_and_async_filters_interleaved(self):
        class SyncAdd:
            def call(self, payload: Payload) -> Payload:
                return payload.insert("n", payload.get("n", 0) + 1)

        class AsyncMul:
            async def call(self, payload: Payload) -> Payload:
                return payload.insert("n", payload.get("n", 0) * 3)

        async def go():
            pipeline = Pipeline()
            pipeline.add_filter(SyncAdd(),  name="add")   # sync
            pipeline.add_filter(AsyncMul(), name="mul")   # async
            pipeline.add_filter(SyncAdd(),  name="add2")  # sync again
            return await pipeline.run(Payload({"n": 0}))

        # (0+1)*3 + 1 = 4
        assert run(go()).get("n") == 4

    def test_sync_filter_recorded_in_state(self):
        class SyncPass:
            def call(self, payload: Payload) -> Payload:
                return payload

        async def go():
            pipeline = Pipeline()
            pipeline.add_filter(SyncPass(), name="sync_pass")
            await pipeline.run(Payload({}))
            return pipeline.state

        state = run(go())
        assert "sync_pass" in state.executed


# ===========================================================================
# Sync Taps
# ===========================================================================

class TestSyncTap:
    def test_sync_tap_observes_without_modifying(self):
        seen = []

        class SyncTap:
            def observe(self, payload: Payload) -> None:    # no async
                seen.append(payload.get("x"))

        async def go():
            pipeline = Pipeline()
            pipeline.add_tap(SyncTap(), name="spy")
            return await pipeline.run(Payload({"x": 42}))

        result = run(go())
        assert result.get("x") == 42
        assert seen == [42]

    def test_sync_tap_recorded_in_state(self):
        class SyncNopTap:
            def observe(self, payload: Payload) -> None:
                pass

        async def go():
            pipeline = Pipeline()
            pipeline.add_tap(SyncNopTap(), name="nop_tap")
            await pipeline.run(Payload({}))
            return pipeline.state

        state = run(go())
        assert "nop_tap" in state.executed


# ===========================================================================
# Sync Hooks
# ===========================================================================

class TestSyncHook:
    def test_sync_hook_methods_called(self):
        log = []

        class SyncHook(Hook):
            def before(self, filter, payload: Payload) -> None:   # no async
                log.append(f"before:{filter.__class__.__name__ if filter else 'pipeline'}")

            def after(self, filter, payload: Payload) -> None:    # no async
                log.append(f"after:{filter.__class__.__name__ if filter else 'pipeline'}")

        class PassFilter:
            async def call(self, payload: Payload) -> Payload:
                return payload

        async def go():
            pipeline = Pipeline()
            pipeline.use_hook(SyncHook())
            pipeline.add_filter(PassFilter(), name="pass")
            await pipeline.run(Payload({}))

        run(go())
        assert log == [
            "before:pipeline",
            "before:PassFilter",
            "after:PassFilter",
            "after:pipeline",
        ]

    def test_sync_on_error_hook_called_on_failure(self):
        errors = []

        class SyncErrHook(Hook):
            def on_error(self, filter, error: Exception, payload: Payload) -> None:
                errors.append(str(error))

        class BoomFilter:
            async def call(self, payload: Payload) -> Payload:
                raise RuntimeError("boom")

        async def go():
            pipeline = Pipeline()
            pipeline.use_hook(SyncErrHook())
            pipeline.add_filter(BoomFilter(), name="boom")
            try:
                await pipeline.run(Payload({}))
            except RuntimeError:
                pass

        run(go())
        assert errors == ["boom"]


# ===========================================================================
# Sync Valve inner filter
# ===========================================================================

class TestSyncValveInner:
    def test_sync_inner_filter_executes_when_predicate_true(self):
        class SyncDiscount:
            def call(self, payload: Payload) -> Payload:   # no async
                return payload.insert("total", payload.get("total", 0) * 0.9)

        valve = Valve(
            name="disc",
            inner=SyncDiscount(),
            predicate=lambda p: p.get("vip") is True,
        )

        async def go():
            pipeline = Pipeline()
            pipeline.add_filter(valve, name="disc")
            return await pipeline.run(Payload({"vip": True, "total": 200}))

        result = run(go())
        assert result.get("total") == 180.0

    def test_sync_inner_filter_skipped_when_predicate_false(self):
        class SyncDiscount:
            def call(self, payload: Payload) -> Payload:
                return payload.insert("total", payload.get("total", 0) * 0.9)

        valve = Valve(
            name="disc",
            inner=SyncDiscount(),
            predicate=lambda p: p.get("vip") is True,
        )

        async def go():
            pipeline = Pipeline()
            pipeline.add_filter(valve, name="disc")
            await pipeline.run(Payload({"vip": False, "total": 200}))
            return pipeline.state

        state = run(go())
        assert "disc" in state.skipped
