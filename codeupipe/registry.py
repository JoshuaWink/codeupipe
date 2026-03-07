"""
Registry: Name-based component catalog for codeupipe.

Provides:
- Registry: name → component mapping with lazy import from discovery
- cup_component: decorator for explicit registration
- default_registry: module-level convenience instance
"""

import ast
import importlib
import importlib.util
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Type, Union

__all__ = ["Registry", "cup_component", "default_registry"]


# ── Component classification (reuses linter logic) ───────────

def _classify_class_node(node: ast.ClassDef) -> Optional[str]:
    """Classify an AST ClassDef as a CUP component kind, or None."""
    methods = {
        n.name
        for n in ast.iter_child_nodes(node)
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    for base in node.bases:
        base_name = getattr(base, "id", None)
        if base_name == "Hook":
            return "hook"
    if "stream" in methods:
        return "stream-filter"
    if "call" in methods:
        return "filter"
    if "observe" in methods:
        return "tap"
    return None


def _classify_instance(obj: Any) -> Optional[str]:
    """Classify a class or instance at runtime by checking methods/bases."""
    cls = obj if isinstance(obj, type) else type(obj)
    from codeupipe.core.hook import Hook
    if issubclass(cls, Hook):
        return "hook"
    if hasattr(cls, "stream") and callable(getattr(cls, "stream")):
        return "stream-filter"
    if hasattr(cls, "call") and callable(getattr(cls, "call")):
        return "filter"
    if hasattr(cls, "observe") and callable(getattr(cls, "observe")):
        return "tap"
    return None


# ── Registry Entry ───────────────────────────────────────────

class _Entry:
    """Internal registry entry — either a direct class/factory or a lazy reference."""

    __slots__ = ("target", "module_path", "class_name", "kind")

    def __init__(
        self,
        target: Optional[Union[Type, Callable]] = None,
        module_path: Optional[str] = None,
        class_name: Optional[str] = None,
        kind: Optional[str] = None,
    ):
        self.target = target
        self.module_path = module_path
        self.class_name = class_name
        self.kind = kind

    def resolve(self, **kwargs) -> Any:
        """Get a fresh instance. Lazy-imports if needed."""
        if self.target is None and self.module_path and self.class_name:
            self.target = self._lazy_import()

        target = self.target
        if target is None:
            raise RuntimeError("Registry entry has no target")

        if isinstance(target, type):
            return target(**kwargs) if kwargs else target()
        if callable(target):
            return target(**kwargs)
        raise TypeError(f"Registry target is not callable: {target!r}")

    def _lazy_import(self) -> Type:
        """Import a module by file path and extract the class."""
        spec = importlib.util.spec_from_file_location(
            f"_cup_discovered.{self.class_name}", self.module_path,
        )
        if spec is None or spec.loader is None:
            raise ImportError(f"Cannot load {self.module_path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        cls = getattr(module, self.class_name, None)
        if cls is None:
            raise ImportError(
                f"Class {self.class_name} not found in {self.module_path}"
            )
        return cls


# ── Registry ─────────────────────────────────────────────────

class Registry:
    """
    Name → component catalog.

    Usage:
        reg = Registry()
        reg.register(SanitizeFilter)              # auto-name from class
        reg.register("custom-name", SanitizeFilter)  # explicit name
        reg.register("factory", my_factory_fn)     # factory callable
        reg.discover("myproject/filters/")         # auto-scan directory
        instance = reg.get("SanitizeFilter")       # fresh instance
    """

    def __init__(self):
        self._entries: Dict[str, _Entry] = {}

    def register(
        self,
        name_or_target: Union[str, Type, Callable],
        target: Optional[Union[Type, Callable]] = None,
        *,
        kind: Optional[str] = None,
        force: bool = False,
    ) -> None:
        """Register a component class or factory.

        Signatures:
            register(MyClass)                  — name = "MyClass"
            register("name", MyClass)          — explicit name
            register("name", factory_fn)       — callable factory
            register(factory_fn)               — name = fn.__name__
        """
        if isinstance(name_or_target, str):
            name = name_or_target
            if target is None:
                raise TypeError("register('name') requires a second argument (class or factory)")
        else:
            target = name_or_target
            name = getattr(target, "__name__", None)
            if name is None:
                raise TypeError(f"Cannot determine name for {target!r}. Pass an explicit name.")

        if not force and name in self._entries:
            raise ValueError(f"'{name}' already registered. Use force=True to overwrite.")

        if kind is None:
            kind = _classify_instance(target) if isinstance(target, type) else None

        self._entries[name] = _Entry(target=target, kind=kind)

    def get(self, name: str, **kwargs) -> Any:
        """Get a fresh instance by name. kwargs are passed to constructor/factory."""
        if name not in self._entries:
            raise KeyError(f"'{name}' not registered in this Registry")
        return self._entries[name].resolve(**kwargs)

    def has(self, name: str) -> bool:
        """Check if a name is registered."""
        return name in self._entries

    def list(self) -> List[str]:
        """List all registered names."""
        return sorted(self._entries.keys())

    def info(self, name: str) -> Dict[str, Any]:
        """Get metadata about a registered component."""
        if name not in self._entries:
            raise KeyError(f"'{name}' not registered")
        entry = self._entries[name]
        return {
            "name": name,
            "kind": entry.kind,
            "lazy": entry.target is None,
            "module_path": entry.module_path,
            "class_name": entry.class_name,
        }

    def unregister(self, name: str) -> None:
        """Remove a registered component."""
        if name not in self._entries:
            raise KeyError(f"'{name}' not registered")
        del self._entries[name]

    def __len__(self) -> int:
        return len(self._entries)

    # ── Discovery ────────────────────────────────────────────

    def discover(self, directory: str, *, recursive: bool = False) -> int:
        """Auto-scan a directory for CUP components via AST analysis.

        Components are registered lazily — modules are not imported until
        .get() is called. Returns the number of components discovered.

        Args:
            directory: Path to scan for .py files.
            recursive: If True, scan sub-directories recursively.
        """
        dir_path = Path(directory)
        if not dir_path.is_dir():
            raise FileNotFoundError(f"Directory not found: {directory}")

        count = 0
        glob_pattern = "**/*.py" if recursive else "*.py"

        for py_file in sorted(dir_path.glob(glob_pattern)):
            if py_file.name == "__init__.py":
                continue

            try:
                source = py_file.read_text()
                tree = ast.parse(source, filename=str(py_file))
            except (SyntaxError, OSError):
                continue

            for node in ast.iter_child_nodes(tree):
                if not isinstance(node, ast.ClassDef):
                    continue
                if node.name.startswith("_"):
                    continue

                kind = _classify_class_node(node)
                if kind is None:
                    continue

                name = node.name
                if name not in self._entries:
                    self._entries[name] = _Entry(
                        module_path=str(py_file.resolve()),
                        class_name=name,
                        kind=kind,
                    )
                    count += 1

        return count


# ── Decorator ────────────────────────────────────────────────

def cup_component(
    name: Optional[str] = None,
    *,
    kind: Optional[str] = None,
    registry: Optional[Registry] = None,
):
    """Decorator to register a class as a CUP component.

    Usage:
        @cup_component("sanitize", kind="filter", registry=my_reg)
        class Sanitize:
            def call(self, payload): ...

        @cup_component(registry=my_reg)
        class AutoNamed:
            def call(self, payload): ...
    """
    # Handle @cup_component being called with just a class (no parens, no args)
    if isinstance(name, type):
        cls = name
        _reg = default_registry if registry is None else registry
        _name = cls.__name__
        _kind = kind or _classify_instance(cls)
        _reg._entries[_name] = _Entry(target=cls, kind=_kind)
        return cls

    def decorator(cls):
        _reg = default_registry if registry is None else registry
        _name = name or cls.__name__
        _kind = kind or _classify_instance(cls)
        if _name in _reg._entries:
            raise ValueError(f"'{_name}' already registered")
        _reg._entries[_name] = _Entry(target=cls, kind=_kind)
        return cls

    return decorator


# ── Default Registry (module singleton) ──────────────────────

default_registry = Registry()
