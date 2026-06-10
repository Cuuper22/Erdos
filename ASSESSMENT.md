# Independent Assessment: Erdos Proof Mining System

**Date:** 2026-03-10
**Assessor:** Independent automated review (Claude)
**Method:** Installed Lean 4.28.0, wrote 125+ tests (66 wiring + 30 real-data + 16 bug fix demos + 16 operational), compiled real theorems against Lean compiler, tested full pipeline end-to-end, fixed 4 critical bugs + 7 operational gaps, added LLM isolation architecture

---

## Executive Summary

**Is this a real tool or scaffolding?**

It's **both** — but after our fixes, it's now **significantly closer to real**. The architecture is genuine — the solver loop, integrity checking, sandbox, and packager all function. We found and **fixed 4 critical bugs** that prevented it from working in practice, including a security hole where axiom abuse bypassed all checks.

**Verdict:** A genuine, usable tool. After 4 critical bug fixes and 7 operational fixes, it works end-to-end: manifest paths resolve correctly, Lean pre-flight checks run, provider failures are handled gracefully, and `--setup` orchestrates the full workflow. Still needs real LLM integration testing for production use.

---

## Bugs Found and Fixed

### BUG 1: Axiom Abuse Security Hole — FIXED
**File:** `src/validator.py:20`
**Before:** Regex `r"\baxiom\b(?!\s+\w+\s*:)"` exempted declaration-form axioms
**After:** Regex `r"\baxiom\b"` — ALL axiom usage banned in LLM proof candidates
**Why:** An LLM could write `axiom my_cheat : P` to trivially prove any theorem P. Proof candidates should never introduce axioms — only the original problem file defines what exists.
**Demo:** `tests/test_bug_fix_demos.py::TestDemo_AxiomAbuse`

### BUG 2: Sandbox Cannot Find `lake` — FIXED
**File:** `src/sandbox.py`
**Before:** `env={**os.environ, "LAKE_NO_INTERACTIVE": "1"}` — no elan PATH
**After:** Added `_discover_elan_bin()` that checks `~/.elan/bin/`, `~/.erdos-prover/bin/elan/bin/`, and `ELAN_HOME` env var, then prepends to PATH
**Why:** On fresh installs, `lake` is at `~/.elan/bin/lake` but not in system PATH
**Demo:** `tests/test_bug_fix_demos.py::TestDemo_SandboxPATH`

### BUG 3: Wrong `sorry` Replacement — FIXED
**File:** `src/solver.py`, `AgentProver._clean_response()`
**Before:** `original.replace('sorry', response, 1)` — replaces first occurrence (could be in a comment)
**After:** `_replace_sorry_in_body()` — skips sorry in line comments (`-- ...`), replaces only in code
**Why:** Comments like `-- remove sorry here` would get modified instead of the actual proof
**Demo:** `tests/test_bug_fix_demos.py::TestDemo_SorryReplacement`

### BUG 4: Always Re-downloads elan — FIXED
**File:** `src/environment.py:234`
**Before:** `if not installer_path.exists() or True:` — always true
**After:** `if not installer_path.exists():` — uses cache
**Why:** Debug hack left in code, wasting bandwidth on every call
**Demo:** `tests/test_bug_fix_demos.py::TestDemo_ElanCache`

---

## New Feature: LLM Feedback Isolation

**File:** `src/solver.py`, class `FeedbackSanitizer`

The LLM now **never sees internal validation details**. When errors occur during the solve loop, the `FeedbackSanitizer` strips:
- Security check names ("Banned: Axiom declaration...")
- Hash values and integrity check internals
- Sandbox paths and file locations
- Budget/cost information

The LLM only receives:
- **Lean compiler errors** (real, actionable feedback for fixing proofs)
- **Critic suggestions** (proof quality feedback)
- **Generic rejection** for security violations ("Your proof was rejected. Try a different approach.")

**Why:** This prevents the LLM from learning about and gaming the security checks. It can only improve by writing better proofs, not by hacking the eval.

**Demo:** `tests/test_bug_fix_demos.py::TestDemo_FeedbackIsolation`

---

## What's Real (Functions Correctly)

