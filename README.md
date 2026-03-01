# Erdos

Automated mathematical proof mining. You provide compute and API credits, it tries to solve formalized math conjectures in Lean 4.

Uses a Prover/Critic multi-agent loop — one LLM generates proof attempts, another pokes holes in them, repeat until the Lean compiler is happy or the budget runs out. Theorem statements are SHA-256 hashed so the agents can't quietly change what they're proving.

## Quick Start

### Desktop App

Download from [Releases](https://github.com/Cuuper22/Erdos/releases) — Python is bundled, no installation needed:
- Windows: `.msi` / `.exe`
- macOS: `.dmg`
- Linux: `.AppImage` / `.deb`

### Command Line

```bash
git clone https://github.com/Cuuper22/Erdos.git
cd Erdos
pip install -e "."
python -m src.environment --install    # sets up Lean toolchain
```

Set an API key:
```bash
export GOOGLE_API_KEY="your-key"
# Or: OPENAI_API_KEY, ANTHROPIC_API_KEY, OLLAMA_URL for local models
```

Run:
```bash
python -m src.solver --manifest manifest.json
python -m src.solver --manifest manifest.json --problem-id Erdos1024
python -m src.solver --list-solutions
```

Mock mode (no API key):
```bash
export ERDOS_MOCK_MODE=1
python -m src.solver --manifest manifest.json
```

## LLM Providers

All implemented, auto-detected from environment variables:

| Provider | Env Var | Default Model |
|----------|---------|---------------|
| Google Gemini | `GOOGLE_API_KEY` or `GEMINI_API_KEY` | gemini-3-flash |
| OpenAI | `OPENAI_API_KEY` | gpt-4o |
| Anthropic | `ANTHROPIC_API_KEY` | claude-sonnet-4-6 |
| Ollama (local) | `OLLAMA_URL` | llama3.3 |
| Mock (testing) | `ERDOS_MOCK_MODE=1` | — |

Override model: `export LLM_MODEL="gemini-3-pro"`

## Configuration

Env vars: `LLM_MODEL`, `MAX_COST_USD`, `MAX_RETRIES`, `BUILD_TIMEOUT`.

Or `config.json`:
```json
{
  "llm": { "provider": "google", "model": "gemini-3-flash", "temperature_prover": 0.7, "temperature_critic": 0.1 },
  "cost": { "max_cost_usd": 5.0 },
  "solver": { "max_retries": 10, "build_timeout_seconds": 60 }
}
```

## Architecture

**Python Backend:**
- `solver.py` — Prover/Critic loop with exponential backoff, JSON Lines event output
- `validator.py` — Security analysis: banned patterns, IO violations, suspicious imports (SHA-256 theorem locking)
- `sandbox.py` — Isolated Lean build environments
- `environment.py` — Auto-installs elan/Lean toolchain, SHA-256 verified downloads, toolchain caching
- `manifest.py` — Remote problem manifest fetching with GitHub URL conversion, TTL caching, offline fallback
- `campaign.py` — Problem history persistence, unsolved prioritization
- `packager.py` — ZIP artifact bundling (proof, build log, critique, metadata) with JSON solution index
- `llm/` — Provider factory with auto-detection, retry logic, cost tracking

**Desktop GUI (Tauri):**
- Rust backend: async process spawning, typed IPC events, settings persistence
- React frontend: settings panel (4 providers + custom model), log viewer with filtering/search, cost progress bar, proof viewer with Lean 4 syntax highlighting, solution export

**CI/CD:**
- Tests run on push (Python 3.10-3.12 matrix + Rust clippy/build)
- Tag push triggers: pytest → PyInstaller build (3 platforms) → Tauri build with sidecar → GitHub Release

## Project Structure

```
Erdos/
├── src/                        # Python backend
│   ├── solver.py               # Prover/Critic loop
│   ├── validator.py            # Security + theorem integrity
│   ├── sandbox.py              # Isolated Lean builds
│   ├── environment.py          # Lean/elan management
│   ├── manifest.py             # Remote problem manifests
│   ├── campaign.py             # Problem history tracking
│   ├── packager.py             # Solution ZIP bundling
│   ├── config.py               # Configuration
│   ├── events.py               # JSON Lines event system
│   └── llm/                    # LLM provider factory
│       ├── factory.py          # Auto-detection + instantiation
│       ├── gemini.py           # Google Gemini
│       ├── openai_provider.py  # OpenAI
│       ├── anthropic_provider.py # Anthropic
│       └── ollama_provider.py  # Ollama (local)
├── gui/                        # Tauri desktop app
│   ├── src/                    # React frontend
│   │   ├── App.tsx             # Main app with event listeners
│   │   └── components/         # Settings, LogViewer, SolutionsGallery
│   └── src-tauri/              # Rust backend
│       └── src/main.rs         # IPC, process management, settings
├── tests/                      # 195 tests
├── manifest.json               # Problem queue
├── erdos-solver.spec           # PyInstaller config
└── .github/workflows/          # CI/CD
```

## Building from Source

```bash
# Desktop GUI
cd gui && npm install
npm run tauri dev      # dev mode with hot reload
npm run tauri build    # production build

# Tests (195 passing)
python -m pytest tests/ -v
```

## License

MIT
