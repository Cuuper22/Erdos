"""Tests for the manifest module."""

import json
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from src.manifest import (
    ManifestProblem,
    Manifest,
    ManifestError,
    _convert_github_url,
    validate_manifest_data,
    parse_manifest,
    fetch_manifest,
    load_local_manifest,
    merge_manifests,
    _is_cache_fresh,
    _save_cache,
)


SAMPLE_MANIFEST = {
    "active_campaign": "Test_Q1",
    "min_app_version": "1.0.0",
    "priority_problems": [
        {"id": "P001", "path": "problems/001.lean", "difficulty": "Easy"},
        {"id": "P002", "path": "problems/002.lean", "difficulty": "Hard",
         "maintainer_note": "Use omega"},
    ],
    "banned_tactics": ["sorry", "admit"],
    "repository": {
        "url": "https://github.com/test/repo",
        "branch": "main",
    },
}


class TestConvertGithubUrl:
    """Test GitHub URL conversion."""

    def test_raw_url_passthrough(self):
        url = "https://raw.githubusercontent.com/owner/repo/main/manifest.json"
        assert _convert_github_url(url) == url

    def test_api_url_passthrough(self):
        url = "https://api.github.com/repos/owner/repo/contents/manifest.json"
        assert _convert_github_url(url) == url

    def test_blob_url_converted(self):
        url = "https://github.com/owner/repo/blob/main/manifest.json"
        expected = "https://raw.githubusercontent.com/owner/repo/main/manifest.json"
        assert _convert_github_url(url) == expected

    def test_repo_url_converted(self):
        url = "https://github.com/owner/repo"
        result = _convert_github_url(url)
        assert "raw.githubusercontent.com" in result
        assert "manifest.json" in result


class TestValidateManifest:
    """Test manifest validation."""

    def test_valid_manifest(self):
        errors = validate_manifest_data(SAMPLE_MANIFEST)
        assert errors == []

    def test_missing_problems(self):
        data = {"active_campaign": "Test"}
        errors = validate_manifest_data(data)
        assert errors == []  # empty problems list is valid

    def test_problem_missing_id(self):
        data = {"priority_problems": [{"path": "test.lean"}]}
        errors = validate_manifest_data(data)
        assert any("missing 'id'" in e for e in errors)

    def test_problem_missing_path(self):
        data = {"priority_problems": [{"id": "P001"}]}
        errors = validate_manifest_data(data)
        assert any("missing 'path'" in e for e in errors)

    def test_not_a_dict(self):
        errors = validate_manifest_data([1, 2, 3])
        assert any("must be a JSON object" in e for e in errors)

    def test_problems_not_a_list(self):
        data = {"priority_problems": "not a list"}
        errors = validate_manifest_data(data)
        assert any("must be a list" in e for e in errors)


class TestParseManifest:
    """Test manifest parsing."""

    def test_parse_full_manifest(self):
        manifest = parse_manifest(SAMPLE_MANIFEST, source="test")
        assert manifest.active_campaign == "Test_Q1"
        assert len(manifest.problems) == 2
        assert manifest.problems[0].id == "P001"
        assert manifest.problems[1].maintainer_note == "Use omega"
        assert manifest.repository_url == "https://github.com/test/repo"
        assert manifest.source == "test"

    def test_parse_minimal_manifest(self):
        data = {"priority_problems": [{"id": "X", "path": "x.lean"}]}
        manifest = parse_manifest(data)
        assert len(manifest.problems) == 1
        assert manifest.problems[0].difficulty == "Unknown"

    def test_problem_ids_property(self):
        manifest = parse_manifest(SAMPLE_MANIFEST)
        assert manifest.problem_ids == ["P001", "P002"]


class TestLoadLocalManifest:
    """Test local manifest loading."""

    def test_load_valid(self, tmp_path):
        path = tmp_path / "manifest.json"
        path.write_text(json.dumps(SAMPLE_MANIFEST))

        manifest = load_local_manifest(path)
        assert len(manifest.problems) == 2
        assert manifest.source == "local"

    def test_load_missing_file(self, tmp_path):
        with pytest.raises(ManifestError, match="not found"):
            load_local_manifest(tmp_path / "nope.json")

    def test_load_invalid_manifest(self, tmp_path):
        path = tmp_path / "manifest.json"
        path.write_text(json.dumps({"priority_problems": [{"no_id": True}]}))

        with pytest.raises(ManifestError, match="Invalid"):
            load_local_manifest(path)