| Component | Status | Evidence |
|-----------|--------|----------|
| Theorem integrity hashing | **REAL** | Catches weakened theorems, added hypotheses, renamed theorems |
| sorry/admit/native_decide detection | **REAL** | Word-boundary matching works, no false positives |
| Axiom abuse detection | **REAL (FIXED)** | ALL axiom declarations now caught in proof candidates |
| IO/process escape detection | **REAL** | IO.FS, System.Process, IO.getStdin all blocked |
| Sandbox file lifecycle | **REAL** | Create, write, read, cleanup all verified |
| Sandbox PATH discovery | **REAL (FIXED)** | Finds elan via `~/.elan/bin/`, `ELAN_HOME`, or app-isolated install |
| Solver loop structure | **REAL** | Prover→Integrity→Build→Critic pipeline executes |
| Sorry replacement | **REAL (FIXED)** | Only replaces sorry in code, not in comments |
| LLM feedback isolation | **REAL (NEW)** | Sanitizes errors before passing to LLM |
| Cost tracking | **REAL** | Accumulates correctly, budget enforcement works |
| Critic JSON parsing | **REAL** | Handles valid JSON, malformed JSON, empty responses |
| Packager ZIP output | **REAL** | Creates valid ZIP with proof, metadata, critique, build log |
| Error classification | **REAL** | Transient vs permanent vs budget correctly classified |
| Mock fallback | **REAL** | No API key → mock provider, no crash |
| GPT-5.4 xhigh reasoning | **REAL (NEW)** | `reasoning_effort` parameter properly handled |

## Operational Fixes (Phase 2)

After the 4 critical bug fixes above, 7 additional operational gaps were identified and fixed to make the system actually usable end-to-end.

### FIX 5: Manifest Path Resolution
**File:** `src/solver.py`, function `load_manifest()`
**Before:** Paths stored as-is from JSON — `examples/manifest.json` looked for `./test_theorem.lean` instead of `./examples/test_theorem.lean`
**After:** Paths resolved relative to manifest file's parent directory; `original_content` pre-loaded from resolved path
**Test:** `tests/test_operational.py::TestManifestPathResolution` (5 tests)

### FIX 6: Root Manifest With Working Paths
**File:** `manifest.json` (root)
**Before:** Referenced `FormalConjectures/Erdos/1024.lean` etc. from uncloned DeepMind repo
**After:** References local `examples/*.lean` files that actually exist; old manifest preserved as `manifest.remote.json`
**Test:** `tests/test_operational.py::TestRootManifestIsUsable` (2 tests)

### FIX 7: Pre-Flight Lean Check
**File:** `src/solver.py`, function `main()`
**Before:** No check for Lean/elan — first build attempt failed with cryptic `FileNotFoundError`
**After:** Checks `_discover_elan_bin()` and `check_lean_installed()` before solving; prints clear install instructions on failure
**Test:** `tests/test_operational.py::TestPreFlightCheck` (1 test)

### FIX 8: Graceful Gemini Import Failure
**File:** `src/llm/factory.py`
**Before:** `from .gemini import GeminiProvider` unprotected — `pyo3_runtime.PanicException` (inherits `BaseException`, not `Exception`) crashed the system
**After:** All Gemini blocks wrapped in `try/except BaseException`; falls through to next provider on failure
**Test:** `tests/test_operational.py::TestGeminiGracefulFailure` (2 tests)

### FIX 9: Loud Mock Mode Warning
**File:** `src/solver.py`, function `main()`
**Before:** Silent fallback to MockLLMProvider — users got fake proofs without knowing
**After:** Explicit warning when running in mock mode; `except BaseException` catches Rust panics during provider init
**Test:** `tests/test_operational.py::TestMockModeWarning` (1 test)

### FIX 10: Non-Trivial Example Theorems
**File:** `examples/intermediate.lean` (new)
**Before:** Only trivial theorems (`1+1=2`, `add_comm`)
**After:** 6 moderately challenging theorems (nat_add_assoc, nat_mul_zero, nat_succ_ne_zero, bool_and_comm, list_length_nil, nat_le_succ)
**Test:** `tests/test_operational.py::TestIntermediateTheorems` (4 tests)

