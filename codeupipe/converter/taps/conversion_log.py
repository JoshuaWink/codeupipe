"""
ConversionLogTap: Logs conversion progress without modifying the payload.
"""

from typing import List


class ConversionLogTap:
    """
    Tap: Logs the current conversion state for observability.

    Captures log entries into an internal list for inspection.
    """

    def __init__(self):
        self.entries: List[str] = []

    def observe(self, payload):
        config = payload.get("config")
        steps = payload.get("steps")
        classified = payload.get("classified")
        classified_files = payload.get("classified_files")
        files = payload.get("files")
        cup_files = payload.get("cup_files")

        if config and not steps and not classified:
            pattern = config.get("pattern", "?")
            self.entries.append(f"Config loaded: pattern={pattern}")

        if steps and not classified:
            self.entries.append(f"Analyzed: {len(steps)} steps")

        if classified:
            roles = list(classified.keys())
            self.entries.append(f"Classified into roles: {roles}")

        if classified_files:
            roles = list(classified_files.keys())
            total = sum(len(v) for v in classified_files.values())
            self.entries.append(f"Scanned {total} files into roles: {roles}")

        if files:
            self.entries.append(f"Generated {len(files)} export files")

        if cup_files:
            self.entries.append(f"Generated {len(cup_files)} CUP files")
