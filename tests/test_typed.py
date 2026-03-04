"""
Typed Tests for Opt-in Generics
Testing generic type features with codeupipe.
"""

from typing import List, TypedDict, Optional

import pytest

from codeupipe.core import Pipeline, Payload, Filter


class InputData(TypedDict):
    numbers: List[int]
    operation: str


class OutputData(InputData):
    result: float


class SumFilter(Filter[InputData, OutputData]):
    async def call(self, payload: Payload[InputData]) -> Payload[OutputData]:
        numbers = payload.get("numbers") or []
        total = sum(numbers)
        return payload.insert_as("result", float(total))  # type: ignore


class TestTypedBasics:
    @pytest.mark.unit
    def test_typed_payload_creation(self):
        """Test creating a typed payload."""
        data: InputData = {"numbers": [1, 2, 3], "operation": "sum"}
        p: Payload[InputData] = Payload(data)
        assert p.get("numbers") == [1, 2, 3]

    @pytest.mark.unit
    def test_typed_filter_execution(self):
        """Test executing a typed filter."""
        f = SumFilter()
        input_data: InputData = {"numbers": [1, 2, 3, 4], "operation": "sum"}
        p: Payload[InputData] = Payload(input_data)

        import asyncio
        result = asyncio.run(f.call(p))
        assert result.get("result") == 10.0

    @pytest.mark.unit
    def test_typed_pipeline_execution(self):
        """Test executing a typed pipeline."""
        pipeline: Pipeline[InputData, OutputData] = Pipeline()
        pipeline.add_filter(SumFilter(), "sum")

        input_data: InputData = {"numbers": [2, 4, 6, 8], "operation": "stats"}
        p: Payload[InputData] = Payload(input_data)

        import asyncio
        result = asyncio.run(pipeline.run(p))
        assert result.get("result") == 20.0


class TestGenericTypeEvolution:
    """Test generic type evolution features."""

    @pytest.mark.unit
    def test_payload_type_evolution(self):
        """Test that Payload supports type evolution with insert_as."""

        class InitialData(TypedDict):
            name: str

        class EvolvedData(TypedDict):
            name: str
            age: int

        initial: InitialData = {"name": "Alice"}
        p: Payload[InitialData] = Payload(initial)

        evolved = p.insert_as("age", 30)

        assert evolved.get("name") == "Alice"
        assert evolved.get("age") == 30

    @pytest.mark.unit
    def test_generic_payload_operations(self):
        """Test generic Payload operations maintain type safety."""

        class TestData(TypedDict):
            value: int

        data: TestData = {"value": 42}
        p: Payload[TestData] = Payload(data)

        assert p.get("value") == 42
        assert p.get("missing") is None

        new_p = p.insert("new_field", "test")
        assert new_p.get("value") == 42
        assert new_p.get("new_field") == "test"

        other_data: TestData = {"value": 100}
        other_p: Payload[TestData] = Payload(other_data)
        merged = p.merge(other_p)
        assert merged.get("value") == 100

    @pytest.mark.unit
    def test_mutable_payload_generic(self):
        """Test MutablePayload with generic typing."""

        class TestData(TypedDict):
            counter: int

        data: TestData = {"counter": 0}
        mutable = Payload(data).with_mutation()

        mutable.set("counter", 5)  # type: ignore
        assert mutable.get("counter") == 5

        immutable = mutable.to_immutable()  # type: ignore
        assert immutable.get("counter") == 5


class TestTypedWorkflows:
    """Test complete typed workflows."""

    @pytest.mark.unit
    def test_typed_data_processing_pipeline(self):
        """Test a complete typed data processing pipeline."""

        class RawData(TypedDict):
            raw_values: List[str]

        class ParsedData(TypedDict):
            raw_values: List[str]
            parsed_numbers: List[int]

        class ProcessedData(TypedDict):
            raw_values: List[str]
            parsed_numbers: List[int]
            sum: int
            average: float

        class ParseFilter(Filter[RawData, ParsedData]):
            async def call(self, payload: Payload[RawData]) -> Payload[ParsedData]:
                raw_values = payload.get("raw_values") or []
                parsed_numbers = [int(x) for x in raw_values if x.isdigit()]
                return payload.insert_as("parsed_numbers", parsed_numbers)  # type: ignore

        class ProcessFilter(Filter[ParsedData, ProcessedData]):
            async def call(self, payload: Payload[ParsedData]) -> Payload[ProcessedData]:
                numbers = payload.get("parsed_numbers") or []
                total = sum(numbers)
                avg = total / len(numbers) if numbers else 0.0
                return payload.insert_as("sum", total).insert_as("average", avg)  # type: ignore

        pipeline: Pipeline = Pipeline()
        pipeline.add_filter(ParseFilter(), "parse")
        pipeline.add_filter(ProcessFilter(), "process")

        input_data: RawData = {"raw_values": ["1", "2", "3", "4", "5"]}
        p: Payload[RawData] = Payload(input_data)

        import asyncio
        result = asyncio.run(pipeline.run(p))

        assert result.get("parsed_numbers") == [1, 2, 3, 4, 5]
        assert result.get("sum") == 15
        assert result.get("average") == 3.0

    @pytest.mark.unit
    def test_typed_error_handling(self):
        """Test typed error handling in workflows."""

        class InputData(TypedDict):
            value: Optional[int]

        class OutputData(TypedDict):
            value: Optional[int]
            error: Optional[str]

        class ValidateFilter(Filter[InputData, OutputData]):
            async def call(self, payload: Payload[InputData]) -> Payload[OutputData]:
                value = payload.get("value")
                if value is None:
                    return payload.insert_as("error", "Value is required")  # type: ignore
                if not isinstance(value, int):
                    return payload.insert_as("error", "Value must be an integer")  # type: ignore
                if value < 0:
                    return payload.insert_as("error", "Value must be non-negative")  # type: ignore
                return payload.insert_as("error", None)  # type: ignore

        valid_input: InputData = {"value": 42}
        p: Payload[InputData] = Payload(valid_input)

        f = ValidateFilter()
        import asyncio
        result = asyncio.run(f.call(p))
        assert result.get("error") is None

        invalid_input: InputData = {"value": -1}
        p2: Payload[InputData] = Payload(invalid_input)
        result2 = asyncio.run(f.call(p2))
        assert result2.get("error") == "Value must be non-negative"


class TestBackwardCompatibility:
    """Test that generic enhancements don't break untyped code."""

    @pytest.mark.unit
    def test_untyped_payload_still_works(self):
        """Test that untyped Payload usage still works."""
        p = Payload({"key": "value"})
        assert p.get("key") == "value"

        new_p = p.insert("new_key", "new_value")
        assert new_p.get("new_key") == "new_value"

    @pytest.mark.unit
    def test_mixed_typed_untyped_pipelines(self):
        """Test mixing typed and untyped components in pipelines."""

        class SimpleFilter(Filter):
            async def call(self, payload: Payload) -> Payload:
                value = payload.get("input") or 0
                return payload.insert("output", value * 2)

        pipeline = Pipeline()
        pipeline.add_filter(SimpleFilter(), "double")

        p = Payload({"input": 5})
        import asyncio
        result = asyncio.run(pipeline.run(p))
        assert result.get("output") == 10
