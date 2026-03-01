"""Tests for the environment manager module."""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

from src.environment import (
    EnvironmentManager,
    EnvironmentStatus,
    _download_with_progress,
    _verify_checksum,
)


class TestEnvironmentStatus:
    """Test EnvironmentStatus dataclass."""

    def test_is_ready_when_all_installed(self):
        status = EnvironmentStatus(
            elan_installed=True, elan_version="1.0",
            lean_installed=True, lean_version="4.3.0",
            lake_installed=True, lake_version="4.3.0",
            app_dir=Path("/tmp"),
        )
        assert status.is_ready()

    def test_not_ready_when_lean_missing(self):
        status = EnvironmentStatus(
            elan_installed=True, elan_version="1.0",
            lean_installed=False, lean_version=None,
            lake_installed=True, lake_version="4.3.0",
            app_dir=Path("/tmp"),
        )
        assert not status.is_ready()

    def test_not_ready_when_elan_missing(self):
        status = EnvironmentStatus(
            elan_installed=False, elan_version=None,
            lean_installed=False, lean_version=None,
            lake_installed=False, lake_version=None,
            app_dir=Path("/tmp"),
        )
        assert not status.is_ready()


class TestEnvironmentManager:
    """Test EnvironmentManager initialization and directories."""

    def test_default_app_dir(self):
        mgr = EnvironmentManager()
        assert mgr.app_dir == Path.home() / ".erdos-prover"

    def test_custom_app_dir(self, tmp_path):
        mgr = EnvironmentManager(app_dir=tmp_path / "custom")
        assert mgr.app_dir == tmp_path / "custom"

    def test_ensure_directories(self, tmp_path):
        mgr = EnvironmentManager(app_dir=tmp_path / "test_app")
        mgr.ensure_directories()
        assert mgr.app_dir.exists()
        assert mgr.bin_dir.exists()
        assert mgr.cache_dir.exists()
        assert mgr.repos_dir.exists()

    def test_elan_home_property(self, tmp_path):
        mgr = EnvironmentManager(app_dir=tmp_path)
        assert mgr.elan_home == tmp_path / "bin" / "elan"

    def test_elan_bin_dir_property(self, tmp_path):
        mgr = EnvironmentManager(app_dir=tmp_path)
        assert mgr.elan_bin_dir == tmp_path / "bin" / "elan" / "bin"

    def test_get_env_includes_elan_home(self, tmp_path):
        mgr = EnvironmentManager(app_dir=tmp_path)
        env = mgr._get_env()
        assert env["ELAN_HOME"] == str(mgr.elan_home)

    def test_get_env_prepends_bin_dir(self, tmp_path):
        mgr = EnvironmentManager(app_dir=tmp_path)
        mgr.ensure_directories()
        # Create the bin dir so it gets prepended
        mgr.elan_bin_dir.mkdir(parents=True, exist_ok=True)
        env = mgr._get_env()
        assert env["PATH"].startswith(str(mgr.elan_bin_dir))


class TestCheckTool:
    """Test tool checking."""

    def test_check_tool_not_found(self, tmp_path):
        mgr = EnvironmentManager(app_dir=tmp_path)
        installed, version = mgr._check_tool("nonexistent_tool_xyz")
        assert not installed
        assert version is None

    @patch("subprocess.run")
    def test_check_tool_found(self, mock_run, tmp_path):
        mock_run.return_value = MagicMock(returncode=0, stdout="elan 3.1.1\n")
        mgr = EnvironmentManager(app_dir=tmp_path)
        installed, version = mgr._check_tool("elan")
        assert installed
        assert "elan" in version


class TestToolchainManagement:
    """Test toolchain file reading and caching."""

    def test_read_toolchain_file(self, tmp_path):
        mgr = EnvironmentManager(app_dir=tmp_path)
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "lean-toolchain").write_text("leanprover/lean4:v4.3.0\n")

        result = mgr.read_toolchain_file(repo)
        assert result == "leanprover/lean4:v4.3.0"

    def test_read_toolchain_file_missing(self, tmp_path):
        mgr = EnvironmentManager(app_dir=tmp_path)
        result = mgr.read_toolchain_file(tmp_path)
        assert result is None

    def test_toolchain_cache_roundtrip(self, tmp_path):
        mgr = EnvironmentManager(app_dir=tmp_path)
        mgr.ensure_directories()

        mgr._save_toolchain_cache("/repo/path", "leanprover/lean4:v4.3.0")
        cache = mgr._load_toolchain_cache()
        assert cache["/repo/path"] == "leanprover/lean4:v4.3.0"

    def test_load_empty_cache(self, tmp_path):
        mgr = EnvironmentManager(app_dir=tmp_path)
        mgr.ensure_directories()
        cache = mgr._load_toolchain_cache()
        assert cache == {}

    @patch.object(EnvironmentManager, "get_installed_toolchain")
    def test_check_toolchain_update_needed(self, mock_show, tmp_path):
        mock_show.return_value = "leanprover/lean4:v4.2.0"
        mgr = EnvironmentManager(app_dir=tmp_path)
        mgr.ensure_directories()

        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "lean-toolchain").write_text("leanprover/lean4:v4.3.0\n")

        needs_update, toolchain = mgr.check_toolchain_update(repo)
        assert needs_update
        assert toolchain == "leanprover/lean4:v4.3.0"

    @patch.object(EnvironmentManager, "get_installed_toolchain")
    def test_check_toolchain_update_not_needed(self, mock_show, tmp_path):
        mock_show.return_value = "leanprover/lean4:v4.3.0 (default)"
        mgr = EnvironmentManager(app_dir=tmp_path)
        mgr.ensure_directories()

        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "lean-toolchain").write_text("leanprover/lean4:v4.3.0\n")

        needs_update, toolchain = mgr.check_toolchain_update(repo)
        assert not needs_update

    @patch.object(EnvironmentManager, "get_installed_toolchain")
    def test_check_toolchain_uses_cache(self, mock_show, tmp_path):
        mgr = EnvironmentManager(app_dir=tmp_path)
        mgr.ensure_directories()

        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "lean-toolchain").write_text("leanprover/lean4:v4.3.0\n")

        # Pre-seed cache
        mgr._save_toolchain_cache(str(repo), "leanprover/lean4:v4.3.0")

        needs_update, toolchain = mgr.check_toolchain_update(repo)
        assert not needs_update
        # get_installed_toolchain should NOT be called when cache hits
        mock_show.assert_not_called()


