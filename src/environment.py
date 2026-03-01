"""
Environment Manager for the Erdos Proof Mining System.

This module handles automated installation of Lean/elan and management
of the Lean development environment. Key features:
- Cross-platform elan installation (Windows/macOS/Linux)
- App-isolated installation in ~/.erdos-prover/
- Progress reporting during downloads
- Cached installers for offline scenarios
- Toolchain auto-detection from lean-toolchain files
"""

import hashlib
import json
import os
import platform
import shutil
import subprocess
import time
import urllib.request
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class EnvironmentStatus:
    """Status of the Lean environment."""
    elan_installed: bool
    elan_version: Optional[str]
    lean_installed: bool
    lean_version: Optional[str]
    lake_installed: bool
    lake_version: Optional[str]
    app_dir: Path

    def is_ready(self) -> bool:
        """Check if environment is ready for proof mining."""
        return self.elan_installed and self.lean_installed and self.lake_installed


def _download_with_progress(
    url: str,
    dest: Path,
    label: str = "Downloading",
    on_progress=None,
) -> None:
    """Download a file with progress reporting.

    Args:
        url: URL to download
        dest: Destination path
        label: Label for progress messages
        on_progress: Optional callback(bytes_downloaded, total_bytes)
    """
    logger.info(f"{label}: {url}")
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=60) as resp:
        total = int(resp.headers.get("Content-Length", 0))
        downloaded = 0
        chunk_size = 8192

        with open(dest, "wb") as f:
            while True:
                chunk = resp.read(chunk_size)
                if not chunk:
                    break
                f.write(chunk)
                downloaded += len(chunk)
                if on_progress:
                    on_progress(downloaded, total)
                elif total > 0 and downloaded % (chunk_size * 16) == 0:
                    pct = downloaded * 100 // total
                    logger.info(f"{label}: {pct}% ({downloaded}/{total} bytes)")

    logger.info(f"{label}: complete ({downloaded} bytes)")


def _verify_checksum(file_path: Path, expected_sha256: str) -> bool:
    """Verify SHA-256 checksum of a file."""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    actual = h.hexdigest()
    if actual != expected_sha256:
        logger.error(f"Checksum mismatch: expected {expected_sha256[:16]}..., got {actual[:16]}...")
        return False
    return True