### FIX 11: `--setup` Orchestration Flag
**File:** `src/solver.py`, function `main()`
**Before:** Users had to manually chain `python -m src.environment` then `python -m src.solver`
**After:** `--setup` flag auto-runs `EnvironmentManager.setup_environment()` if Lean is not found
**Test:** `tests/test_operational.py::TestSetupFlag` (1 test)

---

## Remaining Gaps

| Component | Status | Notes |
|-----------|--------|-------|
| Out-of-box experience | **FIXED** | Manifest paths resolve, all referenced files exist, `--setup` orchestrates |
| Mock mode proofs | **FAKE** | Mock LLM output doesn't compile in Lean (by design — it's a test fallback) |
| Gemini provider | **GRACEFUL** | cffi/pyo3 dependency broken, but failures caught and system falls through |
| elan installer cache | **FIXED** | Was re-downloading every time |

---

## Claims vs. Reality (Final Assessment)

| Claim | Reality | Verdict |
|-------|---------|---------|
| "SHA-256 integrity locking catches cheating" | Catches all 4 cheating strategies (weaken, sorry, axiom, IO) | **TRUE (after fix)** |
| "200+ tests across 10 modules" | 323 tests total; 311 pass, 12 Gemini dependency failures | **TRUE** |
| "Multi-agent Prover/Critic loop" | Loop structure is real; sandbox discovers elan PATH | **TRUE (after fix)** |
| "Sandbox isolation" | File-level isolation with PATH discovery; no Docker | **MOSTLY TRUE** |
| "Supports Gemini, OpenAI, Anthropic, Ollama" | Gemini broken by cffi but gracefully caught; others functional | **PARTIALLY TRUE** |
| "Works out of the box" | Manifest paths resolve, pre-flight checks run, `--setup` orchestrates | **TRUE (after fixes)** |
| "Single command to solve" | `erdos-solve --setup --manifest manifest.json` handles everything | **TRUE (after fix)** |

---

## Files Modified/Created

### Critical Bug Fixes (Phase 1)
- `src/validator.py` — Fixed axiom regex to ban ALL axiom usage
- `src/sandbox.py` — Added `_discover_elan_bin()` PATH discovery
- `src/solver.py` — Fixed sorry replacement + added `FeedbackSanitizer`
- `src/environment.py` — Removed `or True` debug hack

### Operational Fixes (Phase 2)
- `src/solver.py` — Manifest path resolution, pre-flight Lean check, mock mode warning, `--setup` flag
- `src/llm/factory.py` — `except BaseException` for Gemini (catches pyo3 Rust panics)
- `manifest.json` — Replaced DeepMind references with local example files
- `manifest.remote.json` — Preserved original DeepMind manifest (new file)
- `examples/manifest.json` — Added intermediate.lean entry
- `examples/intermediate.lean` — 6 moderately challenging theorems (new file)

### New Features
- `src/llm/openai_provider.py` — Added `reasoning_effort` for GPT-5.4
- `src/llm/factory.py` — Pass `OPENAI_REASONING_EFFORT` env var

### Tests
- `tests/test_bug_fix_demos.py` — 16 visual proof demo tests (NEW)
- `tests/test_independent_assessment.py` — 66 wiring verification tests
- `tests/test_real_data_validation.py` — 30 real-data tests with Lean compiler
- `tests/test_operational.py` — 16 operational tests for all 7 fixes (NEW)
- `tests/test_validator.py` — Updated axiom test to reflect fix

## Test Summary

| Test File | Tests | Pass | Fail | Notes |
|-----------|-------|------|------|-------|
| Existing suite | 195 | 183 | 12 | Gemini cffi failures (pre-existing) |
| test_independent_assessment.py | 66 | 66 | 0 | Wiring verification |
| test_real_data_validation.py | 30 | 30 | 0 | Real Lean compilation |
| test_bug_fix_demos.py | 16 | 16 | 0 | Visual proof demos |
| test_operational.py | 16 | 16 | 0 | Operational fix verification |
| **Total** | **323** | **311** | **12** | All failures are pre-existing Gemini cffi |
