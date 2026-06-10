"""
Sandbox module for the Erdos Proof Mining System.

This module manages the Lean build process, creates isolated work environments,
and captures build output for error analysis.
"""

import os
import logging
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class BuildResult:
    """Result of a Lean build attempt."""

    success: bool
    stdout: str
    stderr: str
    return_code: int
    duration_seconds: float
    timeout_occurred: bool = False

    def get_error_summary(self) -> str:
        """Extract a concise error summary from the build output."""
        if self.success:
            return "Build successful"

        if self.timeout_occurred:
            return "Build timed out"

        # Parse stderr for Lean errors
        lines = self.stderr.split("\n")
        error_lines = []

        for line in lines:
            if "error:" in line.lower() or "Error:" in line:
                error_lines.append(line.strip())

        if error_lines:
            # Return first 5 errors
            return "\n".join(error_lines[:5])

        # Fallback to full stderr if no specific errors found
        return self.stderr[:1000] if self.stderr else "Unknown error"


@dataclass
class Sandbox:
    """
    Manages an isolated build environment for Lean proofs.

    The sandbox creates a temporary directory, copies necessary files,
    and runs the Lean build process in isolation.
    """

    base_dir: Path
    problem_id: str
    work_dir: Optional[Path] = None
    created_at: datetime = field(default_factory=datetime.now)

    def __post_init__(self):
        """Initialize the sandbox directory."""
        self.work_dir = (
            self.base_dir
            / f"sandbox_{self.problem_id}_{self.created_at.strftime('%Y%m%d_%H%M%S')}"
        )

    def create(self, source_dir: Optional[Path] = None) -> Path:
        """
        Create the sandbox environment.

        Args:
            source_dir: Optional source directory to copy from

        Returns:
            Path to the sandbox working directory
        """
        if self.work_dir is None:
            raise RuntimeError("Sandbox not initialized")

        self.work_dir.mkdir(parents=True, exist_ok=True)

        if source_dir and source_dir.exists():
            # Copy the source directory contents
            for item in source_dir.iterdir():
                if item.is_dir():
                    shutil.copytree(item, self.work_dir / item.name, dirs_exist_ok=True)
                else:
                    shutil.copy2(item, self.work_dir / item.name)

        # If no lakefile exists, initialize a minimal Lean project
        has_lakefile = any(
            (self.work_dir / name).exists()
            for name in ("lakefile.lean", "lakefile.toml", "lakefile")
        )
        if not has_lakefile:
            self._init_lean_project()

        return self.work_dir

    def _init_lean_project(self) -> None:
        """Initialize a minimal Lean 4 project in the sandbox."""
        lake_bin = _discover_elan_bin()
        lake_cmd = str(lake_bin / "lake") if lake_bin else "lake"

        try:
            result = subprocess.run(
                [lake_cmd, "init", "ErdosSandbox"],
                cwd=self.work_dir,
                capture_output=True,
                text=True,
                timeout=30,
                env=_elan_env(lake_bin),
            )
            if result.returncode != 0:
                logger.warning(f"lake init failed: {result.stderr[:200]}")
        except Exception as e:
            logger.warning(f"Could not initialize Lean project: {e}")

    def cleanup(self) -> None:
        """Remove the sandbox directory."""
        if self.work_dir and self.work_dir.exists():
            shutil.rmtree(self.work_dir, ignore_errors=True)

    def write_file(self, relative_path: str, content: str) -> Path:
        """
        Write a file to the sandbox.

        Args:
            relative_path: Path relative to the sandbox root
            content: File content to write

        Returns:
            Full path to the written file
        """
        if self.work_dir is None:
            raise RuntimeError("Sandbox not created")

        file_path = self.work_dir / relative_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")
        return file_path

    def read_file(self, relative_path: str) -> str:
        """
        Read a file from the sandbox.

        Args:
            relative_path: Path relative to the sandbox root

        Returns:
            File content
        """
        if self.work_dir is None:
            raise RuntimeError("Sandbox not created")

        file_path = self.work_dir / relative_path
        return file_path.read_text(encoding="utf-8")

    def __enter__(self) -> "Sandbox":
        """Context manager entry."""
        self.create()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit - cleanup sandbox."""
        self.cleanup()


def _discover_elan_bin() -> Optional[Path]:
    """Discover the elan bin directory containing lean/lake/elan binaries.

    Checks common locations and ELAN_HOME env var. Returns the first
    directory found that exists, or None.
    """
    candidates = []

    # 1. ELAN_HOME env var
    elan_home = os.environ.get("ELAN_HOME")
    if elan_home:
        candidates.append(Path(elan_home) / "bin")

    # 2. Default ~/.elan/bin/
    candidates.append(Path.home() / ".elan" / "bin")

    # 3. Erdos app-isolated install
    candidates.append(Path.home() / ".erdos-prover" / "bin" / "elan" / "bin")

    for candidate in candidates:
        if candidate.exists() and (candidate / "lake").exists():
            return candidate

    return None


def _elan_env(elan_bin: Optional[Path]) -> dict:
    """Build a subprocess environment for elan-proxied binaries.

    The proxies (lean/lake) resolve toolchains via ELAN_HOME, so when the
    discovered install lives outside the default ~/.elan (e.g. the
    app-isolated ~/.erdos-prover location), PATH alone is not enough —
    the proxy would look for toolchains in ~/.elan and fail.
    """
    env = os.environ.copy()
    if elan_bin:
        path_sep = ";" if os.name == "nt" else ":"
        env["PATH"] = str(elan_bin) + path_sep + env.get("PATH", "")
        env["ELAN_HOME"] = str(elan_bin.parent)
    return env


def run_lake_build(
    work_dir: Path, timeout_seconds: int = 60, target: Optional[str] = None
) -> BuildResult:
    """
    Run 'lake build' in the specified directory.

    Args:
        work_dir: Working directory containing the Lean project
        timeout_seconds: Maximum time to wait for the build
        target: Optional specific build target

    Returns:
        BuildResult with the build outcome
    """
    import time

    start_time = time.time()

    cmd = ["lake", "build"]
    if target:
        cmd.append(target)

    # Discover elan bin directory; PATH and ELAN_HOME must both point at it
    env = _elan_env(_discover_elan_bin())
    env["LAKE_NO_INTERACTIVE"] = "1"

    try:
        result = subprocess.run(
            cmd,
            cwd=work_dir,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            env=env,
        )

        duration = time.time() - start_time

        return BuildResult(
            success=result.returncode == 0,
            stdout=result.stdout,
            stderr=result.stderr,
            return_code=result.returncode,
            duration_seconds=duration,
            timeout_occurred=False,
        )

    except subprocess.TimeoutExpired as e:
        duration = time.time() - start_time
        return BuildResult(
            success=False,
            stdout=e.stdout or "",
            stderr=e.stderr or "Build timed out",
            return_code=-1,
            duration_seconds=duration,
            timeout_occurred=True,
        )

    except FileNotFoundError:
        return BuildResult(
            success=False,
            stdout="",
            stderr="lake command not found. Is Lean/elan installed?",
            return_code=-1,
            duration_seconds=0,
            timeout_occurred=False,
        )

    except Exception as e:
        duration = time.time() - start_time
        return BuildResult(
            success=False,
            stdout="",
            stderr=str(e),
            return_code=-1,
            duration_seconds=duration,
            timeout_occurred=False,
        )


def check_lean_installed() -> tuple[bool, str]:
    """
    Check if Lean/elan is installed and accessible.

    Returns:
        Tuple of (is_installed, version_or_error)
    """
    try:
        result = subprocess.run(
            ["lean", "--version"], capture_output=True, text=True, timeout=10
        )

        if result.returncode == 0:
            return True, result.stdout.strip()
        else:
            return False, result.stderr.strip()

    except FileNotFoundError:
        return False, "lean command not found"

    except subprocess.TimeoutExpired:
        return False, "lean --version timed out"

    except Exception as e:
        return False, str(e)


def check_elan_installed() -> tuple[bool, str]:
    """
    Check if elan (Lean version manager) is installed.

    Returns:
        Tuple of (is_installed, version_or_error)
    """
    try:
        result = subprocess.run(
            ["elan", "--version"], capture_output=True, text=True, timeout=10
        )

        if result.returncode == 0:
            return True, result.stdout.strip()
        else:
            return False, result.stderr.strip()

    except FileNotFoundError:
        return False, "elan command not found"

    except subprocess.TimeoutExpired:
        return False, "elan --version timed out"

    except Exception as e:
        return False, str(e)


class SandboxManager:
    """
    Manages multiple sandboxes for different proof attempts.

    This class handles creation, tracking, and cleanup of sandbox
    environments used during proof mining.
    """

    def __init__(self, base_dir: Path):
        """
        Initialize the sandbox manager.

        Args:
            base_dir: Base directory for all sandboxes
        """
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._active_sandboxes: dict[str, Sandbox] = {}

    def create_sandbox(
        self, problem_id: str, source_dir: Optional[Path] = None
    ) -> Sandbox:
        """
        Create a new sandbox for a problem.

        Args:
            problem_id: Unique identifier for the problem
            source_dir: Optional source directory to copy from

        Returns:
            The created Sandbox
        """
        sandbox = Sandbox(base_dir=self.base_dir, problem_id=problem_id)
        sandbox.create(source_dir)
        self._active_sandboxes[problem_id] = sandbox
        return sandbox

    def get_sandbox(self, problem_id: str) -> Optional[Sandbox]:
        """Get an existing sandbox by problem ID."""
        return self._active_sandboxes.get(problem_id)

    def cleanup_sandbox(self, problem_id: str) -> None:
        """Clean up a specific sandbox."""
        if problem_id in self._active_sandboxes:
            self._active_sandboxes[problem_id].cleanup()
            del self._active_sandboxes[problem_id]

    def cleanup_all(self) -> None:
        """Clean up all active sandboxes."""
        for sandbox in self._active_sandboxes.values():
            sandbox.cleanup()
        self._active_sandboxes.clear()

    def __enter__(self) -> "SandboxManager":
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit - cleanup all sandboxes."""
        self.cleanup_all()
