# Independent Assessment: Erdos Proof Mining System

**Date:** 2026-03-10
**Assessor:** Independent automated review (Claude)
**Method:** Installed Lean 4.28.0, wrote 96 tests (66 wiring + 30 real-data), compiled real theorems against Lean compiler, tested full pipeline end-to-end

---

## Executive Summary

**Is this a real tool or scaffolding?**

It's **both**. The architecture is real — the solver loop, integrity checking, sandbox, and packager all function. But the system has **critical bugs that prevent it from working in practice**, and its central security claim (catching all cheating) has a **gaping hole**: axiom abuse is not caught.

**Verdict:** A genuine prototype with real ideas, but NOT production-ready. The wiring works, the individual modules function, but the system cannot produce a valid proof end-to-end without manual PATH configuration, and its security guarantees are weaker than claimed.

---

## Real-Data Testing (with Lean 4.28.0 Compiler)

We installed Lean 4.28.0 and `lake` 5.0.0, created a real Lean project, wrote real theorems with `sorry` placeholders, and tested whether the Erdos system can produce proofs that **actually compile**.

### What We Tested

| Test | Result | Verdict |
|------|--------|---------|
| Real Lean proof compiles | `rfl` proves `1+1=2` | WORKS |
| Multi-theorem file compiles | `simp`, `omega`, `⟨trivial, trivial⟩` | WORKS |
| Sorry proof compiles (with warning) | Lean accepts sorry as placeholder | WORKS |
| Erdos `run_lake_build()` invokes Lean | Only if `lake` is in PATH | PARTIAL |
| Full pipeline: correct proof → artifact | Reaches integrity check, passes | WORKS |
| Full pipeline: cheating proofs caught | 3 of 4 strategies caught | **BUG** |
| Mock LLM output compiles | Does NOT compile | EXPECTED |
| Solver loop calls prover | Prover is called | WORKS |

---

## Critical Bugs Found

### BUG 1: Axiom Abuse NOT Caught (SECURITY HOLE)
**File:** `src/validator.py:20`
```python
(re.compile(r"\baxiom\b(?!\s+\w+\s*:)"), "Axiom usage (non-declaration)"),
```
The regex allows `axiom my_cheat : 1 + 1 = 2` because it matches the declaration pattern. An LLM can introduce:
```lean
axiom my_cheat : 1 + 1 = 2
theorem one_plus_one : 1 + 1 = 2 := my_cheat
```
This passes ALL checks: integrity (theorem statement unchanged), security (axiom looks like a declaration), and compilation (Lean accepts it). **The proof is logically invalid** — it assumes what it's trying to prove.

**Impact:** An LLM can cheat on ANY theorem by introducing a custom axiom. This completely undermines the project's central security claim.

### BUG 2: Sandbox Cannot Find `lake` on Fresh Install
**File:** `src/sandbox.py:169-176`
```python
result = subprocess.run(
    cmd, cwd=work_dir, capture_output=True, text=True,
    timeout=timeout_seconds,
    env={**os.environ, "LAKE_NO_INTERACTIVE": "1"}
)
```
`run_lake_build()` inherits the current PATH but doesn't add `~/.elan/bin/`. Even after `erdos-env --install` installs elan, the sandbox cannot find `lake` unless the user manually sets PATH. The `environment.py` module manages elan PATH via `EnvironmentManager.get_env()`, but `sandbox.py` never calls it.

**Impact:** The system cannot compile anything on a fresh installation.

### BUG 3: `_clean_response` Replaces Wrong `sorry`
**File:** `src/solver.py:184`
```python
if 'sorry' in original:
    return original.replace('sorry', response.strip(), 1)
```
`str.replace('sorry', ..., 1)` replaces the FIRST occurrence. If a comment contains "sorry" (e.g., `-- remove sorry here`), the comment gets modified instead of the actual proof body.

**Impact:** Proofs may still contain sorry after "replacement" if comments mention sorry.

### BUG 4: `or True` in environment.py (Line 234)
**File:** `src/environment.py:234`
```python
if not installer_path.exists() or True:
```
Unconditionally re-downloads the elan installer every time.

### BUG 5: OpenAI Provider Retries Permanent Errors
401/403 errors are retried `max_retries` times before giving up, wasting API calls.

