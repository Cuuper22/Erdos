# Roadmap: Erdos Proof Mining System

## Overview

Transform the existing Erdos prototype into a production-grade desktop application. The Python backend already has the core Prover/Critic loop, sandbox, and validator — but needs multi-provider LLM support, production error handling, and real integration with the Tauri GUI. The GUI shell exists but is disconnected from reality: wrong provider options, no streaming, no persistence. This roadmap takes each subsystem to production quality, then wires them together into a distributable desktop app.

## Domain Expertise

None

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

- [ ] **Phase 1: Project Infrastructure** — Package structure, gitignore, CI skeleton
- [ ] **Phase 2: LLM Provider System** — Multi-provider support with Gemini, OpenAI, Anthropic, Ollama
- [ ] **Phase 3: Solver Engine Hardening** — Production error handling, retry logic, structured output
- [ ] **Phase 4: Validator & Security** — Enhanced theorem locking, IO sandboxing, proof packaging
- [ ] **Phase 5: Environment Manager** — Production elan installer, toolchain auto-update, repo caching
- [ ] **Phase 6: Remote Manifest System** — GitHub manifest fetching, versioning, campaign management
- [ ] **Phase 7: Tauri Backend Integration** — Async process spawning, streaming IPC, process management
- [ ] **Phase 8: Frontend Settings & Config** — Provider selection, settings persistence, model discovery
- [ ] **Phase 9: Frontend Mining & Solutions** — Real-time logs, cost tracking, proof viewer, export
- [ ] **Phase 10: Build & Distribution** — GitHub Actions CI/CD, multi-platform binaries

## Phase Details

### Phase 1: Project Infrastructure
**Goal**: Proper Python package with pyproject.toml, clean .gitignore (exclude gui/src-tauri/target/), CI skeleton
**Depends on**: Nothing (first phase)
**Research**: Unlikely (standard Python packaging)
**Plans**: 2 plans

Plans:
- [ ] 01-01: pyproject.toml, package metadata, entry points, dev dependencies
- [ ] 01-02: .gitignore cleanup, GitHub Actions CI skeleton with pytest

### Phase 2: LLM Provider System
**Goal**: Production-grade multi-provider LLM system with Gemini (updated model), OpenAI, Anthropic, Ollama
**Depends on**: Phase 1
**Research**: Likely (current API patterns for each provider)
**Research topics**: google-generativeai SDK current API, openai SDK patterns, anthropic SDK patterns, ollama REST API
**Plans**: 3 plans

Plans:
- [ ] 02-01: Fix GeminiProvider (gemini-3-flash default, proper error handling, retry with backoff)
- [ ] 02-02: Add OpenAI and Anthropic providers implementing LLMProvider interface
- [ ] 02-03: Add Ollama provider, provider factory/registry, provider auto-detection from env

### Phase 3: Solver Engine Hardening
**Goal**: Production solver loop with structured logging, graceful degradation, configurable retry strategies
**Depends on**: Phase 2
**Research**: Unlikely (internal refactoring)
**Plans**: 3 plans

Plans:
- [ ] 03-01: Structured logging with JSON output mode for GUI consumption
- [ ] 03-02: Retry strategies (exponential backoff, provider fallback, error classification)
- [ ] 03-03: Solver event system (emit events for cost, progress, solutions found)

### Phase 4: Validator & Security
**Goal**: Hardened validator with comprehensive pattern detection, IO sandboxing, proof artifact ZIP packaging
**Depends on**: Phase 3
**Research**: Unlikely (extending existing patterns)
**Plans**: 2 plans

Plans:
- [ ] 04-01: Enhanced banned pattern detection, IO sandboxing rules, security audit
- [ ] 04-02: Proof artifact packaging (ZIP bundle with proof, logs, critique, metadata)

### Phase 5: Environment Manager
**Goal**: Bulletproof elan/Lean installer that works on Windows/macOS/Linux with automatic toolchain management
**Depends on**: Phase 1
**Research**: Likely (elan installer behavior across platforms)
**Research topics**: elan-init.sh flags, Windows PowerShell installer, ELAN_HOME isolation, lean-toolchain file format
**Plans**: 3 plans

