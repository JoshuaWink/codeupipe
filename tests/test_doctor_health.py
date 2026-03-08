"""Tests for doctor health check delegation.

Verifies that _check_connectors delegates to connect.check_health()
when connectors are configured in cup.toml.
"""

import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from codeupipe.doctor import _check_connectors


class TestDoctorConnectorHealth:
    """Doctor delegates connector checks to check_health()."""

    def test_no_manifest_skipped(self, tmp_path):
        """No cup.toml → skip with ok=True."""
        result = _check_connectors(tmp_path)
        assert result["ok"] is True
        assert "skipped" in result["message"].lower()

    def test_no_connectors_section(self, tmp_path):
        """cup.toml exists but no [connectors] → ok."""
        (tmp_path / "cup.toml").write_text('[project]\nname = "test"\n')
        result = _check_connectors(tmp_path)
        assert result["ok"] is True
        assert "No connectors" in result["message"]

    @patch("codeupipe.connect.check_health")
    @patch("codeupipe.connect.discover_connectors")
    @patch("codeupipe.connect.load_connector_configs")
    @patch("codeupipe.registry.Registry")
    @patch("codeupipe.deploy.manifest.load_manifest")
    def test_all_connectors_healthy(self, mock_manifest, mock_reg_cls, mock_load, mock_discover, mock_health, tmp_path):
        """All connectors healthy → ok=True."""
        (tmp_path / "cup.toml").write_text('[project]\nname = "test"\n[connectors.mydb]\npackage = "test"\n')
        mock_manifest.return_value = {
            "project": {"name": "test"},
            "connectors": {"mydb": {"package": "test"}},
        }
        mock_load.return_value = [MagicMock()]
        mock_discover.return_value = ["mydb"]
        mock_health.return_value = {"mydb": True}

        result = _check_connectors(tmp_path)
        assert result["ok"] is True
        assert "healthy" in result["message"]

    @patch("codeupipe.connect.check_health")
    @patch("codeupipe.connect.discover_connectors")
    @patch("codeupipe.connect.load_connector_configs")
    @patch("codeupipe.registry.Registry")
    @patch("codeupipe.deploy.manifest.load_manifest")
    def test_unhealthy_connector_fails(self, mock_manifest, mock_reg_cls, mock_load, mock_discover, mock_health, tmp_path):
        """Unhealthy connector → ok=False with details."""
        (tmp_path / "cup.toml").write_text('[project]\nname = "test"\n[connectors.redis]\npackage = "test"\n')
        mock_manifest.return_value = {
            "project": {"name": "test"},
            "connectors": {"redis": {"package": "test"}},
        }
        mock_load.return_value = [MagicMock()]
        mock_discover.return_value = ["redis"]
        mock_health.return_value = {"redis": False}

        result = _check_connectors(tmp_path)
        assert result["ok"] is False
        assert "unhealthy" in result["message"]
        assert "redis" in result["unhealthy"]
