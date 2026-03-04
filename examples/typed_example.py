"""
Typed Example: Opt-in payload typing with TypedDict

Demonstrates how to opt in to payload typing using Payload[MyShape],
Filter[InShape, OutShape], and Pipeline[InShape, OutShape].
"""

from typing import TypedDict, List
import asyncio
from codeupipe.core import Payload, Pipeline, Filter


class InputShape(TypedDict):
    numbers: List[int]


class OutputShape(TypedDict):
    result: float


class SumFilter(Filter[InputShape, OutputShape]):
    async def call(self, payload: Payload[InputShape]) -> Payload[OutputShape]:
        numbers = payload.get("numbers") or []
        total = sum(numbers)
        return payload.insert("result", total / len(numbers) if numbers else 0.0)


async def main() -> None:
    pipeline: Pipeline[InputShape, OutputShape] = Pipeline()
    pipeline.add_filter(SumFilter(), "sum")

    payload = Payload[InputShape]({"numbers": [1, 2, 3]})
    result = await pipeline.run(payload)

    print(result.get("result"))


if __name__ == "__main__":
    asyncio.run(main())
