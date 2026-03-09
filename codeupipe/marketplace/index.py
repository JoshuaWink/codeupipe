"""
Marketplace index — fetch, cache, search, and inspect connector metadata.

The index is a static JSON file hosted on GitHub, fetched via urllib.
A local cache file avoids repeated network calls. Zero external deps.
"""

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.error import URLError
from urllib.request import Request, urlopen

__all__ = ["fetch_index", "search", "info", "MarketplaceError"]

# Default index URL — raw GitHub JSON from the standalone marketplace repo
INDEX_URL = (
    "https://raw.githubusercontent.com/codeuchain/codeupipe-marketplace/"
    "main/index.json"
)

# Cache lives under ~/.codeupipe/marketplace/
_CACHE_DIR = Path.home() / ".codeupipe" / "marketplace"
_CACHE_FILE = _CACHE_DIR / "index.json"
_CACHE_MAX_AGE = 3600  # 1 hour


class MarketplaceError(Exception):
    """Raised when the marketplace index cannot be fetched or parsed."""


def _read_cache() -> Optional[Dict[str, Any]]:
    """Return cached index if fresh, else None."""
    if not _CACHE_FILE.exists():
        return None
    age = time.time() - _CACHE_FILE.stat().st_mtime
    if age > _CACHE_MAX_AGE:
        return None
    try:
        return json.loads(_CACHE_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _write_cache(data: Dict[str, Any]) -> None:
    """Write index data to cache file."""
    try:
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        _CACHE_FILE.write_text(
            json.dumps(data, indent=2), encoding="utf-8"
        )
    except OSError:
        pass  # Cache write failure is non-fatal


def fetch_index(
    url: Optional[str] = None,
    timeout: int = 10,
    force: bool = False,
) -> Dict[str, Any]:
    """Fetch the marketplace index JSON.

    Checks the local cache first (unless *force* is True).  Falls back to
    the cache on network failure.

    Args:
        url: Override index URL (useful for testing / mirrors).
        timeout: HTTP timeout in seconds.
        force: Bypass cache and always fetch from network.

    Returns:
        Parsed index dict with 'version' and 'connectors' keys.

    Raises:
        MarketplaceError: If the index cannot be fetched or parsed.
    """
    if not force:
        cached = _read_cache()
        if cached is not None:
            return cached

    target = url or os.environ.get("CUP_MARKETPLACE_URL") or INDEX_URL
    try:
        req = Request(target, headers={"User-Agent": "codeupipe-marketplace"})
        with urlopen(req, timeout=timeout) as resp:  # noqa: S310 — URL is controlled
            raw = resp.read().decode("utf-8")
        data = json.loads(raw)
    except (URLError, OSError, json.JSONDecodeError) as exc:
        # Fall back to stale cache on network failure
        if _CACHE_FILE.exists():
            try:
                return json.loads(_CACHE_FILE.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass
        raise MarketplaceError(f"Failed to fetch marketplace index: {exc}") from exc

    _write_cache(data)
    return data


def search(
    index: Dict[str, Any],
    query: str,
    category: Optional[str] = None,
    provider: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Search connectors in the marketplace index.

    Args:
        index: Parsed index from fetch_index().
        query: Free-text keyword to match against name, description, filters.
        category: Optional category filter (exact match).
        provider: Optional provider filter (exact match).

    Returns:
        List of matching connector entries.
    """
    connectors = index.get("connectors", [])
    query_lower = query.lower().strip()
    results: List[Dict[str, Any]] = []

    for entry in connectors:
        # Category filter
        if category and category.lower() not in [
            c.lower() for c in entry.get("categories", [])
        ]:
            continue
        # Provider filter
        if provider and entry.get("provider", "").lower() != provider.lower():
            continue
        # Keyword match: name, description, filters, categories, provider
        if query_lower:
            searchable = " ".join([
                entry.get("name", ""),
                entry.get("description", ""),
                entry.get("provider", ""),
                " ".join(entry.get("filters", [])),
                " ".join(entry.get("categories", [])),
            ]).lower()
            if query_lower not in searchable:
                continue
        results.append(entry)

    return results


def info(index: Dict[str, Any], package_name: str) -> Optional[Dict[str, Any]]:
    """Get detailed info for a single connector package.

    Args:
        index: Parsed index from fetch_index().
        package_name: Package name (e.g. 'codeupipe-stripe').

    Returns:
        Connector entry dict, or None if not found.
    """
    for entry in index.get("connectors", []):
        if entry.get("name", "").lower() == package_name.lower():
            return entry
        # Also match by provider shorthand
        if entry.get("provider", "").lower() == package_name.lower():
            return entry
    return None