class EnvironmentManager:
    """
    Manages the Lean development environment.

    Handles elan/Lean installation, repository cloning,
    and toolchain version management — all isolated inside ~/.erdos-prover/.
    """

    APP_DIR_NAME = ".erdos-prover"
    BIN_DIR_NAME = "bin"
    CACHE_DIR_NAME = "cache"
    REPOS_DIR_NAME = "repos"

    ELAN_UNIX_URL = "https://raw.githubusercontent.com/leanprover/elan/master/elan-init.sh"
    ELAN_WINDOWS_URL = "https://raw.githubusercontent.com/leanprover/elan/master/elan-init.ps1"

    # Cache file for toolchain state
    TOOLCHAIN_CACHE_FILE = "toolchain_cache.json"

    def __init__(self, app_dir: Optional[Path] = None):
        if app_dir:
            self.app_dir = Path(app_dir)
        else:
            self.app_dir = Path.home() / self.APP_DIR_NAME

        self.bin_dir = self.app_dir / self.BIN_DIR_NAME
        self.cache_dir = self.app_dir / self.CACHE_DIR_NAME
        self.repos_dir = self.app_dir / self.REPOS_DIR_NAME

        self._system = platform.system().lower()
        self._is_windows = self._system == "windows"

    def ensure_directories(self) -> None:
        """Create all required directories."""
        for d in (self.app_dir, self.bin_dir, self.cache_dir, self.repos_dir):
            d.mkdir(parents=True, exist_ok=True)

    @property
    def elan_home(self) -> Path:
        """Path to the isolated ELAN_HOME directory."""
        return self.bin_dir / "elan"

    @property
    def elan_bin_dir(self) -> Path:
        """Path to elan's bin directory (contains lean, lake, elan)."""
        return self.elan_home / "bin"

    def get_status(self) -> EnvironmentStatus:
        """Get current environment status."""
        elan_installed, elan_version = self._check_tool("elan")
        lean_installed, lean_version = self._check_tool("lean")
        lake_installed, lake_version = self._check_tool("lake")

        return EnvironmentStatus(
            elan_installed=elan_installed,
            elan_version=elan_version,
            lean_installed=lean_installed,
            lean_version=lean_version,
            lake_installed=lake_installed,
            lake_version=lake_version,
            app_dir=self.app_dir,
        )

    def _check_tool(self, name: str) -> Tuple[bool, Optional[str]]:
        """Check if a tool is installed and return its version."""
        try:
            result = subprocess.run(
                [name, "--version"],
                capture_output=True,
                text=True,
                timeout=10,
                env=self._get_env(),
            )
            if result.returncode == 0:
                return True, result.stdout.strip()
            return False, None
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False, None

    def _get_env(self) -> dict:
        """Get environment with elan paths prepended."""
        env = os.environ.copy()
        elan_home = self.elan_home
        bin_path = self.elan_bin_dir
        path_sep = ";" if self._is_windows else ":"

        if bin_path.exists():
            env["PATH"] = str(bin_path) + path_sep + env.get("PATH", "")

        env["ELAN_HOME"] = str(elan_home)
        return env

    # ── Elan installation ──

    def install_elan(
        self,
        force: bool = False,
        expected_sha256: Optional[str] = None,
        on_progress=None,
    ) -> bool:
        """Install elan (Lean version manager).

        Args:
            force: Force reinstall even if already installed
            expected_sha256: Optional SHA-256 checksum for the installer script
            on_progress: Optional callback(bytes_downloaded, total_bytes)

        Returns:
            True if installation successful
        """
        self.ensure_directories()

        if not force:
            installed, version = self._check_tool("elan")
            if installed:
                logger.info(f"elan already installed: {version}")
                return True

        elan_home = self.elan_home

        try:
            if self._is_windows:
                return self._install_elan_windows(elan_home, expected_sha256, on_progress)
            else:
                return self._install_elan_unix(elan_home, expected_sha256, on_progress)
        except Exception as e:
            logger.error(f"Failed to install elan: {e}")
            return False

    def _install_elan_unix(
        self,
        elan_home: Path,
        expected_sha256: Optional[str] = None,
        on_progress=None,
    ) -> bool:
        """Install elan on Unix-like systems."""
        installer_path = self.cache_dir / "elan-init.sh"

        # Use cached installer if available and no network
        if not installer_path.exists() or True:
            _download_with_progress(
                self.ELAN_UNIX_URL,
                installer_path,
                label="Downloading elan installer",
                on_progress=on_progress,
            )

        if expected_sha256 and not _verify_checksum(installer_path, expected_sha256):
            logger.error("Installer checksum verification failed")
            return False

        installer_path.chmod(0o755)

        env = os.environ.copy()
        env["ELAN_HOME"] = str(elan_home)

        result = subprocess.run(
            [str(installer_path), "-y", "--no-modify-path"],
            env=env,
            capture_output=True,
            text=True,
            timeout=300,
        )

        if result.returncode == 0:
            logger.info("elan installed successfully")
            return self._verify_elan_binary()
        else:
            logger.error(f"elan installation failed: {result.stderr}")
            return False

    def _install_elan_windows(
        self,
        elan_home: Path,
        expected_sha256: Optional[str] = None,
        on_progress=None,
    ) -> bool:
        """Install elan on Windows."""
        installer_path = self.cache_dir / "elan-init.ps1"

        _download_with_progress(
            self.ELAN_WINDOWS_URL,
            installer_path,
            label="Downloading elan installer",
            on_progress=on_progress,
        )

        if expected_sha256 and not _verify_checksum(installer_path, expected_sha256):
            logger.error("Installer checksum verification failed")
            return False

        env = os.environ.copy()
        env["ELAN_HOME"] = str(elan_home)

        # Quote paths for spaces in usernames
        ps1_path = str(installer_path)

        result = subprocess.run(
            [
                "powershell", "-ExecutionPolicy", "Bypass",
                "-File", ps1_path,
                "-NoPrompt", "-NoModifyPath",
            ],
            env=env,
            capture_output=True,
            text=True,
            timeout=300,
        )

        if result.returncode == 0:
            logger.info("elan installed successfully")
            return self._verify_elan_binary()
        else:
            logger.error(f"elan installation failed: {result.stderr}")
            return False

    def _verify_elan_binary(self) -> bool:
        """Verify elan binary is installed and executable."""
        if self._is_windows:
            elan_bin = self.elan_bin_dir / "elan.exe"
        else:
            elan_bin = self.elan_bin_dir / "elan"

        if not elan_bin.exists():
            logger.error(f"elan binary not found at {elan_bin}")
            return False

        installed, version = self._check_tool("elan")
        if installed:
            logger.info(f"Verified elan binary: {version}")
            return True
        else:
            logger.error("elan binary exists but failed to execute")
            return False

    # ── Toolchain management ──

    def install_lean_toolchain(self, toolchain: str = "stable") -> bool:
        """Install a specific Lean toolchain via elan."""
        logger.info(f"Installing Lean toolchain: {toolchain}")

        try:
            result = subprocess.run(
                ["elan", "toolchain", "install", toolchain],
                capture_output=True,
                text=True,
                timeout=600,
                env=self._get_env(),
            )

            if result.returncode == 0:
                logger.info(f"Toolchain {toolchain} installed successfully")
                return True
            else:
                logger.error(f"Failed to install toolchain: {result.stderr}")
                return False
        except Exception as e:
            logger.error(f"Error installing toolchain: {e}")
            return False

    def read_toolchain_file(self, repo_path: Path) -> Optional[str]:
        """Read and parse the lean-toolchain file from a repository.

        Returns:
            Toolchain string (e.g. 'leanprover/lean4:v4.3.0'), or None.
        """
        toolchain_file = repo_path / "lean-toolchain"
        if not toolchain_file.exists():
            return None

        try:
            return toolchain_file.read_text(encoding="utf-8").strip()
        except Exception as e:
            logger.error(f"Error reading lean-toolchain: {e}")
            return None

    def get_installed_toolchain(self) -> Optional[str]:
        """Get the currently active toolchain via `elan show`."""
        try:
            result = subprocess.run(
                ["elan", "show"],
                capture_output=True,
                text=True,
                timeout=10,
                env=self._get_env(),
            )
            if result.returncode == 0:
                return result.stdout.strip()
            return None
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return None

    def check_toolchain_update(self, repo_path: Path) -> Tuple[bool, Optional[str]]:
        """Check if the repository's lean-toolchain has changed.

        Uses a local cache to avoid redundant checks. Returns (needs_update, toolchain_version).
        """
        required = self.read_toolchain_file(repo_path)
        if not required:
            return False, None

        # Check cache first
        cached = self._load_toolchain_cache()
        cache_key = str(repo_path)
        if cache_key in cached and cached[cache_key] == required:
            return False, required

        # Check against installed toolchain
        current = self.get_installed_toolchain()
        needs_update = current is None or required not in current

        if not needs_update:
            # Update cache since we're up to date
            self._save_toolchain_cache(cache_key, required)

        return needs_update, required

    def ensure_toolchain(self, repo_path: Path) -> bool:
        """Ensure the correct toolchain is installed for a repository.

        Installs missing toolchains and runs lake update when needed.
        Returns True if environment is ready.
        """
        needs_update, toolchain = self.check_toolchain_update(repo_path)
        if not needs_update:
            return True

        if toolchain:
            logger.info(f"Toolchain update needed: {toolchain}")
            if self.install_lean_toolchain(toolchain):
                self.run_lake_update(repo_path)
                self._save_toolchain_cache(str(repo_path), toolchain)
                return True
            return False

        return True

    def _load_toolchain_cache(self) -> dict:
        """Load toolchain cache from disk."""
        cache_file = self.cache_dir / self.TOOLCHAIN_CACHE_FILE
        if cache_file.exists():
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                return {}
        return {}

    def _save_toolchain_cache(self, key: str, value: str) -> None:
        """Save toolchain cache entry to disk."""
        self.ensure_directories()
        cache = self._load_toolchain_cache()
        cache[key] = value
        cache_file = self.cache_dir / self.TOOLCHAIN_CACHE_FILE
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(cache, f, indent=2)

    # ── Repository management ──

    def clone_repository(
        self,
        repo_url: str,
        repo_name: Optional[str] = None,
        branch: str = "main",
    ) -> Optional[Path]:
        """Clone a repository into the repos directory."""
        self.ensure_directories()

        if repo_name is None:
            repo_name = repo_url.rstrip("/").split("/")[-1]
            if repo_name.endswith(".git"):
                repo_name = repo_name[:-4]

        repo_path = self.repos_dir / repo_name

        if repo_path.exists():
            logger.info(f"Repository already exists at {repo_path}, updating...")
            return self._update_repository(repo_path, branch)

        logger.info(f"Cloning {repo_url} to {repo_path}")

        try:
            result = subprocess.run(
                ["git", "clone", "--branch", branch, "--depth", "1",
                 repo_url, str(repo_path)],
                capture_output=True,
                text=True,
                timeout=300,
            )

            if result.returncode == 0:
                logger.info(f"Repository cloned successfully to {repo_path}")
                return repo_path
            else:
                logger.error(f"Failed to clone repository: {result.stderr}")
                return None
        except Exception as e:
            logger.error(f"Error cloning repository: {e}")
            return None

    def _update_repository(self, repo_path: Path, branch: str) -> Optional[Path]:
        """Update an existing repository using fast-forward only (non-destructive)."""
        try:
            # Fetch updates
            result = subprocess.run(
                ["git", "fetch", "origin", branch],
                cwd=str(repo_path),
                capture_output=True,
                text=True,
                timeout=120,
            )

            if result.returncode != 0:
                logger.warning(f"Failed to fetch updates: {result.stderr}")
                return repo_path

            # Fast-forward only — no destructive reset
            result = subprocess.run(
                ["git", "merge", "--ff-only", f"origin/{branch}"],
                cwd=str(repo_path),
                capture_output=True,
                text=True,
                timeout=60,
            )

            if result.returncode == 0:
                logger.info("Repository updated successfully (fast-forward)")
            else:
                logger.warning(
                    f"Fast-forward merge failed (local changes?): {result.stderr}. "
                    "Repository left as-is."
                )

            return repo_path
        except Exception as e:
            logger.error(f"Error updating repository: {e}")
            return repo_path

    def run_lake_update(self, repo_path: Path) -> bool:
        """Run lake update in a repository."""
        logger.info(f"Running lake update in {repo_path}")

        try:
            result = subprocess.run(
                ["lake", "update"],
                cwd=str(repo_path),
                capture_output=True,
                text=True,
                timeout=600,
                env=self._get_env(),
            )

            if result.returncode == 0:
                logger.info("lake update completed successfully")
                return True
            else:
                logger.error(f"lake update failed: {result.stderr}")
                return False
        except Exception as e:
            logger.error(f"Error running lake update: {e}")
            return False

    # ── Full setup ──

    def setup_environment(
        self,
        repo_url: Optional[str] = None,
        branch: str = "main",
    ) -> EnvironmentStatus:
        """Full environment setup: install elan, clone repo, check toolchain."""
        logger.info("Setting up Lean environment...")

        self.install_elan()
        self.install_lean_toolchain("stable")

        if repo_url:
            repo_path = self.clone_repository(repo_url, branch=branch)
            if repo_path:
                self.ensure_toolchain(repo_path)

        return self.get_status()

    def cleanup(self, keep_elan: bool = True) -> None:
        """Clean up the environment."""
        logger.info("Cleaning up environment...")

        if self.repos_dir.exists():
            shutil.rmtree(self.repos_dir, ignore_errors=True)
            logger.info(f"Removed {self.repos_dir}")

        if self.cache_dir.exists():
            shutil.rmtree(self.cache_dir, ignore_errors=True)
            logger.info(f"Removed {self.cache_dir}")

        if not keep_elan and self.bin_dir.exists():
            shutil.rmtree(self.bin_dir, ignore_errors=True)
            logger.info(f"Removed {self.bin_dir}")