Plans:
- [ ] 05-01: Cross-platform elan installation with proper isolation in app directory
- [ ] 05-02: Toolchain auto-detection from lean-toolchain file, automatic lake update
- [ ] 05-03: Repository cloning/caching with integrity checks and incremental updates

### Phase 6: Remote Manifest System
**Goal**: Fetch problem manifests from GitHub repos, support campaign versioning and problem queue management
**Depends on**: Phase 4
**Research**: Likely (GitHub raw content API, manifest schema design)
**Research topics**: GitHub API for raw file access, caching strategies for manifests
**Plans**: 2 plans

Plans:
- [ ] 06-01: Remote manifest fetcher with GitHub API, local caching, version checking
- [ ] 06-02: Campaign management (active campaign tracking, problem prioritization, completion history)

### Phase 7: Tauri Backend Integration
**Goal**: Replace blocking subprocess with async process spawning, streaming stdout/stderr to frontend via Tauri events
**Depends on**: Phase 3, Phase 5
**Research**: Likely (Tauri v1 async commands, sidecar process management)
**Research topics**: Tauri sidecar API, tauri::async_runtime, streaming Command output, process kill on Windows
**Plans**: 3 plans

Plans:
- [ ] 07-01: Async Python process spawning with stdout/stderr line-by-line streaming
- [ ] 07-02: IPC event system (log-event, cost-update, solution-found, mining-status)
- [ ] 07-03: Process lifecycle management (start, stop/kill, restart, crash recovery)

### Phase 8: Frontend Settings & Config
**Goal**: Settings panel with all 4 providers, settings persistence to disk, model list updates
**Depends on**: Phase 7
**Research**: Unlikely (React state management, localStorage/file persistence)
**Plans**: 2 plans

Plans:
- [ ] 08-01: Add Google/Gemini provider option, update model lists for all providers
- [ ] 08-02: Settings persistence (save to ~/.erdos-prover/settings.json), load on startup

### Phase 9: Frontend Mining & Solutions
**Goal**: Real-time mining dashboard with streaming logs, live cost tracking, proof viewer, and export
**Depends on**: Phase 7, Phase 8
**Research**: Unlikely (React components, existing patterns)
**Plans**: 3 plans

Plans:
- [ ] 09-01: Real-time log viewer with level filtering, search, auto-scroll toggle
- [ ] 09-02: Live cost tracking bar, mining progress indicator, problem queue display
- [ ] 09-03: Proof viewer (syntax-highlighted Lean code), export to ZIP, solution history

### Phase 10: Build & Distribution
**Goal**: GitHub Actions CI/CD building Windows/macOS/Linux binaries, PyInstaller for Python backend
**Depends on**: All previous phases
**Research**: Likely (Tauri GitHub Actions, PyInstaller bundling with google-generativeai)
**Research topics**: tauri-action for GitHub Actions, PyInstaller hooks for google-generativeai, code signing
**Plans**: 2 plans

Plans:
- [ ] 10-01: GitHub Actions workflow for multi-platform Tauri builds
- [ ] 10-02: PyInstaller spec for Python backend, NSIS/DMG installer configuration

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9 → 10

Note: Phase 5 can run in parallel with Phases 2-4 (independent dependency chain).

| Phase | Plans Complete | Status | Completed |
|-------|---------------|--------|-----------|
| 1. Project Infrastructure | 0/2 | Not started | - |
| 2. LLM Provider System | 0/3 | Not started | - |
| 3. Solver Engine Hardening | 0/3 | Not started | - |
| 4. Validator & Security | 0/2 | Not started | - |
| 5. Environment Manager | 0/3 | Not started | - |
| 6. Remote Manifest System | 0/2 | Not started | - |
| 7. Tauri Backend Integration | 0/3 | Not started | - |
| 8. Frontend Settings & Config | 0/2 | Not started | - |
| 9. Frontend Mining & Solutions | 0/3 | Not started | - |
| 10. Build & Distribution | 0/2 | Not started | - |
