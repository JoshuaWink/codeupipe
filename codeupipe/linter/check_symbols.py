"""
CheckSymbols: AST-verify that referenced symbols exist in source files.

Parses each referenced source file and checks that the symbols mentioned
in cup:ref markers actually exist as top-level classes, functions, or
class attributes/methods.
"""

import ast
from pathlib import Path
from typing import List, Optional, Set

from codeupipe import Payload


def _collect_top_level_names(tree: ast.Module) -> Set[str]:
    """Collect top-level class and function names from an AST."""
    names = set()
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    names.add(target.id)
    return names


def _collect_class_members(tree: ast.Module, class_name: str) -> Set[str]:
    """Collect method and assignment attribute names within a class."""
    members = set()
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            for child in ast.iter_child_nodes(node):
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    members.add(child.name)
                elif isinstance(child, ast.Assign):
                    for target in child.targets:
                        if isinstance(target, ast.Name):
                            members.add(target.id)
            # Also check __init__ for self.attr assignments
            for child in ast.walk(node):
                if isinstance(child, ast.Assign):
                    for target in child.targets:
                        if (isinstance(target, ast.Attribute)
                                and isinstance(target.value, ast.Name)
                                and target.value.id == "self"):
                            members.add(target.attr)
    return members


class CheckSymbols:
    """
    Filter (sync): Verify referenced symbols exist in source files.

    Input keys:
        - directory (str): root directory
        - resolved_refs (list[dict]): from ResolveRefs

    Output keys (added):
        - symbol_issues (list[dict]): symbols not found, each with:
            symbol, file, doc_path, line
    """

    def call(self, payload: Payload) -> Payload:
        resolved = payload.get("resolved_refs", [])
        issues: List[dict] = []

        for ref in resolved:
            if not ref.get("exists", False):
                continue

            symbols = ref.get("symbols", [])
            if not symbols:
                continue

            abs_path = ref["abs_path"]
            try:
                source = Path(abs_path).read_text(encoding="utf-8", errors="replace")
                tree = ast.parse(source)
            except (SyntaxError, OSError):
                continue

            top_names = _collect_top_level_names(tree)

            for symbol in symbols:
                if "." in symbol:
                    # Dotted: Class.member
                    parts = symbol.split(".", 1)
                    class_name, member_name = parts[0], parts[1]
                    if class_name not in top_names:
                        issues.append({
                            "symbol": symbol,
                            "file": ref["file"],
                            "doc_path": ref["doc_path"],
                            "line": ref["line"],
                            "content": ref.get("content", ""),
                        })
                    else:
                        members = _collect_class_members(tree, class_name)
                        if member_name not in members:
                            issues.append({
                                "symbol": symbol,
                                "file": ref["file"],
                                "doc_path": ref["doc_path"],
                                "line": ref["line"],
                                "content": ref.get("content", ""),
                            })
                else:
                    if symbol not in top_names:
                        issues.append({
                            "symbol": symbol,
                            "file": ref["file"],
                            "doc_path": ref["doc_path"],
                            "line": ref["line"],
                            "content": ref.get("content", ""),
                        })

        return payload.insert("symbol_issues", issues)
