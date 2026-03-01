"""
Remote manifest fetcher for the Erdos Proof Mining System.

Fetches problem manifests from GitHub repositories with local caching,
TTL-based refresh, schema validation, and offline fallback.
"""

import json
import logging
import time
import urllib.request
import urllib.error
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Default cache location
DEFAULT_CACHE_DIR = Path.home() / ".erdos-prover" / "cache"
MANIFEST_CACHE_FILE = "manifest_cache.json"
MANIFEST_META_FILE = "manifest_meta.json"

# Default TTL: 1 hour
DEFAULT_TTL_SECONDS = 3600


@dataclass
class ManifestProblem:
    """A problem entry from the manifest."""
    id: str
    path: str
    difficulty: str = "Unknown"
    maintainer_note: str = ""


@dataclass
class Manifest:
    """Parsed and validated manifest."""
    active_campaign: str = ""
    min_app_version: str = "0.0.0"
    problems: list[ManifestProblem] = field(default_factory=list)
    banned_tactics: list[str] = field(default_factory=list)
    repository_url: str = ""
    repository_branch: str = "main"
    source: str = "unknown"  # "remote", "cache", "local"

    @property
    def problem_ids(self) -> list[str]:
        return [p.id for p in self.problems]


def _convert_github_url(url: str) -> str:
    """Convert a GitHub URL to a raw content URL if needed.

    Handles:
    - github.com/owner/repo/blob/branch/path -> raw.githubusercontent.com
    - Already-raw URLs pass through unchanged
    - API URLs pass through unchanged
    """
    if "raw.githubusercontent.com" in url:
        return url
    if "api.github.com" in url:
        return url

    # Convert github.com blob URLs to raw
    if "github.com" in url and "/blob/" in url:
        return url.replace("github.com", "raw.githubusercontent.com").replace("/blob/", "/")

    # Convert github.com repo URLs to raw (assume manifest.json at root)
    if "github.com" in url and not url.endswith(".json"):
        # Construct raw URL: owner/repo -> raw.githubusercontent.com/owner/repo/main/manifest.json
        parts = url.rstrip("/").split("github.com/")[1].split("/")
        if len(parts) >= 2:
            owner, repo = parts[0], parts[1]
            branch = parts[3] if len(parts) > 3 else "main"
            return f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/manifest.json"

    return url


def validate_manifest_data(data: dict) -> list[str]:
    """Validate manifest data structure. Returns list of errors (empty = valid)."""
    errors = []

    if not isinstance(data, dict):
        return ["Manifest must be a JSON object"]

    problems = data.get("priority_problems", [])
    if not isinstance(problems, list):
        errors.append("'priority_problems' must be a list")
    else:
        for i, p in enumerate(problems):
            if not isinstance(p, dict):
                errors.append(f"Problem {i} must be an object")
                continue
            if "id" not in p:
                errors.append(f"Problem {i} missing 'id'")
            if "path" not in p:
                errors.append(f"Problem {i} missing 'path'")

    return errors


def parse_manifest(data: dict, source: str = "unknown") -> Manifest:
    """Parse a raw manifest dict into a Manifest object."""
    problems = []
    for p in data.get("priority_problems", []):
        problems.append(ManifestProblem(
            id=p["id"],
            path=p["path"],
            difficulty=p.get("difficulty", "Unknown"),
            maintainer_note=p.get("maintainer_note", ""),
        ))

    repo = data.get("repository", {})

    return Manifest(
        active_campaign=data.get("active_campaign", ""),
        min_app_version=data.get("min_app_version", "0.0.0"),
        problems=problems,
        banned_tactics=data.get("banned_tactics", []),
        repository_url=repo.get("url", ""),
        repository_branch=repo.get("branch", "main"),
        source=source,
    )


