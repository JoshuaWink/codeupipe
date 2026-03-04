"""
Pipeline Components: Reusable Pipeline Implementations
"""

from codeupipe.core.payload import Payload
from codeupipe.core.pipeline import Pipeline

__all__ = ["BasicPipeline"]


class BasicPipeline(Pipeline):
    """A basic pipeline with sensible defaults."""
    pass
