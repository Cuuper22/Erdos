# Erdos Proof Mining System

## 1. Executive Summary

**Objective:** Create a consumer-grade desktop application that utilizes user-provided compute and API credits to solve formalized mathematical conjectures in Lean 4.

**Core Philosophy:** "Trust the Compiler, Verify the Intent."

**Output:** The system does not submit "solutions." It submits **Proof Artifacts**—verified, compiled code bundles that have passed a local adversarial critique, ready for rapid human review.

---

## 2. High-Level Architecture

The system follows a **Local Client-Server** model wrapped in a desktop GUI.

| Component | Description |
|-----------|-------------|
| **The Shell (UI)** | A lightweight GUI (Electron or Tauri) that manages settings and displays progress. |
| **The Engine (Python)** | Handles the LLM orchestration, file management, and git operations. |
| **The Lab (Lean 4 Environment)** | A managed instance of the Lean toolchain (elan) running in a controlled subdirectory. |

---

## 3. User Experience (UX) Flow

### 3.1 Onboarding
User downloads the installer (.exe / .dmg).

### 3.2 Configuration
1. User launches app.
2. Input: OpenAI/Anthropic API Key OR Local Model URL (Ollama).
3. Input: Maximum Cost Limit (e.g., "Stop after $5").

### 3.3 Execution
1. User clicks "Start Mining".
2. The app downloads the latest "Problem Set" manifest from the official repository.

### 3.4 The Loop
The user watches a terminal-like log:
> "Attempting Problem #104... Compiling... Failed. Retrying... Success! Validating..."

### 3.5 Submission
On success, the app automatically zips the artifacts and pushes them to a "Solutions" branch or API endpoint.

---

## 4. Technical Specifications

### 4.A The Tech Stack

| Component | Technology | Rationale |
|-----------|------------|-----------|
| **Frontend (GUI)** | Tauri (Rust + React) | Extremely small binary size (<10MB), low RAM usage, native look and feel. Easier to bundle than Electron. |
| **Backend (Logic)** | Python 3.11 (bundled via PyInstaller) | Richest ecosystem for LLM orchestration (LiteLLM, LangChain) and file I/O. |
| **Proof Assistant** | Elan (Lean Version Manager) | We must manage the Lean version automatically. The user cannot be expected to install Lean manually. |

### 4.B The "Smart" Wrapper (Multi-Agent Logic)

This is the core "brain" that runs locally on the user's machine.

#### Agent 1: The Prover (Temperature: 0.7)
- **Goal:** Close the `sorry` gap in the code.
- **Prompt Constraints:** "You are a formalization expert. Output raw Lean 4 code only. Do not modify imports unless necessary."

#### Agent 2: The Critic (Temperature: 0.1)
- **Goal:** Quality Control.
- **Trigger:** Activates after the Prover generates code and before final submission.
- **Checklist:**
  - Did the code compile? (Yes/No)
  - Is the proof "brute force" or elegant?
  - Security Check: Are there any `os.cmd` or weird I/O calls? (Lean can run IO, we must block this).

#### The Rigid Validator (Non-AI)
- **Theorem Locking:** Calculates SHA-256 hash of the theorem statement lines in the original file. If the candidate file has a different hash for those lines, it is discarded instantly.
- **Sanity Grep:** Regex search for `sorry`, `admit`, or `axiom` in the proof block.

---

## 5. Development Phases

### Phase 1: The Headless MVP (Week 1-2)
**Goal:** A Python script that can solve one problem given a hardcoded API key.

**Deliverables:**
- `solver.py`: Implements the Prover/Critic loop.
- `sandbox.py`: Manages the lake build process and captures stderr (error logs).
- `manifest.json`: A standard format for defining the problem queue.

### Phase 2: The Environment Manager (Week 3)
**Goal:** Automate the installation of Lean.

**Logic:**
1. Check if `elan` is installed.
2. If not, download the `elan-init.sh` (or Windows equivalent) and run it silently in a localized app directory (`~/.the-prover/bin`).
3. Clone the target repository (e.g., `google-deepmind/formal-conjectures`) into a cached directory.

### Phase 3: The GUI & Packaging (Week 4-5)
**Goal:** Build the Tauri frontend.

**Features:**
- Settings Panel (API Keys, Model Selection).
- Live Logs (Streaming stdout from the Python process to the React UI).
- "Found Solutions" Gallery.

**Packaging:** Use GitHub Actions to build binaries for Windows, MacOS, and Linux.

---

## 6. Detailed Component Logic (The "Wrapper")

Here is the robust workflow for the Backend Engine:

