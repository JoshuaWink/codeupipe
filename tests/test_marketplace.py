"""
Tests for codeupipe.marketplace — Ring 9: Marketplace.

Covers: index fetch, cache, search, info, offline fallback, error handling.
"""

import json
import os
import time
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from threading import Thread
from unittest.mock import patch

import pytest

from codeupipe.marketplace import MarketplaceError, fetch_index, info, search


# ── Fixtures ────────────────────────────────────────────────────────


SAMPLE_INDEX = {
    "version": 1,
    "updated": "2026-03-07T00:00:00Z",
    "connectors": [
        {
            "name": "codeupipe-google-ai",
            "provider": "google-ai",
            "pypi": "codeupipe-google-ai",
            "repo": "https://github.com/codeuchain/codeupipe/tree/main/connectors/codeupipe-google-ai",
            "description": "Google AI (Gemini) — multimodal generation, embeddings, and vision",
            "categories": ["ai", "llm", "multimodal", "vision", "embeddings"],
            "filters": ["GeminiGenerate", "GeminiGenerateStream", "GeminiEmbed", "GeminiVision"],
            "trust": "verified",
            "min_codeupipe": "0.8.0",
            "latest": "0.1.0",
        },
        {
            "name": "codeupipe-stripe",
            "provider": "stripe",
            "pypi": "codeupipe-stripe",
            "repo": "https://github.com/codeuchain/codeupipe/tree/main/connectors/codeupipe-stripe",
            "description": "Stripe checkout, subscriptions, and webhooks",
            "categories": ["payments", "billing"],
            "filters": ["StripeCheckout", "StripeSubscription", "StripeWebhook", "StripeCustomer"],
            "trust": "verified",
            "min_codeupipe": "0.8.0",
            "latest": "0.1.0",
        },
        {
            "name": "codeupipe-postgres",
            "provider": "postgres",
            "pypi": "codeupipe-postgres",
            "repo": "https://github.com/codeuchain/codeupipe/tree/main/connectors/codeupipe-postgres",
            "description": "PostgreSQL queries, transactions, and bulk insert",
            "categories": ["database", "sql"],
            "filters": ["PostgresQuery", "PostgresExecute", "PostgresTransaction", "PostgresBulkInsert"],
            "trust": "verified",
            "min_codeupipe": "0.8.0",
            "latest": "0.1.0",
        },
        {
            "name": "codeupipe-resend",
            "provider": "resend",
            "pypi": "codeupipe-resend",
            "repo": "https://github.com/codeuchain/codeupipe/tree/main/connectors/codeupipe-resend",
            "description": "Resend transactional email and template rendering",
            "categories": ["email", "notifications"],
            "filters": ["ResendEmail", "ResendTemplate"],
            "trust": "verified",
            "min_codeupipe": "0.8.0",
            "latest": "0.1.0",
        },
    ],
}


@pytest.fixture
def sample_index():
    """Provide a sample marketplace index dict."""
    return SAMPLE_INDEX


@pytest.fixture
def index_server(tmp_path):
    """Spin up a local HTTP server serving the sample index.json."""
    index_file = tmp_path / "index.json"
    index_file.write_text(json.dumps(SAMPLE_INDEX), encoding="utf-8")

    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *a, **kw):
            super().__init__(*a, directory=str(tmp_path), **kw)

        def log_message(self, *_args):
            pass  # suppress output

    server = HTTPServer(("127.0.0.1", 0), Handler)
    port = server.server_address[1]
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{port}/index.json"
    server.shutdown()


@pytest.fixture(autouse=True)
def clean_cache(tmp_path, monkeypatch):
    """Redirect cache dir to tmp_path so tests don't pollute ~/.codeupipe."""
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    monkeypatch.setattr("codeupipe.marketplace.index._CACHE_DIR", cache_dir)
    monkeypatch.setattr("codeupipe.marketplace.index._CACHE_FILE", cache_dir / "index.json")


# ── fetch_index ─────────────────────────────────────────────────────


