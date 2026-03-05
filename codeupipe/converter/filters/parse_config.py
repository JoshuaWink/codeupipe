"""
ParseConfigFilter: Reads conversion config from file or applies defaults.
"""

from pathlib import Path
from codeupipe import Payload
from codeupipe.converter.config import load_config


class ParseConfigFilter:
    """
    Filter: Parse a .cup.json config or apply pattern defaults.

    Input payload keys:
        - config_path (str, optional): Path to .cup.json
        - pattern (str, optional): Pattern name fallback (mvc, clean, hexagonal, flat)

    Output payload adds:
        - config (dict): Resolved configuration
    """

    def call(self, payload):
        config_path = payload.get("config_path")
        pattern = payload.get("pattern")
        config = load_config(config_path=config_path, pattern=pattern)
        return payload.insert("config", config)