```python
# Pseudo-code for the robustness engine

def process_problem(problem_id, config):
    # 1. SETUP
    # Clone repo to a temp folder to prevent corrupting the main install
    work_dir = create_sandbox(problem_id)
    original_hash = get_theorem_hash(work_dir, problem_id)
    
    # 2. LOAD CONTEXT
    # Maintainers can provide "hints" or "strategies" in the manifest
    instructions = load_maintainer_instructions(problem_id)
    
    # 3. AGENT LOOP
    attempts = 0
    last_error = None
    while attempts < config.max_retries:
        # A. GENERATE
        proof_candidate = Agent_Prover.generate(instructions, error_log=last_error)
        
        # B. INTEGRITY CHECK (Fast Fail)
        if get_theorem_hash(proof_candidate) != original_hash:
            last_error = "SYSTEM: You modified the theorem statement. FORBIDDEN."
            attempts += 1
            continue
            
        # C. COMPILATION CHECK
        # Run 'lake build' with a timeout to prevent infinite loops
        success, logs = run_lake_build(work_dir, timeout=60)
        
        if success:
            # D. CRITIC CHECK
            critique = Agent_Critic.review(proof_candidate)
            if critique.status == "PASS":
                return package_artifact(proof_candidate, logs, critique)
            else:
                last_error = f"CRITIC: {critique.feedback}"
        else:
            last_error = f"COMPILER: {logs}"
            
        attempts += 1
        
    return None
```

---

## 7. Edge Cases & Risk Mitigation

| Risk Area | Scenario | Solution |
|-----------|----------|----------|
| **User Environment** | User has a messy path or spaces in username (common Windows issue). | The app must use relative paths strictly inside its own installation folder or `%APPDATA%`. Do not rely on system PATH. |
| **Dependency Hell** | The repo updates mathlib and the user's cached version breaks. | The app checks the repo's `lean-toolchain` file on every launch. If it changed, it runs `lake update` automatically. |
| **Malicious Instruction** | An LLM tries to write a file outside the directory. | Sandboxing: The Lean process should ideally run with restricted permissions. Alternatively, the Critic agent explicitly scans for IO modules. |
| **Cost Runaway** | The loop gets stuck and burns $100 of API credit. | Hard Circuit Breaker: The app tracks token usage internally. If it hits the user-defined limit (e.g., $5), it kills the process immediately. |

---

## 8. The "Maintainer Control Panel"

*(This is how the experts control the swarm)*

The app reads a remote `manifest.json` file hosted on GitHub. Maintainers control the app behavior by editing this file:

```json
{
  "active_campaign": "Erdos_Problems_Q1_2026",
  "min_app_version": "1.0.2",
  "priority_problems": [
    {
      "id": "Erdos1024",
      "path": "FormalConjectures/Erdos/1024.lean",
      "difficulty": "Hard",
      "maintainer_note": "Focus on induction strategies. Watch out for divide by zero."
    }
  ],
  "banned_tactics": ["sorry", "admit", "cheating_tactic"]
}
```

---

## 9. File Structure (All Phases)

```
Erdos/
├── Plan.md                     # This document
├── README.md                   # Project documentation
├── manifest.json               # Problem queue definition
├── requirements.txt            # Python dependencies
├── .gitignore                  # Git ignore rules
│
├── src/                        # Phase 1: Python Backend
│   ├── __init__.py
│   ├── solver.py               # Main Prover/Critic loop
│   ├── sandbox.py              # Lake build process manager
│   ├── validator.py            # Theorem hash validation & sanity checks
│   ├── config.py               # Configuration management
│   └── environment.py          # Phase 2: Lean/elan environment manager
│
├── gui/                        # Phase 3: Tauri Desktop Application
│   ├── package.json            # Node.js dependencies
│   ├── vite.config.ts          # Vite build configuration
│   ├── tsconfig.json           # TypeScript configuration
│   ├── index.html              # Entry HTML
│   ├── src/
│   │   ├── main.tsx            # React entry point
│   │   ├── App.tsx             # Main application component
│   │   ├── styles.css          # Global styles
│   │   └── components/
│   │       ├── LogViewer.tsx       # Live log streaming
│   │       ├── SettingsPanel.tsx   # API keys & model selection
│   │       └── SolutionsGallery.tsx # Found solutions display
│   └── src-tauri/
│       ├── Cargo.toml          # Rust dependencies
│       ├── tauri.conf.json     # Tauri configuration
│       ├── build.rs            # Build script
│       └── src/
│           └── main.rs         # Tauri backend (Rust)
│
└── .github/
    └── workflows/
        └── build.yml           # CI/CD for multi-platform builds
```