class TestFetchIndex:
    """Tests for fetch_index — network, cache, and fallback behavior."""

    def test_fetch_from_server(self, index_server):
        """Fetch index from a live HTTP server."""
        data = fetch_index(url=index_server)
        assert data["version"] == 1
        assert len(data["connectors"]) == 4

    def test_fetch_populates_cache(self, index_server, tmp_path):
        """After fetch, cache file exists."""
        fetch_index(url=index_server)
        cache_file = tmp_path / "cache" / "index.json"
        assert cache_file.exists()
        cached = json.loads(cache_file.read_text())
        assert cached["version"] == 1

    def test_uses_cache_on_second_call(self, index_server, tmp_path):
        """A second fetch uses cache, not network."""
        fetch_index(url=index_server)
        # Modify cache to prove it's being read
        cache_file = tmp_path / "cache" / "index.json"
        modified = SAMPLE_INDEX.copy()
        modified["version"] = 99
        cache_file.write_text(json.dumps(modified))
        data = fetch_index(url=index_server)
        assert data["version"] == 99  # from cache, not server

    def test_force_bypasses_cache(self, index_server, tmp_path):
        """force=True re-fetches from network even with valid cache."""
        fetch_index(url=index_server)
        cache_file = tmp_path / "cache" / "index.json"
        modified = SAMPLE_INDEX.copy()
        modified["version"] = 99
        cache_file.write_text(json.dumps(modified))
        data = fetch_index(url=index_server, force=True)
        assert data["version"] == 1  # from server, not modified cache

    def test_stale_cache_triggers_refetch(self, index_server, tmp_path, monkeypatch):
        """Expired cache triggers network fetch."""
        fetch_index(url=index_server)
        cache_file = tmp_path / "cache" / "index.json"
        # Make cache stale
        old_time = time.time() - 7200  # 2 hours ago
        os.utime(cache_file, (old_time, old_time))
        # Modify server data via cache (just to confirm we refetch)
        data = fetch_index(url=index_server)
        assert data["version"] == 1  # came from server again

    def test_network_failure_falls_back_to_stale_cache(self, tmp_path):
        """On network failure, stale cache is returned."""
        cache_file = tmp_path / "cache" / "index.json"
        cache_file.write_text(json.dumps(SAMPLE_INDEX))
        # Make cache stale
        old_time = time.time() - 7200
        os.utime(cache_file, (old_time, old_time))
        # Fetch from bad URL — should fall back to stale cache
        data = fetch_index(url="http://127.0.0.1:1/nonexistent", timeout=1)
        assert data["version"] == 1

    def test_network_failure_no_cache_raises(self):
        """On network failure with no cache, MarketplaceError is raised."""
        with pytest.raises(MarketplaceError, match="Failed to fetch"):
            fetch_index(url="http://127.0.0.1:1/nonexistent", timeout=1)

    def test_env_var_url_override(self, index_server, monkeypatch):
        """CUP_MARKETPLACE_URL env var overrides default URL."""
        monkeypatch.setenv("CUP_MARKETPLACE_URL", index_server)
        data = fetch_index()  # no url argument — uses env var
        assert data["version"] == 1


# ── search ──────────────────────────────────────────────────────────


class TestSearch:
    """Tests for marketplace search — keyword, category, and provider filtering."""

    def test_search_by_name(self, sample_index):
        results = search(sample_index, "stripe")
        assert len(results) == 1
        assert results[0]["name"] == "codeupipe-stripe"

    def test_search_by_description(self, sample_index):
        results = search(sample_index, "multimodal")
        assert len(results) == 1
        assert results[0]["provider"] == "google-ai"

    def test_search_by_filter_name(self, sample_index):
        results = search(sample_index, "GeminiEmbed")
        assert len(results) == 1
        assert results[0]["name"] == "codeupipe-google-ai"

    def test_search_by_category(self, sample_index):
        results = search(sample_index, "", category="payments")
        assert len(results) == 1
        assert results[0]["provider"] == "stripe"

    def test_search_by_provider(self, sample_index):
        results = search(sample_index, "", provider="postgres")
        assert len(results) == 1
        assert results[0]["name"] == "codeupipe-postgres"

    def test_search_empty_query_returns_all(self, sample_index):
        results = search(sample_index, "")
        assert len(results) == 4

    def test_search_no_match(self, sample_index):
        results = search(sample_index, "twilio")
        assert len(results) == 0

    def test_search_case_insensitive(self, sample_index):
        results = search(sample_index, "STRIPE")
        assert len(results) == 1

    def test_search_category_and_keyword(self, sample_index):
        results = search(sample_index, "checkout", category="payments")
        assert len(results) == 1
        assert results[0]["name"] == "codeupipe-stripe"

    def test_search_category_no_match(self, sample_index):
        results = search(sample_index, "checkout", category="ai")
        assert len(results) == 0

    def test_search_provider_narrows(self, sample_index):
        results = search(sample_index, "", provider="resend")
        assert len(results) == 1
        assert results[0]["name"] == "codeupipe-resend"

    def test_search_by_category_keyword(self, sample_index):
        """Search by category name as keyword (not filter)."""
        results = search(sample_index, "database")
        assert len(results) == 1
        assert results[0]["provider"] == "postgres"


