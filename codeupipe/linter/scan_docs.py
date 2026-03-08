"""
ScanDocs: Extract cup:ref markers from markdown files.

Recursively scans all .md files under a directory for <!-- cup:ref ... --> markers
and produces a list of doc-code references for downstream validation.
Also captures the content between opening and closing markers so
downstream consumers can highlight what needs review.
"""

import re
from pathlib import Path

from codeupipe import Payload


_MARKER_RE = re.compile(
    r"<!--\s*cup:ref\s+(.*?)\s*-->",
    re.IGNORECASE,
)

_CLOSE_RE = re.compile(
    r"<!--\s*/cup:ref\s*-->",
    re.IGNORECASE,
)

_ATTR_RE = re.compile(r"(\w+)=(\S+)")


class ScanDocs:
    """
    Filter (sync): Scan .md files for cup:ref markers.

    Input keys:
        - directory (str): root directory to scan

    Output keys (added):
        - doc_refs (list[dict]): extracted references, each with:
            file, symbols, hash, doc_path, line, content
    """

    def call(self, payload: Payload) -> Payload:
        directory = Path(payload.get("directory", "."))
        refs = []

        for md_path in sorted(directory.rglob("*.md")):
            text = md_path.read_text(encoding="utf-8", errors="replace")
            lines = text.splitlines()

            # Track stacked markers: multiple opening refs share one content block
            open_group = []   # refs in current group (by index into refs)
            content_lines = []
            depth = 0
            in_code_block = False

            for line_num, line in enumerate(lines, start=1):
                # Track fenced code blocks (```) — skip markers inside them
                stripped = line.strip()
                if stripped.startswith("```"):
                    in_code_block = not in_code_block
                if in_code_block:
                    if depth > 0:
                        content_lines.append(line)
                    continue

                # Check for opening marker first
                open_match = _MARKER_RE.search(line)
                close_match = _CLOSE_RE.search(line)

                if open_match and not close_match:
                    attrs_str = open_match.group(1)
                    attrs = dict(_ATTR_RE.findall(attrs_str))

                    if "file" not in attrs:
                        continue

                    symbols_raw = attrs.get("symbols", "")
                    symbols = [s for s in symbols_raw.split(",") if s]

                    ref = {
                        "file": attrs["file"],
                        "symbols": symbols,
                        "hash": attrs.get("hash", None),
                        "doc_path": str(md_path),
                        "line": line_num,
                        "content": "",
                    }
                    refs.append(ref)
                    open_group.append(len(refs) - 1)
                    depth += 1
                    # Reset content accumulator when entering a new group
                    if depth == 1:
                        content_lines = []

                elif close_match and depth > 0:
                    depth -= 1
                    if depth == 0:
                        captured = "\n".join(content_lines).strip()
                        for idx in open_group:
                            refs[idx]["content"] = captured
                        open_group = []
                        content_lines = []

                elif depth > 0:
                    content_lines.append(line)

        return payload.insert("doc_refs", refs)