class TestMergeManifests:
    """Test manifest merging."""

    def test_local_overrides_remote(self):
        remote = parse_manifest(SAMPLE_MANIFEST, source="remote")
        local_data = {
            "priority_problems": [
                {"id": "P001", "path": "problems/001.lean", "difficulty": "Medium",
                 "maintainer_note": "Local override"},
            ],
        }
        local = parse_manifest(local_data, source="local")

        merged = merge_manifests(remote, local)
        p001 = next(p for p in merged.problems if p.id == "P001")
        assert p001.difficulty == "Medium"
        assert p001.maintainer_note == "Local override"

    def test_local_adds_new_problems(self):
        remote = parse_manifest(SAMPLE_MANIFEST, source="remote")
        local_data = {
            "priority_problems": [
                {"id": "LOCAL1", "path": "local/001.lean"},
            ],
        }
        local = parse_manifest(local_data, source="local")

        merged = merge_manifests(remote, local)
        ids = [p.id for p in merged.problems]
        assert "P001" in ids
        assert "P002" in ids
        assert "LOCAL1" in ids

    def test_banned_tactics_merged(self):
        remote = parse_manifest(SAMPLE_MANIFEST, source="remote")
        local_data = {"priority_problems": [], "banned_tactics": ["native_decide"]}
        local = parse_manifest(local_data, source="local")

        merged = merge_manifests(remote, local)
        assert "sorry" in merged.banned_tactics
        assert "native_decide" in merged.banned_tactics

    def test_merged_source(self):
        remote = parse_manifest(SAMPLE_MANIFEST, source="remote")
        local = parse_manifest({"priority_problems": []}, source="local")
        merged = merge_manifests(remote, local)
        assert merged.source == "merged"


class TestCacheFreshness:
    """Test cache TTL logic."""

    def test_fresh_cache(self, tmp_path):
        meta_file = tmp_path / "meta.json"
        meta_file.write_text(json.dumps({"fetched_at": time.time()}))
        assert _is_cache_fresh(meta_file, ttl_seconds=3600)

    def test_stale_cache(self, tmp_path):
        meta_file = tmp_path / "meta.json"
        meta_file.write_text(json.dumps({"fetched_at": time.time() - 7200}))
        assert not _is_cache_fresh(meta_file, ttl_seconds=3600)

    def test_no_cache(self, tmp_path):
        assert not _is_cache_fresh(tmp_path / "nonexistent.json", ttl_seconds=3600)

    def test_corrupted_cache(self, tmp_path):
        meta_file = tmp_path / "meta.json"
        meta_file.write_text("not json")
        assert not _is_cache_fresh(meta_file, ttl_seconds=3600)


class TestFetchManifest:
    """Test remote manifest fetching with caching."""

    @patch("src.manifest._fetch_json")
    def test_fetch_and_cache(self, mock_fetch, tmp_path):
        mock_fetch.return_value = SAMPLE_MANIFEST
        manifest = fetch_manifest(
            "https://github.com/test/repo",
            cache_dir=tmp_path,
            force_refresh=True,
        )
        assert manifest.source == "remote"
        assert len(manifest.problems) == 2
        # Cache files should exist
        assert (tmp_path / "manifest_cache.json").exists()
        assert (tmp_path / "manifest_meta.json").exists()

    @patch("src.manifest._fetch_json")
    def test_uses_fresh_cache(self, mock_fetch, tmp_path):
        # Pre-seed cache
        cache_file = tmp_path / "manifest_cache.json"
        meta_file = tmp_path / "manifest_meta.json"
        _save_cache(cache_file, meta_file, SAMPLE_MANIFEST, "https://test")

        manifest = fetch_manifest(
            "https://github.com/test/repo",
            cache_dir=tmp_path,
            ttl_seconds=3600,
        )
        assert manifest.source == "cache"
        mock_fetch.assert_not_called()

    @patch("src.manifest._fetch_json")
    def test_offline_fallback(self, mock_fetch, tmp_path):
        mock_fetch.side_effect = Exception("Network error")

        # Pre-seed stale cache
        cache_file = tmp_path / "manifest_cache.json"
        meta_file = tmp_path / "manifest_meta.json"
        _save_cache(cache_file, meta_file, SAMPLE_MANIFEST, "https://test")
        # Make cache stale
        meta = {"fetched_at": time.time() - 99999, "url": "https://test"}
        meta_file.write_text(json.dumps(meta))

        manifest = fetch_manifest(
            "https://github.com/test/repo",
            cache_dir=tmp_path,
            ttl_seconds=3600,
        )
        assert manifest.source == "cache"

    @patch("src.manifest._fetch_json")
    def test_no_cache_no_network_raises(self, mock_fetch, tmp_path):
        mock_fetch.side_effect = Exception("Network error")

        with pytest.raises(ManifestError, match="Cannot fetch"):
            fetch_manifest(
                "https://github.com/test/repo",
                cache_dir=tmp_path,
            )

    @patch("src.manifest._fetch_json")
    def test_invalid_remote_manifest_raises(self, mock_fetch, tmp_path):
        mock_fetch.return_value = {"priority_problems": [{"no_id": True}]}

        with pytest.raises(ManifestError, match="Invalid"):
            fetch_manifest(
                "https://github.com/test/repo",
                cache_dir=tmp_path,
                force_refresh=True,
            )
