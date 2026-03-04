"""
Simple Example: Math Pipeline

Demonstrates modular pipeline processing with math filters, taps, and hooks.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import asyncio
from codeupipe.core import Payload, Pipeline, Valve
from components.filters import MathFilter
from components.hooks import LoggingHook
from components.taps import PrintTap


async def main():
    pipeline = Pipeline()
    pipeline.add_filter(MathFilter("sum"), "sum")
    pipeline.add_filter(
        Valve("mean", MathFilter("mean"), lambda p: p.get("result") is not None),
        "mean"
    )
    pipeline.add_tap(PrintTap("RESULT"), "result_tap")
    pipeline.use_hook(LoggingHook())

    payload = Payload({"numbers": [1, 2, 3, 4, 5]})
    result = await pipeline.run(payload)

    print(f"Final result: {result.get('result')}")
    print(f"Full payload: {result.to_dict()}")
    print(f"Execution state: {pipeline.state}")


if __name__ == "__main__":
    asyncio.run(main())
