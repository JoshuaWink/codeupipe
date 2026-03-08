"""
AssembleDocReport: Merge all doc-check findings into a structured report.

Combines results from ScanDocs, ResolveRefs, CheckSymbols, DetectDrift,
and CheckIndex into a single structured report with summary counts and
detail items.
"""

from codeupipe import Payload


class AssembleDocReport:
    """
    Filter (sync): Assemble the final doc-check report.

    Input keys:
        - doc_refs (list[dict]): from ScanDocs
        - resolved_refs (list[dict]): from ResolveRefs
        - drifted_refs (list[dict]): from DetectDrift
        - symbol_issues (list[dict]): from CheckSymbols
        - index_issues (list[dict]): from CheckIndex (optional)

    Output keys (added):
        - doc_report (dict): structured report with:
            total_refs, drifted, missing_symbols, missing_files,
            unmapped_files, status ("ok"|"stale"), details (list)
    """

    def call(self, payload: Payload) -> Payload:
        doc_refs = payload.get("doc_refs", [])
        resolved = payload.get("resolved_refs", [])
        drifted = payload.get("drifted_refs", [])
        symbol_issues = payload.get("symbol_issues", [])
        index_issues = payload.get("index_issues", [])

        missing_files = sum(1 for r in resolved if not r.get("exists", True))

        details = []

        for d in drifted:
            details.append({
                "type": "drift",
                "file": d["file"],
                "doc_path": d["doc_path"],
                "line": d["line"],
                "content": d.get("content", ""),
                "stored_hash": d["stored_hash"],
                "current_hash": d["current_hash"],
                "message": (
                    f"Hash drift: stored={d['stored_hash']}, "
                    f"current={d['current_hash']}"
                ),
            })

        for s in symbol_issues:
            details.append({
                "type": "missing_symbol",
                "file": s["file"],
                "doc_path": s["doc_path"],
                "line": s["line"],
                "content": s.get("content", ""),
                "message": f"Symbol '{s['symbol']}' not found in {s['file']}",
            })

        for r in resolved:
            if not r.get("exists", True):
                details.append({
                    "type": "missing_file",
                    "file": r["file"],
                    "doc_path": r["doc_path"],
                    "line": r["line"],
                    "content": r.get("content", ""),
                    "message": f"Referenced file '{r['file']}' does not exist",
                })

        for idx in index_issues:
            details.append({
                "type": "unmapped_file",
                "file": idx["file"],
                "doc_path": "INDEX.md",
                "line": 0,
                "message": idx["message"],
            })

        has_issues = (
            len(drifted) > 0
            or len(symbol_issues) > 0
            or missing_files > 0
            or len(index_issues) > 0
        )

        report = {
            "total_refs": len(doc_refs),
            "drifted": len(drifted),
            "missing_symbols": len(symbol_issues),
            "missing_files": missing_files,
            "unmapped_files": len(index_issues),
            "status": "stale" if has_issues else "ok",
            "details": details,
        }

        return payload.insert("doc_report", report)