# ── info ────────────────────────────────────────────────────────────


class TestInfo:
    """Tests for marketplace info — single package lookup."""

    def test_info_by_name(self, sample_index):
        entry = info(sample_index, "codeupipe-stripe")
        assert entry is not None
        assert entry["provider"] == "stripe"

    def test_info_by_provider(self, sample_index):
        entry = info(sample_index, "stripe")
        assert entry is not None
        assert entry["name"] == "codeupipe-stripe"

    def test_info_not_found(self, sample_index):
        entry = info(sample_index, "codeupipe-twilio")
        assert entry is None

    def test_info_case_insensitive(self, sample_index):
        entry = info(sample_index, "CODEUPIPE-GOOGLE-AI")
        assert entry is not None
        assert entry["provider"] == "google-ai"

    def test_info_returns_full_entry(self, sample_index):
        entry = info(sample_index, "codeupipe-google-ai")
        assert entry is not None
        assert "filters" in entry
        assert "categories" in entry
        assert entry["trust"] == "verified"
        assert entry["min_codeupipe"] == "0.8.0"

    def test_info_provider_shorthand(self, sample_index):
        """Provider shorthand resolves to full entry."""
        entry = info(sample_index, "resend")
        assert entry is not None
        assert entry["name"] == "codeupipe-resend"
        assert "ResendEmail" in entry["filters"]


# ── Edge cases ──────────────────────────────────────────────────────


class TestEdgeCases:
    """Edge cases for marketplace functions."""

    def test_empty_index(self):
        idx = {"version": 1, "connectors": []}
        assert search(idx, "anything") == []
        assert info(idx, "anything") is None

    def test_missing_connectors_key(self):
        idx = {"version": 1}
        assert search(idx, "anything") == []
        assert info(idx, "anything") is None

    def test_search_partial_entry(self):
        """An entry missing optional fields doesn't crash search."""
        idx = {
            "version": 1,
            "connectors": [{"name": "minimal", "provider": "x", "description": ""}],
        }
        results = search(idx, "minimal")
        assert len(results) == 1


# ── CLI: cup marketplace ────────────────────────────────────────────


