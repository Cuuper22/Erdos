"""
Environment Manager for the Erdos Proof Mining System.

This module handles automated installation of Lean/elan and management
of the Lean development environment.
"""

import os
import platform
import subprocess
import shutil
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple
import logging

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


class EnvironmentManager:
    """
    Manages the Lean development environment.
    
    This class handles:
    - Checking if elan/Lean is installed
    - Installing elan silently in a localized directory
    - Cloning and caching target repositories
    - Managing Lean toolchain versions
    """
    
    # Default app directory names
    APP_DIR_NAME = ".erdos-prover"
    BIN_DIR_NAME = "bin"
    CACHE_DIR_NAME = "cache"
    REPOS_DIR_NAME = "repos"
    
    # Elan installer URLs
    ELAN_UNIX_URL = "https://raw.githubusercontent.com/leanprover/elan/master/elan-init.sh"
    ELAN_WINDOWS_URL = "https://raw.githubusercontent.com/leanprover/elan/master/elan-init.ps1"
    
    def __init__(self, app_dir: Optional[Path] = None):
        """
        Initialize the environment manager.
        
        Args:
            app_dir: Custom app directory. Defaults to ~/.erdos-prover
        """
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
        self.app_dir.mkdir(parents=True, exist_ok=True)
        self.bin_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.repos_dir.mkdir(parents=True, exist_ok=True)
    
    def get_status(self) -> EnvironmentStatus:
        """Get current environment status."""
        elan_installed, elan_version = self._check_elan()
        lean_installed, lean_version = self._check_lean()
        lake_installed, lake_version = self._check_lake()
        
        return EnvironmentStatus(
            elan_installed=elan_installed,
            elan_version=elan_version,
            lean_installed=lean_installed,
            lean_version=lean_version,
            lake_installed=lake_installed,
            lake_version=lake_version,
            app_dir=self.app_dir
        )
    
    def _check_elan(self) -> Tuple[bool, Optional[str]]:
        """Check if elan is installed."""
        try:
            result = subprocess.run(
                ["elan", "--version"],
                capture_output=True,
                text=True,
                timeout=10,
                env=self._get_env()
            )
            if result.returncode == 0:
                return True, result.stdout.strip()
            return False, None
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False, None
    
    def _check_lean(self) -> Tuple[bool, Optional[str]]:
        """Check if Lean is installed."""
        try:
            result = subprocess.run(
                ["lean", "--version"],
                capture_output=True,
                text=True,
                timeout=10,
                env=self._get_env()
            )
            if result.returncode == 0:
                return True, result.stdout.strip()
            return False, None
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False, None
    
    def _check_lake(self) -> Tuple[bool, Optional[str]]:
        """Check if lake is installed."""
        try:
            result = subprocess.run(
                ["lake", "--version"],
                capture_output=True,
                text=True,
                timeout=10,
                env=self._get_env()
            )
            if result.returncode == 0:
                return True, result.stdout.strip()
            return False, None
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False, None
    
    def _get_env(self) -> dict:
        """Get environment with elan paths added."""
        env = os.environ.copy()
        elan_home = self.bin_dir / "elan"
        
        if self._is_windows:
            path_sep = ";"
            bin_path = elan_home / "bin"
        else:
            path_sep = ":"
            bin_path = elan_home / "bin"
        
        if bin_path.exists():
            env["PATH"] = str(bin_path) + path_sep + env.get("PATH", "")
        
        env["ELAN_HOME"] = str(elan_home)
        return env
    
    def install_elan(self, force: bool = False) -> bool:
        """
        Install elan (Lean version manager).
        
        Args:
            force: Force reinstall even if already installed
        
        Returns:
            True if installation successful
        """
        self.ensure_directories()
        
        # Check if already installed
        if not force:
            installed, _ = self._check_elan()
            if installed:
                logger.info("elan is already installed")
                return True
        
        logger.info("Installing elan...")
        
        elan_home = self.bin_dir / "elan"
        
        try:
            if self._is_windows:
                return self._install_elan_windows(elan_home)
            else:
                return self._install_elan_unix(elan_home)
        except Exception as e:
            logger.error(f"Failed to install elan: {e}")
            return False
    
    def _install_elan_unix(self, elan_home: Path) -> bool:
        """Install elan on Unix-like systems."""
        # Download installer
        installer_path = self.cache_dir / "elan-init.sh"
        
        logger.info(f"Downloading elan installer from {self.ELAN_UNIX_URL}")
        urllib.request.urlretrieve(self.ELAN_UNIX_URL, installer_path)
        
        # Make executable
        installer_path.chmod(0o755)
        
        # Run installer silently
        env = os.environ.copy()
        env["ELAN_HOME"] = str(elan_home)
        
        result = subprocess.run(
            [str(installer_path), "-y", "--no-modify-path"],
            env=env,
            capture_output=True,
            text=True,
            timeout=300
        )
        
        if result.returncode == 0:
            logger.info("elan installed successfully")
            return True
        else:
            logger.error(f"elan installation failed: {result.stderr}")
            return False
    
    def _install_elan_windows(self, elan_home: Path) -> bool:
        """Install elan on Windows."""
        # Download installer
        installer_path = self.cache_dir / "elan-init.ps1"
        
        logger.info(f"Downloading elan installer from {self.ELAN_WINDOWS_URL}")
        urllib.request.urlretrieve(self.ELAN_WINDOWS_URL, installer_path)
        
        # Run PowerShell installer
        env = os.environ.copy()
        env["ELAN_HOME"] = str(elan_home)
        
        result = subprocess.run(
            [
                "powershell", "-ExecutionPolicy", "Bypass",
                "-File", str(installer_path),
                "-NoPrompt", "-NoModifyPath"
            ],
            env=env,
            capture_output=True,
            text=True,
            timeout=300
        )
        
        if result.returncode == 0:
            logger.info("elan installed successfully")
            return True
        else:
            logger.error(f"elan installation failed: {result.stderr}")
            return False
    
    def install_lean_toolchain(self, toolchain: str = "stable") -> bool:
        """
        Install a specific Lean toolchain.
        
        Args:
            toolchain: Toolchain name (e.g., "stable", "leanprover/lean4:v4.3.0")
        
        Returns:
            True if installation successful
        """
        logger.info(f"Installing Lean toolchain: {toolchain}")
        
        try:
            result = subprocess.run(
                ["elan", "toolchain", "install", toolchain],
                capture_output=True,
                text=True,
                timeout=600,
                env=self._get_env()
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
    
    def clone_repository(
        self,
        repo_url: str,
        repo_name: Optional[str] = None,
        branch: str = "main"
    ) -> Optional[Path]:
        """
        Clone a repository into the repos directory.
        
        Args:
            repo_url: Git repository URL
            repo_name: Name for the local directory (derived from URL if not provided)
            branch: Branch to clone
        
        Returns:
            Path to cloned repository, or None if failed
        """
        self.ensure_directories()
        
        if repo_name is None:
            # Extract repo name from URL
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
                ["git", "clone", "--branch", branch, "--depth", "1", repo_url, str(repo_path)],
                capture_output=True,
                text=True,
                timeout=300
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
        """Update an existing repository."""
        try:
            # Fetch updates
            result = subprocess.run(
                ["git", "fetch", "origin", branch],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=120
            )
            
            if result.returncode != 0:
                logger.warning(f"Failed to fetch updates: {result.stderr}")
                return repo_path
            
            # Reset to origin
            result = subprocess.run(
                ["git", "reset", "--hard", f"origin/{branch}"],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                logger.info(f"Repository updated successfully")
            else:
                logger.warning(f"Failed to reset repository: {result.stderr}")
            
            return repo_path
        except Exception as e:
            logger.error(f"Error updating repository: {e}")
            return repo_path
    
    def check_toolchain_update(self, repo_path: Path) -> Tuple[bool, Optional[str]]:
        """
        Check if the repository's lean-toolchain has changed.
        
        Args:
            repo_path: Path to the repository
        
        Returns:
            Tuple of (needs_update, toolchain_version)
        """
        toolchain_file = repo_path / "lean-toolchain"
        
        if not toolchain_file.exists():
            return False, None
        
        try:
            toolchain = toolchain_file.read_text().strip()
            
            # Check current toolchain
            result = subprocess.run(
                ["elan", "show"],
                capture_output=True,
                text=True,
                timeout=10,
                env=self._get_env()
            )
            
            current = result.stdout.strip() if result.returncode == 0 else ""
            
            needs_update = toolchain not in current
            return needs_update, toolchain
        except Exception as e:
            logger.error(f"Error checking toolchain: {e}")
            return False, None
    
    def run_lake_update(self, repo_path: Path) -> bool:
        """
        Run lake update in a repository.
        
        Args:
            repo_path: Path to the repository
        
        Returns:
            True if successful
        """
        logger.info(f"Running lake update in {repo_path}")
        
        try:
            result = subprocess.run(
                ["lake", "update"],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=600,
                env=self._get_env()
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
    
    def setup_environment(self, repo_url: Optional[str] = None, branch: str = "main") -> EnvironmentStatus:
        """
        Full environment setup: install elan, clone repo, check toolchain.
        
        Args:
            repo_url: Optional repository URL to clone
            branch: Branch to clone
        
        Returns:
            Final environment status
        """
        logger.info("Setting up Lean environment...")
        
        # Step 1: Install elan
        self.install_elan()
        
        # Step 2: Install stable toolchain
        self.install_lean_toolchain("stable")
        
        # Step 3: Clone repository if specified
        if repo_url:
            repo_path = self.clone_repository(repo_url, branch=branch)
            
            if repo_path:
                # Step 4: Check and update toolchain
                needs_update, toolchain = self.check_toolchain_update(repo_path)
                
                if needs_update and toolchain:
                    logger.info(f"Installing required toolchain: {toolchain}")
                    self.install_lean_toolchain(toolchain)
                    self.run_lake_update(repo_path)
        
        return self.get_status()
    
    def cleanup(self, keep_elan: bool = True) -> None:
        """
        Clean up the environment.
        
        Args:
            keep_elan: If True, keep elan installation but remove repos/cache
        """
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
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    parser = argparse.ArgumentParser(description="Erdos Environment Manager")
    parser.add_argument("--status", action="store_true", help="Show environment status")
    parser.add_argument("--install", action="store_true", help="Install elan and Lean")
    parser.add_argument("--repo", type=str, help="Clone a repository")
    parser.add_argument("--branch", type=str, default="main", help="Branch to clone")
    parser.add_argument("--cleanup", action="store_true", help="Clean up environment")
    
    args = parser.parse_args()
    
    manager = EnvironmentManager()
    
    if args.status:
        status = manager.get_status()
        print(f"App Directory: {status.app_dir}")
        print(f"Elan: {'✓ ' + (status.elan_version or '') if status.elan_installed else '✗ Not installed'}")
        print(f"Lean: {'✓ ' + (status.lean_version or '') if status.lean_installed else '✗ Not installed'}")
        print(f"Lake: {'✓ ' + (status.lake_version or '') if status.lake_installed else '✗ Not installed'}")
        print(f"Ready: {'✓' if status.is_ready() else '✗'}")
    
    elif args.install:
        status = manager.setup_environment(repo_url=args.repo, branch=args.branch)
        print(f"Setup complete. Ready: {'✓' if status.is_ready() else '✗'}")
    
    elif args.cleanup:
        manager.cleanup()
        print("Cleanup complete")
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
