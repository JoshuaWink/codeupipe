"""
Converter: CUP ↔ Standard Python bidirectional conversion.

Built with CUP — the converter itself is a set of Filters and Pipelines.
"""

from .config import load_config, DEFAULT_CONFIG, PATTERN_DEFAULTS

__all__ = ["load_config", "DEFAULT_CONFIG", "PATTERN_DEFAULTS"]