class TestCLIMarketplace:
    """Tests for cup marketplace CLI commands."""

    @pytest.fixture(autouse=True)
    def _serve_index(self, index_server, monkeypatch):
        """Point marketplace at the local test server."""
        monkeypatch.setenv("CUP_MARKETPLACE_URL", index_server)

    def test_marketplace_search_all(self, capsys):
        from codeupipe.cli import main

        result = main(["marketplace", "search"])
        assert result == 0
        out = capsys.readouterr().out
        assert "codeupipe-google-ai" in out
        assert "codeupipe-stripe" in out

    def test_marketplace_search_keyword(self, capsys):
        from codeupipe.cli import main

        result = main(["marketplace", "search", "payments"])
        assert result == 0
        out = capsys.readouterr().out
        assert "codeupipe-stripe" in out
        assert "codeupipe-google-ai" not in out

    def test_marketplace_search_no_match(self, capsys):
        from codeupipe.cli import main

        result = main(["marketplace", "search", "twilio"])
        assert result == 0
        out = capsys.readouterr().out
        assert "No connectors found" in out

    def test_marketplace_search_json(self, capsys):
        from codeupipe.cli import main

        result = main(["--json", "marketplace", "search", "stripe"])
        assert result == 0
        out = capsys.readouterr().out
        data = json.loads(out)
        assert "results" in data
        assert len(data["results"]) == 1
        assert data["results"][0]["provider"] == "stripe"

    def test_marketplace_search_category_flag(self, capsys):
        from codeupipe.cli import main

        result = main(["marketplace", "search", "", "--category", "ai"])
        assert result == 0
        out = capsys.readouterr().out
        assert "codeupipe-google-ai" in out

    def test_marketplace_search_provider_flag(self, capsys):
        from codeupipe.cli import main

        result = main(["marketplace", "search", "", "--provider", "resend"])
        assert result == 0
        out = capsys.readouterr().out
        assert "codeupipe-resend" in out

    def test_marketplace_info(self, capsys):
        from codeupipe.cli import main

        result = main(["marketplace", "info", "codeupipe-stripe"])
        assert result == 0
        out = capsys.readouterr().out
        assert "stripe" in out.lower()
        assert "StripeCheckout" in out
        assert "pip install" in out

    def test_marketplace_info_json(self, capsys):
        from codeupipe.cli import main

        result = main(["--json", "marketplace", "info", "codeupipe-google-ai"])
        assert result == 0
        out = capsys.readouterr().out
        data = json.loads(out)
        assert data["provider"] == "google-ai"
        assert "GeminiGenerate" in data["filters"]

    def test_marketplace_info_not_found(self, capsys):
        from codeupipe.cli import main

        result = main(["marketplace", "info", "codeupipe-nonexistent"])
        assert result == 1

    def test_marketplace_info_provider_shorthand(self, capsys):
        from codeupipe.cli import main

        result = main(["marketplace", "info", "postgres"])
        assert result == 0
        out = capsys.readouterr().out
        assert "codeupipe-postgres" in out

    def test_marketplace_no_subcommand(self, capsys):
        from codeupipe.cli import main

        result = main(["marketplace"])
        assert result == 1


# ── Real index.json validation ──────────────────────────────────────


class TestRealIndex:
    """Validate the shipped marketplace/index.json against the actual repo.

    These tests read the real index file and verify that every connector
    it references actually exists on disk with the expected structure.
    Trust-but-verify: the index says it, we confirm it.
    """

    @pytest.fixture()
    def real_index(self):
        """Load the actual marketplace/index.json from the repo root."""
        repo_root = Path(__file__).resolve().parent.parent
        index_path = repo_root / "marketplace" / "index.json"
        assert index_path.exists(), f"marketplace/index.json not found at {index_path}"
        return json.loads(index_path.read_text(encoding="utf-8"))

    def test_index_has_required_keys(self, real_index):
        assert "version" in real_index
        assert "connectors" in real_index
        assert isinstance(real_index["connectors"], list)
        assert len(real_index["connectors"]) > 0

    def test_each_connector_has_required_fields(self, real_index):
        required = {"name", "provider", "pypi", "repo", "description",
                    "categories", "filters", "trust", "min_codeupipe", "latest"}
        for entry in real_index["connectors"]:
            missing = required - set(entry.keys())
            assert not missing, f"{entry.get('name', '?')} missing fields: {missing}"

    def test_connector_directories_exist(self, real_index):
        repo_root = Path(__file__).resolve().parent.parent
        for entry in real_index["connectors"]:
            connector_dir = repo_root / "connectors" / entry["name"]
            assert connector_dir.is_dir(), (
                f"Connector dir missing for {entry['name']}: {connector_dir}"
            )

    def test_connector_pyproject_exists(self, real_index):
        repo_root = Path(__file__).resolve().parent.parent
        for entry in real_index["connectors"]:
            pyproject = repo_root / "connectors" / entry["name"] / "pyproject.toml"
            assert pyproject.is_file(), (
                f"pyproject.toml missing for {entry['name']}: {pyproject}"
            )

    def test_repo_urls_point_to_monorepo(self, real_index):
        for entry in real_index["connectors"]:
            expected_prefix = "https://github.com/codeuchain/codeupipe/tree/main/connectors/"
            assert entry["repo"].startswith(expected_prefix), (
                f"{entry['name']} repo URL doesn't point to monorepo: {entry['repo']}"
            )
            # The URL should end with the connector name
            assert entry["repo"].endswith(entry["name"]), (
                f"{entry['name']} repo URL doesn't end with package name: {entry['repo']}"
            )

    def test_trust_is_valid_tier(self, real_index):
        valid_tiers = {"verified", "community", "unindexed"}
        for entry in real_index["connectors"]:
            assert entry["trust"] in valid_tiers, (
                f"{entry['name']} has invalid trust tier: {entry['trust']}"
            )

    def test_sample_index_matches_real_index(self, real_index):
        """Verify the test fixture stays in sync with the real index."""
        real_names = sorted(e["name"] for e in real_index["connectors"])
        sample_names = sorted(e["name"] for e in SAMPLE_INDEX["connectors"])
        assert real_names == sample_names, (
            f"SAMPLE_INDEX out of sync with real index.\n"
            f"  Real: {real_names}\n"
            f"  Sample: {sample_names}"
        )


