# Independent Assessment: Erdos Proof Mining System

**Date:** 2026-03-10
**Assessor:** Independent automated review (Claude)
**Method:** Cloned repo, installed from scratch, wrote 66 independent tests, attempted real API integration

---

## Executive Summary

The Erdos project is a **well-architected but incomplete** proof mining system. Its core integrity-locking mechanism (SHA-256 theorem hashing) **works as claimed** and is genuinely novel. However, the project has significant gaps between its promises and its operational reality: it cannot run end-to-end out of the box, critical modules have zero test coverage, and it doesn't support modern reasoning models like GPT-5.4.

**Verdict:** Solid foundation with real ideas, but not production-ready. The "200+ tests" claim is slightly overstated, and the tests that exist heavily test periphery while leaving the core (solver, sandbox) undertested.

---

## What Actually Works

### 1. Theorem Integrity Locking (VERIFIED)
The central claim — SHA-256 hashing catches agents that modify theorem statements — **is true**. Our independent tests confirm:
- Subtle modifications (e.g., `1+1=2` → `1+1=3`) are detected
- Theorem renaming is detected
- Adding extra hypotheses is detected
- Weakening conclusions is detected
- Whitespace normalization works correctly
- Multi-line theorem extraction works
- The `TheoremLocker` class correctly locks and verifies

**This is the project's genuine contribution.** The idea of hashing theorem statements before the LLM loop to prevent specification gaming is sound and well-implemented.

### 2. Security Scanner (VERIFIED)
The banned pattern detection works correctly:
- `sorry`, `admit`, `native_decide` properly caught with word-boundary matching
- `sorry` inside other words (e.g., `notsorryatall`) correctly NOT flagged
- `axiom` in declaration context correctly NOT flagged
- IO/process/filesystem access patterns properly blocked
- Clean proofs pass without false positives

