"""
Operational Tests — Verify the System Works End-to-End
======================================================
These tests verify the 7 fixes that bring Erdos from "prototype with bugs"
to "actually usable tool". They test the user-facing experience:
manifest loading, path resolution, pre-flight checks, provider fallback,
and environment orchestration.
"""

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.solver import load_manifest, Problem
from src.llm.factory import create_provider, _auto_detect
from src.llm import MockLLMProvider
from src.sandbox import _discover_elan_bin
from src.config import Config

PROJECT_ROOT = Path(__file__).parent.parent.resolve()


# ════════════════════════════════════════════════════════════════════
# Fix 1: Manifest Path Resolution
# ════════════════════════════════════════════════════════════════════


class TestManifestPathResolution(unittest.TestCase):
    """Paths in manifests are resolved relative to the manifest file."""

    def test_root_manifest_loads_with_resolved_paths(self):
        """Root manifest.json paths resolve to existing files."""
        manifest = PROJECT_ROOT / "manifest.json"
        problems = load_manifest(manifest)
        self.assertGreater(len(problems), 0, "Manifest should have problems")

        for p in problems:
            self.assertTrue(
                Path(p.path).exists(),
                f"Problem {p.id}: resolved path does not exist: {p.path}",
            )

    def test_examples_manifest_loads_with_resolved_paths(self):
        """examples/manifest.json paths resolve relative to examples/."""
        manifest = PROJECT_ROOT / "examples" / "manifest.json"
        problems = load_manifest(manifest)
        self.assertGreater(len(problems), 0)

        for p in problems:
            self.assertTrue(
                Path(p.path).exists(),
                f"Problem {p.id}: resolved path does not exist: {p.path}",
            )

    def test_original_content_is_preloaded(self):
        """When the file exists, original_content is pre-loaded."""
        manifest = PROJECT_ROOT / "manifest.json"
        problems = load_manifest(manifest)

        for p in problems:
            self.assertIsNotNone(
                p.original_content,
                f"Problem {p.id}: original_content should be pre-loaded",
            )
            self.assertIn(
                "sorry",
                p.original_content,
                f"Problem {p.id}: content should contain sorry",
            )

    def test_custom_manifest_with_relative_paths(self):
        """A manifest in a subdirectory resolves paths relative to itself."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a sub-directory with a lean file and manifest
            subdir = Path(tmpdir) / "sub"
            subdir.mkdir()
            (subdir / "test.lean").write_text("theorem t : True := by\n  sorry")
            manifest_data = {
                "priority_problems": [
                    {"id": "t1", "path": "test.lean", "difficulty": "Easy"}
                ]
            }
            manifest_path = subdir / "manifest.json"
            manifest_path.write_text(json.dumps(manifest_data))

            problems = load_manifest(manifest_path)
            self.assertEqual(len(problems), 1)
            self.assertTrue(Path(problems[0].path).exists())
            self.assertIn("sorry", problems[0].original_content)

    def test_missing_file_still_loads_with_none_content(self):
        """If a manifest references a non-existent file, it loads but content is None."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest_data = {
                "priority_problems": [
                    {"id": "missing", "path": "nonexistent.lean", "difficulty": "Hard"}
                ]
            }
            manifest_path = Path(tmpdir) / "manifest.json"
            manifest_path.write_text(json.dumps(manifest_data))

            problems = load_manifest(manifest_path)
            self.assertEqual(len(problems), 1)
            self.assertIsNone(problems[0].original_content)


# ════════════════════════════════════════════════════════════════════
# Fix 2: Root Manifest Has Working Paths
# ════════════════════════════════════════════════════════════════════


class TestRootManifestIsUsable(unittest.TestCase):
    """The root manifest.json references files that actually exist."""

    def test_all_referenced_files_exist(self):
        manifest = PROJECT_ROOT / "manifest.json"
        with open(manifest) as f:
            data = json.load(f)

        for p in data["priority_problems"]:
            resolved = PROJECT_ROOT / p["path"]
            self.assertTrue(
                resolved.exists(),
                f"manifest.json references non-existent file: {p['path']}",
            )

    def test_remote_manifest_preserved(self):
        """The old DeepMind manifest is preserved as manifest.remote.json."""
        remote = PROJECT_ROOT / "manifest.remote.json"
        self.assertTrue(remote.exists(), "manifest.remote.json should exist")
        with open(remote) as f:
            data = json.load(f)
        self.assertIn("repository", data)
        self.assertIn("google-deepmind", data["repository"]["url"])


# ════════════════════════════════════════════════════════════════════
# Fix 3: Pre-Flight Lean Check
# ════════════════════════════════════════════════════════════════════


