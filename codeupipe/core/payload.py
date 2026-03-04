"""
Payload: The Data Container

The Payload carries data through the pipeline — immutable by default for safety,
mutable when flexibility is needed.
Enhanced with generic typing for type-safe workflows.
"""

from typing import Any, Dict, Optional, TypeVar, Generic, Union

__all__ = ["Payload", "MutablePayload"]

T = TypeVar('T')
TInput = TypeVar('TInput')
TOutput = TypeVar('TOutput')


class Payload(Generic[T]):
    """
    Immutable data container — holds data flowing through the pipeline.
    Returns fresh copies on modification for safety.
    Enhanced with generic typing for type-safe workflows.
    """

    def __init__(self, data: Optional[Union[Dict[str, Any], T]] = None):
        if data is None:
            self._data: Dict[str, Any] = {}
        elif isinstance(data, dict):
            self._data = data.copy() if data else {}
        else:
            try:
                self._data = dict(data)  # type: ignore
            except (TypeError, ValueError):
                self._data = {}

    def get(self, key: str, default: Any = None) -> Any:
        """Return the value for key, or default if absent."""
        return self._data.get(key, default)

    def insert(self, key: str, value: Any) -> 'Payload[T]':
        """Return a fresh Payload with the addition."""
        new_data = self._data.copy()
        new_data[key] = value
        return Payload[T](new_data)

    def insert_as(self, key: str, value: Any) -> 'Payload[T]':
        """
        Create a new Payload with type evolution — allows clean transformation
        between TypedDict shapes without explicit casting.
        """
        new_data = self._data.copy()
        new_data[key] = value
        return Payload[T](new_data)

    def with_mutation(self) -> 'MutablePayload[T]':
        """Convert to a mutable sibling for performance-critical sections."""
        return MutablePayload[T](self._data.copy())

    def merge(self, other: 'Payload[T]') -> 'Payload[T]':
        """Combine payloads, with other taking precedence on conflicts."""
        new_data = self._data.copy()
        new_data.update(other._data)
        return Payload[T](new_data)

    def to_dict(self) -> Dict[str, Any]:
        """Express as dict for ecosystem integration."""
        return self._data.copy()

    def __repr__(self) -> str:
        return f"Payload({self._data})"


class MutablePayload(Generic[T]):
    """
    Mutable data container for performance-critical sections.
    Enhanced with generic typing for type-safe workflows.
    """

    def __init__(self, data: Optional[Dict[str, Any]] = None):
        self._data = data or {}

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Change in place."""
        self._data[key] = value

    def to_immutable(self) -> Payload[T]:
        """Return to safety with a fresh immutable copy."""
        return Payload[T](self._data.copy())

    def __repr__(self) -> str:
        return f"MutablePayload({self._data})"
