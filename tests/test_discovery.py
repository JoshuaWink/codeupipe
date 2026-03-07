"""Tests for Registry.discover() — auto-scan directories for CUP components."""

import os
import subprocess

import pytest

from codeupipe import Payload
from codeupipe.registry import Registry


# ── Fixtures ─────────────────────────────────────────────────

@pytest.fixture
def component_dir(tmp_path):
    """Create a temp directory with various CUP component files."""
    # A filter
    (tmp_path / "sanitize.py").write_text(
        "from codeupipe import Payload\n\n"
        "class SanitizeFilter:\n"
        "    def call(self, payload: Payload) -> Payload:\n"
        "        return payload\n"
    )
    # A tap
    (tmp_path / "audit_log.py").write_text(
        "from codeupipe import Payload\n\n"
        "class AuditLogTap:\n"
        "    def observe(self, payload: Payload) -> None:\n"
        "        pass\n"
    )
    # A stream filter
    (tmp_path / "fan_out.py").write_text(
        "from codeupipe import Payload\n\n"
        "class FanOutStreamFilter:\n"
        "    async def stream(self, chunk: Payload):\n"
        "        yield chunk\n"
    )
    # A hook (inherits from Hook ABC)
    (tmp_path / "timing_hook.py").write_text(
        "from codeupipe.core.hook import Hook\n\n"
        "class TimingHook(Hook):\n"
        "    async def before(self, filter, payload):\n"
        "        pass\n"
        "    async def after(self, filter, payload):\n"
        "        pass\n"
    )
    # A non-component file (just a helper)
    (tmp_path / "helpers.py").write_text(
        "def format_name(s):\n"
        "    return s.strip().title()\n"
    )
    # __init__.py should be skipped
    (tmp_path / "__init__.py").write_text("")
    return tmp_path


@pytest.fixture
def nested_dir(tmp_path):
    """Directory with nested sub-directories."""
    filters_dir = tmp_path / "filters"
    filters_dir.mkdir()
    (filters_dir / "__init__.py").write_text("")
    (filters_dir / "validate.py").write_text(
        "from codeupipe import Payload\n\n"
        "class ValidateFilter:\n"
        "    def call(self, payload):\n"
        "        return payload\n"
    )
    taps_dir = tmp_path / "taps"
    taps_dir.mkdir()
    (taps_dir / "__init__.py").write_text("")
    (taps_dir / "logger.py").write_text(
        "from codeupipe import Payload\n\n"
        "class LoggerTap:\n"
        "    def observe(self, payload):\n"
        "        pass\n"
    )
    return tmp_path


@pytest.fixture
def decorated_dir(tmp_path):
    """Directory with components using @cup_component decorator."""
    (tmp_path / "custom.py").write_text(
        "from codeupipe.registry import cup_component\n"
        "from codeupipe import Payload\n\n"
        "@cup_component('custom-sanitize', kind='filter')\n"
        "class WeirdName:\n"
        "    def call(self, payload: Payload) -> Payload:\n"
        "        return payload\n"
    )
    return tmp_path


# ── Discovery Tests ──────────────────────────────────────────

class TestDiscovery:
    """Registry.discover() auto-scanning."""

    def test_discovers_filter(self, component_dir):
        reg = Registry()
        reg.discover(str(component_dir))
        assert reg.has("SanitizeFilter")
        info = reg.info("SanitizeFilter")
        assert info["kind"] == "filter"

    def test_discovers_tap(self, component_dir):
        reg = Registry()
        reg.discover(str(component_dir))
        assert reg.has("AuditLogTap")
        info = reg.info("AuditLogTap")
        assert info["kind"] == "tap"

    def test_discovers_stream_filter(self, component_dir):
        reg = Registry()
        reg.discover(str(component_dir))
        assert reg.has("FanOutStreamFilter")
        info = reg.info("FanOutStreamFilter")
        assert info["kind"] == "stream-filter"

    def test_discovers_hook(self, component_dir):
        reg = Registry()
        reg.discover(str(component_dir))
        assert reg.has("TimingHook")
        info = reg.info("TimingHook")
        assert info["kind"] == "hook"

    def test_skips_non_components(self, component_dir):
        reg = Registry()
        reg.discover(str(component_dir))
        assert not reg.has("format_name")

    def test_skips_init(self, component_dir):
        reg = Registry()
        reg.discover(str(component_dir))
        # No class from __init__.py should be registered
        names = reg.list()
        assert all("__init__" not in n for n in names)

    def test_returns_count(self, component_dir):
        reg = Registry()
        count = reg.discover(str(component_dir))
        assert count == 4  # filter + tap + stream-filter + hook

    def test_recursive_discover(self, nested_dir):
        reg = Registry()
        count = reg.discover(str(nested_dir), recursive=True)
        assert reg.has("ValidateFilter")
        assert reg.has("LoggerTap")
        assert count == 2

    def test_non_recursive_skips_subdirs(self, nested_dir):
        reg = Registry()
        count = reg.discover(str(nested_dir), recursive=False)
        assert count == 0
        assert not reg.has("ValidateFilter")

    def test_discover_nonexistent_dir_raises(self):
        reg = Registry()
        with pytest.raises(FileNotFoundError):
            reg.discover("/nonexistent/path")

    def test_discover_multiple_dirs(self, component_dir, nested_dir):
        reg = Registry()
        reg.discover(str(component_dir))
        reg.discover(str(nested_dir), recursive=True)
        assert reg.has("SanitizeFilter")
        assert reg.has("ValidateFilter")

    def test_discover_lazy_import(self, component_dir):
        """Discovery via AST scan doesn't import the module."""
        reg = Registry()
        reg.discover(str(component_dir))
        # The module shouldn't be in sys.modules
        import sys
        assert "sanitize" not in sys.modules

    def test_get_after_discover_returns_instance(self, component_dir):
        """Getting a discovered component imports and instantiates it."""
        reg = Registry()
        reg.discover(str(component_dir))
        instance = reg.get("SanitizeFilter")
        assert hasattr(instance, "call")

    def test_discover_with_syntax_error(self, tmp_path):
        """Files with syntax errors are skipped gracefully."""
        (tmp_path / "bad.py").write_text("class Broken(\n")
        (tmp_path / "good.py").write_text(
            "class GoodFilter:\n"
            "    def call(self, payload):\n"
            "        return payload\n"
        )
        reg = Registry()
        count = reg.discover(str(tmp_path))
        assert count == 1
        assert reg.has("GoodFilter")