### 3. Sandbox Module (VERIFIED — was previously untested)
The sandbox lifecycle works:
- Create, write, read, cleanup all function correctly
- Context manager support works
- Subdirectory creation works
- Graceful failure when `lake` not installed (returns error, doesn't crash)

### 4. Config System (VERIFIED)
- Environment variable loading works
- Mock mode fallback works
- Budget tracking and enforcement works
- JSON round-trip serialization works

### 5. Error Classification (VERIFIED)
- Transient errors (429, 503, rate limits) correctly classified for retry
- Permanent errors (401, 403, auth failures) correctly classified
- Budget exhaustion correctly classified

### 6. Critic JSON Parsing (VERIFIED)
- Valid JSON parsed correctly
- JSON with surrounding text (typical LLM output) handled
- Malformed JSON falls back to heuristic
- Nested braces handled correctly
- Empty responses don't crash

---

## What Doesn't Work

### 1. Cannot Run End-to-End Out of the Box
The manifest references files from `google-deepmind/formal-conjectures` but the repository is not cloned. Running `erdos-solve --manifest manifest.json` in mock mode produces:
```
Problem file not found: FormalConjectures/Erdos/1024.lean
Problem file not found: FormalConjectures/Erdos/0042.lean
Problem file not found: FormalConjectures/Erdos/0007.lean
```
**0 problems solved, 0 cost spent.** The system needs `erdos-env --repo` first, but this isn't documented in any quick-start guide.

### 2. No GPT-5.4 Support (Fixed in this assessment)
The OpenAI provider used `temperature` with all models, which is incompatible with GPT-5.4's `reasoning_effort` parameter. We added support for the `reasoning_effort` parameter:
- When `reasoning_effort` is set (and not "none"), `temperature` is omitted
- Valid values: `none`, `low`, `medium`, `high`, `xhigh`
- Factory passes through `OPENAI_REASONING_EFFORT` env var

**Note:** The provided API key returned 401 Unauthorized, so we could not verify the actual API call succeeds. The SDK accepted the `reasoning_effort` parameter without error (unlike the initial `reasoning` dict attempt).

### 3. Provider Retries 401 Errors
The `OpenAIProvider._is_transient()` correctly identifies 401 as non-transient, BUT the retry loop structure means it still makes `max_retries + 1` attempts before the transient check kicks in on the *next* iteration. The first attempt fails, the loop continues, and each subsequent attempt also fails with 401 — wasting API calls on a permanent error. The solver's `_classify_error` handles this correctly at a higher level, but the provider itself doesn't short-circuit.

---

## Bugs Found

### Bug 1: `or True` in environment.py (Line 234)
```python
if not installer_path.exists() or True:
    _download_with_progress(...)
```
This unconditionally re-downloads the elan installer every time, ignoring any cached version. Should be:
```python
if not installer_path.exists():
```

### Bug 2: Provider Retry on Permanent Errors
The OpenAI provider retries 401/403 errors up to `max_retries` times before giving up. The `_is_transient` check works, but the retry loop's structure means the first failure always continues to the next iteration before breaking.

---

## Claims vs. Reality

| Claim | Reality | Verdict |
|-------|---------|---------|
| "200+ tests across 10 modules" | 195 tests collected, 183 pass (12 Gemini failures from env issue) | Slightly overstated |
| "SHA-256 integrity locking catches cheating" | Independently verified — works correctly | TRUE |
| "Multi-agent Prover/Critic loop" | Code exists and structure is sound, but cannot run without external Lean project | PARTIALLY TRUE |
| "Supports Gemini, OpenAI, Anthropic, Ollama" | Factory and providers exist; Gemini tests fail due to cffi dependency; OpenAI didn't support reasoning models (fixed) | PARTIALLY TRUE |
| "Sandbox isolation" | Works for file I/O; no actual process isolation (no Docker, no chroot) | OVERSTATED |
| "Desktop app shipped" | Tauri GUI code exists but not tested in this assessment | UNVERIFIED |
| "Single-person project" | Consistent code style suggests single author | PLAUSIBLE |

---

## Test Coverage Gaps

| Module | Lines | Tests Before | Tests After | Critical? |
|--------|-------|-------------|-------------|-----------|
| sandbox.py | 340 | 0 | 16 (new) | YES — core build system |
| solver.py | 677 | 7 (mocks only) | 22 (new) | YES — main orchestration |
| validator.py | 238 | 42 | 55 (13 new) | No — already well-tested |
| environment.py | 400+ | 31 | 32 (1 bug test) | Contains confirmed bug |
| llm/openai_provider.py | 146 | 10 | 15 (5 new) | Now tested with reasoning |

---

## Genuine Contributions

1. **Theorem integrity hashing** — A practical approach to detecting specification gaming in LLM-generated proofs. Simple, effective, and well-implemented.

2. **Security pattern scanning** — The banned pattern / IO violation / suspicious import layered approach is thoughtful and works correctly.

3. **Multi-provider abstraction** — Clean factory pattern with env var auto-detection and graceful mock fallback.

4. **Error classification** — Transient vs. permanent vs. budget error categories with appropriate retry behavior.

---

## Recommendations

1. **Fix the `or True` bug** in environment.py line 234
2. **Add a quick-start guide** that clones the formal-conjectures repo
3. **Don't retry permanent errors** in the OpenAI provider
4. **Add sandbox.py tests** (we've provided 16 as a starting point)
5. **Add solver integration tests** with mock LLM that returns realistic outputs
6. **Update GPT-5.4 support** using our `reasoning_effort` changes
7. **Fix Gemini dependency** — the `_cffi_backend` issue breaks 12 tests

---

## Files Modified/Created in This Assessment

- `src/llm/openai_provider.py` — Added `reasoning_effort` support for GPT-5.4
- `src/llm/factory.py` — Pass `OPENAI_REASONING_EFFORT` env var through
- `tests/test_independent_assessment.py` — 66 independent verification tests
- `ASSESSMENT.md` — This report