class TestRepoIntegrity:
    """Test repository integrity verification."""

    def test_valid_lean_repo(self, tmp_path):
        mgr = EnvironmentManager(app_dir=tmp_path)
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "lean-toolchain").write_text("leanprover/lean4:v4.3.0")
        (repo / "lakefile.lean").write_text("-- lakefile")

        assert mgr.verify_repo_integrity(repo)

    def test_missing_toolchain(self, tmp_path):
        mgr = EnvironmentManager(app_dir=tmp_path)
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "lakefile.lean").write_text("-- lakefile")

        assert not mgr.verify_repo_integrity(repo)

    def test_toml_lakefile_accepted(self, tmp_path):
        mgr = EnvironmentManager(app_dir=tmp_path)
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "lean-toolchain").write_text("leanprover/lean4:v4.3.0")
        (repo / "lakefile.toml").write_text("[package]")

        assert mgr.verify_repo_integrity(repo)


class TestCleanupOldRepos:
    """Test selective repo cleanup."""

    def test_cleanup_all(self, tmp_path):
        mgr = EnvironmentManager(app_dir=tmp_path)
        mgr.ensure_directories()
        (mgr.repos_dir / "repo1").mkdir()
        (mgr.repos_dir / "repo2").mkdir()

        removed = mgr.cleanup_old_repos()
        assert removed == 2
        assert not (mgr.repos_dir / "repo1").exists()

    def test_cleanup_keeps_specified(self, tmp_path):
        mgr = EnvironmentManager(app_dir=tmp_path)
        mgr.ensure_directories()
        (mgr.repos_dir / "keep_me").mkdir()
        (mgr.repos_dir / "remove_me").mkdir()

        removed = mgr.cleanup_old_repos(keep=["keep_me"])
        assert removed == 1
        assert (mgr.repos_dir / "keep_me").exists()
        assert not (mgr.repos_dir / "remove_me").exists()


class TestRepositoryUpdate:
    """Test repository update uses fast-forward instead of hard reset."""

    @patch("subprocess.run")
    def test_update_uses_ff_only(self, mock_run, tmp_path):
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        mgr = EnvironmentManager(app_dir=tmp_path)
        repo = tmp_path / "repo"
        repo.mkdir()

        mgr._update_repository(repo, "main")

        # Second call should be merge --ff-only, not reset --hard
        calls = mock_run.call_args_list
        assert len(calls) == 2
        merge_cmd = calls[1][0][0]
        assert "merge" in merge_cmd
        assert "--ff-only" in merge_cmd
        assert "--hard" not in str(calls)


class TestVerifyChecksum:
    """Test checksum verification."""

    def test_correct_checksum(self, tmp_path):
        test_file = tmp_path / "test.txt"
        test_file.write_bytes(b"hello world")

        import hashlib
        expected = hashlib.sha256(b"hello world").hexdigest()
        assert _verify_checksum(test_file, expected)

    def test_incorrect_checksum(self, tmp_path):
        test_file = tmp_path / "test.txt"
        test_file.write_bytes(b"hello world")

        assert not _verify_checksum(test_file, "0" * 64)


class TestCleanup:
    """Test environment cleanup."""

    def test_cleanup_removes_repos_and_cache(self, tmp_path):
        mgr = EnvironmentManager(app_dir=tmp_path)
        mgr.ensure_directories()

        # Create some files
        (mgr.repos_dir / "test_repo").mkdir()
        (mgr.cache_dir / "test_cache").mkdir()

        mgr.cleanup(keep_elan=True)

        assert not mgr.repos_dir.exists()
        assert not mgr.cache_dir.exists()
        assert mgr.bin_dir.exists()  # elan kept

    def test_cleanup_removes_elan(self, tmp_path):
        mgr = EnvironmentManager(app_dir=tmp_path)
        mgr.ensure_directories()

        mgr.cleanup(keep_elan=False)

        assert not mgr.bin_dir.exists()


class TestGetStatus:
    """Test environment status reporting."""

    @patch.object(EnvironmentManager, "_check_tool")
    def test_get_status_all_installed(self, mock_check, tmp_path):
        mock_check.side_effect = [
            (True, "elan 3.1.1"),
            (True, "lean 4.3.0"),
            (True, "lake 4.3.0"),
        ]
        mgr = EnvironmentManager(app_dir=tmp_path)
        status = mgr.get_status()

        assert status.elan_installed
        assert status.lean_installed
        assert status.lake_installed
        assert status.is_ready()

    @patch.object(EnvironmentManager, "_check_tool")
    def test_get_status_nothing_installed(self, mock_check, tmp_path):
        mock_check.return_value = (False, None)
        mgr = EnvironmentManager(app_dir=tmp_path)
        status = mgr.get_status()

        assert not status.elan_installed
        assert not status.is_ready()
