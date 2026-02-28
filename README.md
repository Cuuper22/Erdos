# Erdos

Automated mathematical proof mining. You provide compute and API credits, it tries to solve formalized math conjectures in Lean 4.

Uses a Prover/Critic multi-agent loop -- one LLM generates proof attempts, another pokes holes in them, repeat until the Lean compiler is happy or the budget runs out. Theorem statements are SHA-256 hashed so the agents can't quietly change what they're proving.

## Status

- Phase 1: Headless solver -- done
- Phase 2: Environment manager (auto-installs Lean/elan) -- done
- Phase 3: Desktop GUI (Tauri + React) with CI/CD -- done

It works. Whether it solves your particular conjecture is a different question.

## Quick Start

### Desktop App

Download from releases:
- Windows: `.msi` / `.exe`
- macOS: `.dmg`
- Linux: `.AppImage` / `.deb`

### Command Line

```bash
git clone https://github.com/Cuuper22/Erdos.git
cd Erdos
pip install -r requirements.txt
python -m src.environment --install    # sets up Lean toolchain
```

Set an API key:
```bash
export OPENAI_API_KEY="..."
# or ANTHROPIC_API_KEY, or OLLAMA_URL for local models
```

Run the solver:
```bash
python -m src.solver --manifest manifest.json
python -m src.solver --manifest manifest.json --problem-id Erdos1024   # specific problem
```

## Configuration

```json
{
  "llm": {
    "provider": "openai",
    "model": "gpt-4",
    "temperature_prover": 0.7,
    "temperature_critic": 0.1
  },
  "cost": { "max_cost_usd": 5.0 },
  "solver": { "max_retries": 10, "build_timeout_seconds": 60 }
}
```

Or env vars: `LLM_MODEL`, `MAX_COST_USD`, `MAX_RETRIES`, `BUILD_TIMEOUT`.

## Stack

**Backend (Python):** Prover/Critic loop, theorem integrity validation (SHA-256), sandboxed Lean builds, cost tracking

**Environment Manager:** Auto-installs elan + Lean toolchain, manages Lake builds in isolated sandboxes

**Desktop GUI (Tauri v2):** Rust backend + React frontend. Settings panel, live log streaming, solutions gallery.

## Project Structure

```
Erdos/
├── src/                    # Python backend
│   ├── solver.py           # Prover/Critic loop
│   ├── sandbox.py          # Isolated build environments
│   ├── validator.py        # Theorem hash verification
│   ├── environment.py      # Lean/elan management
│   └── config.py           # Configuration
├── gui/                    # Tauri desktop app
│   ├── src/                # React frontend
│   └── src-tauri/          # Rust backend
├── manifest.json           # Problem queue
└── .github/workflows/      # CI/CD
```

## Development

```bash
cd gui
npm install
npm run tauri dev      # dev mode
npm run tauri build    # release build
```

See [Plan.md](Plan.md) for the full roadmap.

## License

Open source. See LICENSE.