def fetch_manifest(
    url: str,
    cache_dir: Optional[Path] = None,
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
    force_refresh: bool = False,
) -> Manifest:
    """Fetch a manifest from a remote URL with local caching.

    Args:
        url: GitHub URL or raw content URL for the manifest
        cache_dir: Directory for cached manifests
        ttl_seconds: Cache TTL in seconds (default 1 hour)
        force_refresh: Force re-fetch even if cache is fresh

    Returns:
        Parsed and validated Manifest

    Raises:
        ManifestError: If manifest cannot be fetched or is invalid
    """
    cache = cache_dir or DEFAULT_CACHE_DIR
    cache.mkdir(parents=True, exist_ok=True)

    cache_file = cache / MANIFEST_CACHE_FILE
    meta_file = cache / MANIFEST_META_FILE

    # Check cache freshness
    if not force_refresh and _is_cache_fresh(meta_file, ttl_seconds):
        logger.info("Using cached manifest")
        try:
            return _load_cached_manifest(cache_file)
        except Exception:
            logger.warning("Cached manifest corrupted, re-fetching")

    # Fetch from remote
    raw_url = _convert_github_url(url)
    logger.info(f"Fetching manifest from {raw_url}")

    try:
        data = _fetch_json(raw_url)
    except Exception as e:
        logger.warning(f"Failed to fetch remote manifest: {e}")
        # Fallback to cache (even if stale)
        if cache_file.exists():
            logger.info("Using stale cached manifest (offline fallback)")
            return _load_cached_manifest(cache_file)
        raise ManifestError(f"Cannot fetch manifest and no cache available: {e}")

    # Validate
    errors = validate_manifest_data(data)
    if errors:
        raise ManifestError(f"Invalid manifest: {'; '.join(errors)}")

    # Cache it
    _save_cache(cache_file, meta_file, data, raw_url)

    return parse_manifest(data, source="remote")


def load_local_manifest(path: Path) -> Manifest:
    """Load a manifest from a local file."""
    if not path.exists():
        raise ManifestError(f"Manifest file not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    errors = validate_manifest_data(data)
    if errors:
        raise ManifestError(f"Invalid manifest: {'; '.join(errors)}")

    return parse_manifest(data, source="local")


def merge_manifests(remote: Manifest, local: Manifest) -> Manifest:
    """Merge a remote manifest with local overrides.

    Local problems override remote problems with the same ID.
    Local-only problems are added. Remote-only problems are kept.
    """
    local_ids = {p.id for p in local.problems}
    remote_ids = {p.id for p in remote.problems}

    # Start with remote problems, replace with local where IDs match
    problems = []
    for p in remote.problems:
        local_match = next((lp for lp in local.problems if lp.id == p.id), None)
        problems.append(local_match if local_match else p)

    # Add local-only problems
    for p in local.problems:
        if p.id not in remote_ids:
            problems.append(p)

    return Manifest(
        active_campaign=remote.active_campaign or local.active_campaign,
        min_app_version=remote.min_app_version,
        problems=problems,
        banned_tactics=list(set(remote.banned_tactics + local.banned_tactics)),
        repository_url=remote.repository_url or local.repository_url,
        repository_branch=remote.repository_branch,
        source="merged",
    )


class ManifestError(Exception):
    """Error fetching or parsing a manifest."""
    pass


# ── Internal helpers ──

def _fetch_json(url: str) -> dict:
    """Fetch JSON from a URL."""
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _is_cache_fresh(meta_file: Path, ttl_seconds: int) -> bool:
    """Check if the cached manifest is within TTL."""
    if not meta_file.exists():
        return False
    try:
        with open(meta_file, "r", encoding="utf-8") as f:
            meta = json.load(f)
        fetched_at = meta.get("fetched_at", 0)
        return (time.time() - fetched_at) < ttl_seconds
    except (json.JSONDecodeError, OSError):
        return False


def _load_cached_manifest(cache_file: Path) -> Manifest:
    """Load manifest from cache file."""
    with open(cache_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    return parse_manifest(data, source="cache")


def _save_cache(cache_file: Path, meta_file: Path, data: dict, url: str) -> None:
    """Save manifest and metadata to cache."""
    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    meta = {"fetched_at": time.time(), "url": url}
    with open(meta_file, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)