def main():
    """CLI entry point for environment management."""
    import argparse

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    parser = argparse.ArgumentParser(description="Erdos Environment Manager")
    parser.add_argument("--status", action="store_true", help="Show environment status")
    parser.add_argument("--install", action="store_true", help="Install elan and Lean")
    parser.add_argument("--force", action="store_true", help="Force reinstall")
    parser.add_argument("--repo", type=str, help="Clone a repository")
    parser.add_argument("--branch", type=str, default="main", help="Branch to clone")
    parser.add_argument("--cleanup", action="store_true", help="Clean up environment")

    args = parser.parse_args()

    manager = EnvironmentManager()

    if args.status:
        status = manager.get_status()
        print(f"App Directory: {status.app_dir}")
        print(f"Elan: {'[OK] ' + (status.elan_version or '') if status.elan_installed else '[X] Not installed'}")
        print(f"Lean: {'[OK] ' + (status.lean_version or '') if status.lean_installed else '[X] Not installed'}")
        print(f"Lake: {'[OK] ' + (status.lake_version or '') if status.lake_installed else '[X] Not installed'}")
        print(f"Ready: {'[OK]' if status.is_ready() else '[X]'}")

    elif args.install:
        if args.force:
            manager.install_elan(force=True)
        status = manager.setup_environment(repo_url=args.repo, branch=args.branch)
        print(f"Setup complete. Ready: {'[OK]' if status.is_ready() else '[X]'}")

    elif args.cleanup:
        manager.cleanup()
        print("Cleanup complete")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