# ── Live GitHub fetch tests ─────────────────────────────────────────

LIVE_INDEX_URL = (
    "https://raw.githubusercontent.com/codeuchain/codeupipe/"
    "main/marketplace/index.json"
)


@pytest.mark.live
class TestLiveGitHubIndex:
    """Fetch the real index.json from raw.githubusercontent.com and verify it.

    These tests hit the network. They are marked with @pytest.mark.live
    so they can be skipped in offline/CI environments with:
        pytest -m "not live"

    The tests verify that what GitHub is actually serving matches what
    we have on disk — closing the loop between local edits and what
    users will fetch.
    """

    @pytest.fixture()
    def live_index(self, tmp_path, monkeypatch):
        """Fetch index from GitHub, bypassing the local cache."""
        # Redirect cache to tmp so we don't pollute or read stale local cache
        cache_dir = tmp_path / "live_cache"
        cache_dir.mkdir()
        monkeypatch.setattr("codeupipe.marketplace.index._CACHE_DIR", cache_dir)
        monkeypatch.setattr("codeupipe.marketplace.index._CACHE_FILE", cache_dir / "index.json")
        try:
            return fetch_index(url=LIVE_INDEX_URL, force=True)
        except MarketplaceError:
            pytest.skip("Cannot reach raw.githubusercontent.com — offline?")

    def test_live_fetch_returns_valid_json(self, live_index):
        assert "version" in live_index
        assert "connectors" in live_index
        assert isinstance(live_index["connectors"], list)

    def test_live_fetch_has_connectors(self, live_index):
        assert len(live_index["connectors"]) > 0

    def test_live_connector_names_match_local(self, live_index):
        """What GitHub serves must match what's on disk."""
        repo_root = Path(__file__).resolve().parent.parent
        local_index = json.loads(
            (repo_root / "marketplace" / "index.json").read_text(encoding="utf-8")
        )
        live_names = sorted(e["name"] for e in live_index["connectors"])
        local_names = sorted(e["name"] for e in local_index["connectors"])
        assert live_names == local_names, (
            f"Live GitHub index has different connectors than local.\n"
            f"  Live:  {live_names}\n"
            f"  Local: {local_names}"
        )

    def test_live_repo_urls_are_valid(self, live_index):
        """Every repo URL should point to the monorepo."""
        for entry in live_index["connectors"]:
            assert "codeuchain/codeupipe/tree/main/connectors/" in entry["repo"], (
                f"{entry['name']} has bad repo URL on GitHub: {entry['repo']}"
            )

    def test_live_all_entries_have_required_fields(self, live_index):
        required = {"name", "provider", "pypi", "repo", "description",
                    "categories", "filters", "trust", "min_codeupipe", "latest"}
        for entry in live_index["connectors"]:
            missing = required - set(entry.keys())
            assert not missing, f"{entry.get('name', '?')} missing on GitHub: {missing}"

    def test_live_search_works(self, live_index):
        """Verify search() works against the live-fetched data."""
        results = search(live_index, "stripe")
        assert len(results) == 1
        assert results[0]["name"] == "codeupipe-stripe"

    def test_live_info_works(self, live_index):
        """Verify info() works against the live-fetched data."""
        entry = info(live_index, "google-ai")
        assert entry is not None
        assert entry["name"] == "codeupipe-google-ai"

