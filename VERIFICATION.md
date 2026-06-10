# End-to-End Verification Report

**Date:** 2026-06-10
**Environment:** Linux container (Ubuntu 24.04 base), Python 3.12, no prior Lean toolchain, `release.lean-lang.org` blocked by network policy, `github.com` reachable.

This report documents a real end-to-end verification of the Erdos pipeline
against an actual Lean 4 compiler — not mocks. Everything below was executed,
not inferred.

---

## What was verified

### 1. Toolchain installation via the project's own installer

`python -m src.environment --install`

- elan 4.1.2 installed to the app-isolated `~/.erdos-prover/bin/elan/` —
  worked out of the box after splitting binary install from toolchain
  install (`--default-toolchain none`).
- `elan toolchain install stable` **failed** on this network:
  elan fetches channel metadata from `release.lean-lang.org`, which is
  blocked here (returns an HTML error page → elan: "Unexpected character:
  H at (1:1)"). This will affect any locked-down network.
- **Fix shipped:** `_install_toolchain_from_github()` in
  `src/environment.py` — resolves the latest release tag via the GitHub
  `releases/latest` redirect (no API token), downloads the official
  `lean-X.Y.Z-linux.zip` (826 MB), extracts it preserving Unix permission
  bits (Python's `ZipFile.extractall` drops the executable bit — see
  `_extract_zip_with_permissions`), and registers it with
  `elan toolchain link` + `elan default`.
- Result: **Lean 4.30.0 installed and functional** (`lean --version`,
  `lake init`, `lake build` all verified).

### 2. Bug found: elan proxies need `ELAN_HOME`, not just `PATH`

`src/sandbox.py` prepended the discovered elan bin directory to `PATH`
but never set `ELAN_HOME`. The elan proxy binaries (`lean`, `lake`)
resolve toolchains relative to `ELAN_HOME`, defaulting to `~/.elan` —
so with the app-isolated install the proxies failed with
"no default toolchain configured" even though `lake` was on `PATH`.

**Fix:** `_elan_env()` in `src/sandbox.py` builds the subprocess
environment with both `PATH` and `ELAN_HOME` derived from the discovered
install; used by `_init_lean_project()` and `run_lake_build()`.
`tests/test_real_data_validation.py` previously hardcoded `~/.elan/bin`
and now uses the same discovery, so the Lean-gated tests run against
whichever install exists.

### 3. The 9 formerly-skipped real-compilation tests

Before: `314 passed, 9 skipped` (skip reason: "Lean not installed").
After: **`323 passed, 0 skipped`** (8.9 s).

The now-executing tests verify, against the real compiler:

- a known-correct proof compiles (`test_correct_proof_compiles`)
- `sorry` compiles with a warning, and the validator still rejects it
- a wrong proof fails to compile (compiler as arbiter)
- a proof of a *modified* theorem compiles but is rejected by the
  SHA-256 theorem lock (the core anti-specification-gaming property,
  proven against real Lean output)
- the full pipeline — provider → integrity check → real `lake build` →
  critic → packaged artifact — succeeds end to end
  (`test_correct_provider_full_pipeline`)
- mock-mode output does **not** compile (mock is scaffolding, see below)

### 4. Mock-mode end-to-end run

`ERDOS_MOCK_MODE=1 python -m src.solver --manifest manifest.json`

- Lean pre-flight passes; all 4 example problems are attempted.
- Every attempt stops at the integrity gate: the mock provider's canned
  response still contains `sorry`, which is banned in candidates
  (`mining_complete: total_problems=4, solved=0, failed=4`).
- This is **by design** (the suite asserts mock output must not produce
  a valid proof) — mock mode exercises the loop, integrity checking,
  retry, and budget accounting without an API key; it does not
  demonstrate a solve. The end-to-end *success* path is covered by
  `test_correct_provider_full_pipeline` above.

---

## Not verified here

- Real LLM API calls (OpenRouter/OpenAI/Anthropic/Gemini/Ollama) — needs
  keys; the provider layer is covered by mocked tests.
- Windows and macOS installer paths (`elan-init.ps1`, `.tar.zst` assets) —
  the GitHub fallback downloads `.zip` assets, which lean4 publishes for
  all three platforms, but only Linux was executed.
- Tauri GUI ↔ sidecar integration (covered separately by the GUI build
  verification).

## How to reproduce locally

```bash
python -m src.environment --install   # installs elan + Lean (GitHub fallback if needed)
python -m pytest tests/ -q            # expect: 323 passed, 0 skipped
ERDOS_MOCK_MODE=1 python -m src.solver --manifest manifest.json
```