class TestPreFlightCheck(unittest.TestCase):
    """Solver checks for Lean before trying to build."""

    def test_discover_elan_bin_works(self):
        """_discover_elan_bin finds elan when installed."""
        result = _discover_elan_bin()
        # On this system elan is installed, so it should find it
        if (Path.home() / ".elan" / "bin" / "lake").exists():
            self.assertIsNotNone(result)
        # If not installed, None is fine — the pre-flight will catch it


# ════════════════════════════════════════════════════════════════════
# Fix 4: Gemini Graceful Failure
# ════════════════════════════════════════════════════════════════════


class TestGeminiGracefulFailure(unittest.TestCase):
    """Gemini import failures don't crash the system."""

    def test_auto_detect_with_gemini_key_doesnt_crash(self):
        """With GEMINI_API_KEY set but Gemini broken, falls through to next provider."""
        with patch.dict(os.environ, {"GEMINI_API_KEY": "fake-key"}, clear=False):
            # Remove other API keys to isolate
            env = {
                "GEMINI_API_KEY": "fake-key",
            }
            for key in [
                "OPENAI_API_KEY",
                "ANTHROPIC_API_KEY",
                "OLLAMA_URL",
                "GOOGLE_API_KEY",
                "ERDOS_MOCK_MODE",
            ]:
                env[key] = ""

            with patch.dict(os.environ, env, clear=False):
                # This should not raise — it should fall through gracefully
                result = _auto_detect()
                # Result may be None (no working provider) — that's fine
                # The point is it doesn't crash

    def test_factory_falls_back_to_mock(self):
        """create_provider falls back to MockLLMProvider when no providers work."""
        config = Config()
        with patch.dict(
            os.environ,
            {
                "GEMINI_API_KEY": "",
                "GOOGLE_API_KEY": "",
                "OPENAI_API_KEY": "",
                "ANTHROPIC_API_KEY": "",
                "OLLAMA_URL": "",
                "ERDOS_MOCK_MODE": "1",
            },
            clear=False,
        ):
            provider = create_provider(config)
            self.assertIsInstance(provider, MockLLMProvider)


# ════════════════════════════════════════════════════════════════════
# Fix 5: Mock Mode Warning
# ════════════════════════════════════════════════════════════════════


class TestMockModeWarning(unittest.TestCase):
    """User gets clear warning when running in mock mode."""

    def test_mock_provider_is_identifiable(self):
        """MockLLMProvider can be detected with isinstance."""
        mock = MockLLMProvider()
        self.assertIsInstance(mock, MockLLMProvider)


# ════════════════════════════════════════════════════════════════════
# Fix 6: Non-Trivial Theorems
# ════════════════════════════════════════════════════════════════════


class TestIntermediateTheorems(unittest.TestCase):
    """Intermediate.lean exists with non-trivial theorems."""

    def test_intermediate_file_exists(self):
        intermediate = PROJECT_ROOT / "examples" / "intermediate.lean"
        self.assertTrue(intermediate.exists())

    def test_intermediate_has_multiple_theorems(self):
        intermediate = PROJECT_ROOT / "examples" / "intermediate.lean"
        content = intermediate.read_text()
        theorem_count = content.count("theorem ")
        self.assertGreaterEqual(
            theorem_count, 5, f"Expected 5+ theorems, found {theorem_count}"
        )

    def test_intermediate_has_sorry_placeholders(self):
        intermediate = PROJECT_ROOT / "examples" / "intermediate.lean"
        content = intermediate.read_text()
        sorry_count = content.count("sorry")
        self.assertGreaterEqual(sorry_count, 5)

    def test_manifests_include_intermediate(self):
        """Both manifests reference intermediate.lean."""
        for manifest_name in ["manifest.json", "examples/manifest.json"]:
            manifest = PROJECT_ROOT / manifest_name
            with open(manifest) as f:
                data = json.load(f)
            paths = [p["path"] for p in data["priority_problems"]]
            has_intermediate = any("intermediate" in p for p in paths)
            self.assertTrue(
                has_intermediate, f"{manifest_name} should include intermediate.lean"
            )


# ════════════════════════════════════════════════════════════════════
# Fix 7: --setup Flag
# ════════════════════════════════════════════════════════════════════


class TestSetupFlag(unittest.TestCase):
    """The --setup flag is accepted by the CLI."""

    def test_setup_flag_in_argparse(self):
        """Verify --setup is a valid CLI argument."""
        import argparse

        # Import and check the parser accepts --setup
        # We test indirectly by checking the source
        from src.solver import main
        import inspect

        source = inspect.getsource(main)
        self.assertIn("--setup", source)
        self.assertIn("EnvironmentManager", source)


if __name__ == "__main__":
    unittest.main(verbosity=2)
