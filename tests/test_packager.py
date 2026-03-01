"""Tests for the packager module."""

import json
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock

from src.packager import (
    package_artifact,
    list_solutions,
    get_solution,
    extract_solution,
    _load_index,
    _save_index,
)


def _make_artifact(problem_id="test-01", attempts=3):
    """Create a mock ProofArtifact for testing."""
    critique = MagicMock()
    critique.status = "PASS"
    critique.feedback = "Clean proof, well structured."
    critique.is_elegant = True
    critique.security_concerns = []

    artifact = MagicMock()
    artifact.problem_id = problem_id
    artifact.proof_content = "theorem test : 1 + 1 = 2 := by rfl"
    artifact.build_logs = "Build succeeded.\nlean: no errors"
    artifact.critique = critique
    artifact.timestamp = datetime(2026, 2, 28, 12, 0, 0)
    artifact.attempts = attempts
    return artifact


class TestPackageArtifact:
    """Test ZIP packaging."""

    def test_creates_zip_file(self, tmp_path):
        artifact = _make_artifact()
        zip_path = package_artifact(artifact, output_dir=tmp_path)

        assert zip_path.exists()
        assert zip_path.suffix == ".zip"
        assert "test-01" in zip_path.name

    def test_zip_contains_all_files(self, tmp_path):
        artifact = _make_artifact()
        zip_path = package_artifact(artifact, output_dir=tmp_path)

        with zipfile.ZipFile(zip_path, "r") as zf:
            names = zf.namelist()
            prefix = "solution_test-01/"
            assert f"{prefix}proof.lean" in names
            assert f"{prefix}build_log.txt" in names
            assert f"{prefix}critique.json" in names
            assert f"{prefix}metadata.json" in names

    def test_proof_content_matches(self, tmp_path):
        artifact = _make_artifact()
        zip_path = package_artifact(artifact, output_dir=tmp_path)

        with zipfile.ZipFile(zip_path, "r") as zf:
            proof = zf.read("solution_test-01/proof.lean").decode("utf-8")
            assert proof == "theorem test : 1 + 1 = 2 := by rfl"

    def test_metadata_fields(self, tmp_path):
        artifact = _make_artifact()
        zip_path = package_artifact(
            artifact, output_dir=tmp_path, model_name="gemini-3-flash", cost_usd=0.05
        )

        with zipfile.ZipFile(zip_path, "r") as zf:
            meta = json.loads(zf.read("solution_test-01/metadata.json"))

        assert meta["problem_id"] == "test-01"
        assert meta["attempts"] == 3
        assert meta["model"] == "gemini-3-flash"
        assert meta["cost_usd"] == 0.05
        assert "theorem_hash" in meta
        assert len(meta["theorem_hash"]) == 64  # SHA-256

    def test_critique_json(self, tmp_path):
        artifact = _make_artifact()
        zip_path = package_artifact(artifact, output_dir=tmp_path)

        with zipfile.ZipFile(zip_path, "r") as zf:
            crit = json.loads(zf.read("solution_test-01/critique.json"))

        assert crit["status"] == "PASS"
        assert crit["is_elegant"] is True
        assert crit["feedback"] == "Clean proof, well structured."

    def test_updates_index(self, tmp_path):
        artifact = _make_artifact()
        package_artifact(artifact, output_dir=tmp_path)

        index = _load_index(tmp_path)
        assert len(index) == 1
        assert index[0]["problem_id"] == "test-01"

    def test_multiple_packages_append_index(self, tmp_path):
        a1 = _make_artifact("prob-01")
        a2 = _make_artifact("prob-02")
        package_artifact(a1, output_dir=tmp_path)
        package_artifact(a2, output_dir=tmp_path)

        index = _load_index(tmp_path)
        assert len(index) == 2
        ids = {e["problem_id"] for e in index}
        assert ids == {"prob-01", "prob-02"}


class TestListSolutions:
    """Test solution listing."""

    def test_empty_list(self, tmp_path):
        solutions = list_solutions(output_dir=tmp_path)
        assert solutions == []

    def test_lists_solutions_newest_first(self, tmp_path):
        a1 = _make_artifact("prob-01")
        a1.timestamp = datetime(2026, 1, 1, 0, 0, 0)
        a2 = _make_artifact("prob-02")
        a2.timestamp = datetime(2026, 2, 1, 0, 0, 0)

        package_artifact(a1, output_dir=tmp_path)
        package_artifact(a2, output_dir=tmp_path)

        solutions = list_solutions(output_dir=tmp_path)
        assert solutions[0]["problem_id"] == "prob-02"
        assert solutions[1]["problem_id"] == "prob-01"


class TestGetSolution:
    """Test solution retrieval."""

    def test_returns_none_for_missing(self, tmp_path):
        result = get_solution("nonexistent", output_dir=tmp_path)
        assert result is None

    def test_returns_solution(self, tmp_path):
        artifact = _make_artifact("prob-01")
        package_artifact(artifact, output_dir=tmp_path)

        result = get_solution("prob-01", output_dir=tmp_path)
        assert result is not None
        assert result["problem_id"] == "prob-01"


class TestExtractSolution:
    """Test solution extraction."""

    def test_extracts_to_directory(self, tmp_path):
        artifact = _make_artifact("prob-01")
        package_artifact(artifact, output_dir=tmp_path)

        extract_dir = tmp_path / "extracted"
        extract_dir.mkdir()
        result = extract_solution("prob-01", extract_to=extract_dir, output_dir=tmp_path)

        assert result is not None
        assert (result / "proof.lean").exists()
        assert (result / "metadata.json").exists()

    def test_returns_none_for_missing(self, tmp_path):
        result = extract_solution("nonexistent", output_dir=tmp_path)
        assert result is None


class TestIndex:
    """Test index persistence."""

    def test_save_and_load_roundtrip(self, tmp_path):
        data = [{"problem_id": "test", "timestamp": "2026-01-01T00:00:00"}]
        _save_index(tmp_path, data)
        loaded = _load_index(tmp_path)
        assert loaded == data

    def test_load_empty_returns_list(self, tmp_path):
        loaded = _load_index(tmp_path)
        assert loaded == []
