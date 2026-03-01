# Erdos Proof Mining System

## What This Is

A consumer-grade desktop application that uses LLM-powered multi-agent orchestration to solve formalized mathematical conjectures in Lean 4. Users provide their own API keys and compute budget, the system runs a Prover/Critic loop against a problem manifest, validates proofs via SHA-256 theorem locking and Lean compilation, and packages verified Proof Artifacts for submission.

## Core Value

Automate the generation, validation, and packaging of Lean 4 mathematical proofs using adversarial multi-agent LLM orchestration — "Trust the Compiler, Verify the Intent."

## Requirements

### Validated

- Prover/Critic multi-agent loop with configurable LLM providers — existing
- SHA-256 theorem statement locking (integrity validation) — existing
- Sandbox environment with isolated `lake build` execution — existing
- Environment manager for automated elan/Lean installation — existing
- Google Gemini provider via official SDK — existing
- Mock LLM provider for testing — existing
- Configuration from env vars and JSON files — existing
- Cost tracking and budget circuit breaker — existing
- CLI entry point for headless solving — existing
- Banned pattern detection (sorry, admit, axiom) — existing
- Dangerous IO pattern detection — existing
- Tauri + React GUI shell with tabs (Mining, Settings, Solutions) — existing
- Live log viewer with auto-scroll — existing
- Manifest-based problem queue — existing

### Active

- [ ] Google/Gemini provider option in Settings UI (currently only OpenAI/Anthropic/Ollama)
- [ ] Update default model from deprecated gemini-2.0-flash to gemini-3-flash
- [ ] Async/streaming mining execution (currently blocking subprocess)
- [ ] Remote manifest fetching from GitHub repository URL
- [ ] Solution artifact persistence and gallery with proof viewing
- [ ] Proof export functionality (zip bundle for submission)
- [ ] Real-time cost tracking events from backend to frontend
- [ ] Solution found events from backend to frontend
- [ ] Stop mining actually kills the running process (currently just sets a flag)
- [ ] Settings persistence to disk (currently lost on app restart)
- [ ] Multiple LLM provider support in backend (OpenAI, Anthropic, Ollama providers)
- [ ] pyproject.toml with proper package metadata and entry points
- [ ] Production error handling (graceful degradation, retry logic)
- [ ] CI/CD with GitHub Actions for multi-platform builds
- [ ] Proper .gitignore for gui/src-tauri/target/ build artifacts

### Out of Scope

- Cloud deployment or hosted service — this is a local desktop app
- User accounts or authentication — single-user local tool
- Custom theorem creation UI — users work with existing problem manifests
- Mobile app — desktop only (Windows, macOS, Linux)
- Real-time collaboration — solo proof mining

## Context

- **Plan document**: `Plan.md` (237 lines) defines the full 3-phase architecture
- **Tech stack**: Python 3.11 backend + Tauri (Rust + React) frontend
- **Proof assistant**: Lean 4 via elan version manager
- **Target repository**: google-deepmind/formal-conjectures
- **LLM strategy**: Gemini primary (free tier available), OpenAI/Anthropic/Ollama optional
- **Build artifacts**: gui/src-tauri/target/ contains ~250KB of Rust build cache (should be gitignored)
- **Prior work**: Copilot PR #1 implemented initial Phase 2/3 scaffolding, subsequent commits added Gemini SDK and production fixes

## Constraints

- **Zero external dependencies for core**: Python stdlib only for the engine; google-generativeai for Gemini provider
- **Local-first**: All data stays on user's machine, no telemetry, no cloud calls except LLM API
- **Cross-platform**: Must work on Windows, macOS, Linux via Tauri
- **Budget safety**: Hard circuit breaker on API costs — never exceed user-defined limit
- **Lean compatibility**: Must track lean-toolchain file and auto-update when repo changes
- **Git commits**: Use `--no-gpg-sign` (SSH agent not running on dev machine)

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Tauri over Electron | <10MB binary, low RAM, native look | -- Pending |
| Python backend bundled via PyInstaller | Richest LLM ecosystem | -- Pending |
| Gemini as primary provider | Free tier available, good at math | -- Pending |
| SHA-256 theorem locking | Prevents LLM from modifying theorem statements | -- Pending |
| Multi-agent Prover/Critic | Adversarial validation catches more errors | -- Pending |

---
*Last updated: 2026-02-28 after initialization*
