"""
DetectDrift: Compare stored hashes with current file content hashes.

Flags doc references where the stored hash no longer matches the current
file contents, indicating the source has changed since the doc was written.
"""

from codeupipe import Payload


class DetectDrift:
    """
    Filter (sync): Detect hash drift between docs and source files.

    Input keys:
        - resolved_refs (list[dict]): from ResolveRefs

    Output keys (added):
        - drifted_refs (list[dict]): refs with hash mismatches, each with:
            file, stored_hash, current_hash, doc_path, line
    """

    def call(self, payload: Payload) -> Payload:
        resolved = payload.get("resolved_refs", [])
        drifted = []

        for ref in resolved:
            stored_hash = ref.get("hash")
            if stored_hash is None:
                # No stored hash — symbol-only mode, skip drift check
                continue

            current_hash = ref.get("current_hash")

            if current_hash != stored_hash:
                drifted.append({
                    "file": ref["file"],
                    "stored_hash": stored_hash,
                    "current_hash": current_hash,
                    "doc_path": ref["doc_path"],
                    "line": ref["line"],
                    "content": ref.get("content", ""),
                })

        return payload.insert("drifted_refs", drifted)
