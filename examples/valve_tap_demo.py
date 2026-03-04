"""
Valve & Tap Demo: Conditional Flow and Observation

Demonstrates Valves for conditional execution and Taps for observation.
"""

import asyncio
from codeupipe.core import Payload, Pipeline, Valve, Filter
from codeupipe.core.tap import Tap


class AgeCheckFilter:
    """Filter that marks age verification."""

    async def call(self, payload: Payload) -> Payload:
        return payload.insert("age_verified", True)


class DiscountFilter:
    """Filter that applies a discount."""

    async def call(self, payload: Payload) -> Payload:
        total = payload.get("total", 0)
        discount = total * 0.10
        return payload.insert("discount", discount).insert("final_total", total - discount)


class AuditTap:
    """Tap that records payload at observation points."""

    def __init__(self):
        self.log = []

    async def observe(self, payload: Payload) -> None:
        self.log.append(payload.to_dict().copy())


async def main():
    audit = AuditTap()

    pipeline = Pipeline()

    # Always run: set up data
    class SetupFilter:
        async def call(self, payload: Payload) -> Payload:
            return payload.insert("total", 100.0)

    pipeline.add_filter(SetupFilter(), "setup")
    pipeline.add_tap(audit, "after_setup_audit")

    # Valve: only apply discount if customer is premium
    pipeline.add_filter(
        Valve("discount", DiscountFilter(), lambda p: p.get("tier") == "premium"),
        "discount"
    )
    pipeline.add_tap(audit, "after_discount_audit")

    # Run for premium customer
    print("=== Premium Customer ===")
    result = await pipeline.run(Payload({"tier": "premium"}))
    print(f"Discount: {result.get('discount')}")
    print(f"Final total: {result.get('final_total')}")
    print(f"Pipeline state: {pipeline.state}")

    # Run for regular customer
    print("\n=== Regular Customer ===")
    result = await pipeline.run(Payload({"tier": "regular"}))
    print(f"Discount: {result.get('discount')}")
    print(f"Final total: {result.get('final_total')}")
    print(f"Pipeline state: {pipeline.state}")

    print(f"\nAudit log entries: {len(audit.log)}")


if __name__ == "__main__":
    asyncio.run(main())