---

## What's Real (Functions Correctly)

| Component | Status | Evidence |
|-----------|--------|----------|
| Theorem integrity hashing | **REAL** | Catches weakened theorems, added hypotheses, renamed theorems |
| sorry/admit/native_decide detection | **REAL** | Word-boundary matching works, no false positives |
| IO/process escape detection | **REAL** | IO.FS, System.Process, IO.getStdin all blocked |
| Sandbox file lifecycle | **REAL** | Create, write, read, cleanup all verified |
| Solver loop structure | **REAL** | Prover→Integrity→Build→Critic pipeline executes |
| Cost tracking | **REAL** | Accumulates correctly, budget enforcement works |
| Critic JSON parsing | **REAL** | Handles valid JSON, malformed JSON, empty responses |
| Packager ZIP output | **REAL** | Creates valid ZIP with proof, metadata, critique, build log |
| Error classification | **REAL** | Transient vs permanent vs budget correctly classified |
| Mock fallback | **REAL** | No API key → mock provider, no crash |
| Real Lean compilation | **REAL** | `run_lake_build()` invokes `lake build` (if PATH set) |

## What's Scaffolding (Looks Real But Doesn't Work)

| Component | Status | Evidence |
|-----------|--------|----------|
| Axiom security check | **BROKEN** | Custom axioms completely bypass all checks |
| Out-of-box experience | **BROKEN** | Manifest references non-existent files |
| Sandbox↔Environment integration | **MISSING** | Sandbox can't find Lean without manual PATH |
| Mock mode proofs | **FAKE** | Mock LLM output doesn't compile in Lean |
| `_clean_response` with comments | **BUGGY** | Replaces wrong sorry occurrence |
| GPT-5.4 support (original) | **MISSING** | Fixed in this assessment |

---

## Claims vs. Reality (Updated)

| Claim | Reality | Verdict |
|-------|---------|---------|
| "SHA-256 integrity locking catches cheating" | Catches 3 of 4 cheating strategies; axiom abuse bypasses it | **PARTIALLY TRUE** |
| "200+ tests across 10 modules" | 195 tests, 183 pass; existing tests test mocks, not real behavior | **OVERSTATED** |
| "Multi-agent Prover/Critic loop" | Loop structure is real, but never reaches Critic without Lean in PATH | **PARTIALLY TRUE** |
| "Sandbox isolation" | File-level isolation only; no PATH management, no Docker | **OVERSTATED** |
| "Supports Gemini, OpenAI, Anthropic, Ollama" | Gemini broken by cffi; OpenAI had no reasoning support | **PARTIALLY TRUE** |

---

## The Bottom Line

This is a **real but unfinished prototype**. The individual components (validator, sandbox, solver, packager) all have genuine functionality. The architecture is sound. The idea of SHA-256 integrity locking is genuinely novel for LLM proof generation.

But it cannot run end-to-end without significant manual setup, its central security claim has a critical hole (axiom abuse), and the existing test suite (195 tests) primarily validates mock behavior rather than actual Lean compilation.

**For this to be a real tool, it needs:**
1. Fix the axiom detection to ban ALL axiom declarations in proofs (not just non-declaration usage)
2. Integrate environment.py PATH management with sandbox.py
3. Fix `_clean_response` to only replace sorry in proof bodies
4. Add real Lean compilation tests (like the ones in this assessment)

---

## Files Modified/Created

- `src/llm/openai_provider.py` — Added `reasoning_effort` for GPT-5.4
- `src/llm/factory.py` — Pass `OPENAI_REASONING_EFFORT` env var
- `tests/test_independent_assessment.py` — 66 wiring verification tests
- `tests/test_real_data_validation.py` — 30 real-data tests with Lean compiler
- `ASSESSMENT.md` — This report

## Test Summary

| Test File | Tests | Pass | Fail | Notes |
|-----------|-------|------|------|-------|
| Existing suite | 195 | 183 | 12 | Gemini cffi failures |
| test_independent_assessment.py | 66 | 66 | 0 | Wiring verification |
| test_real_data_validation.py | 30 | 30 | 0 | Real Lean compilation |
| **Total** | **291** | **279** | **12** | |
