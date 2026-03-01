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

**Prerequisites:**
- Python 3.11 or higher
- Git
- (Optional) Rust and Cargo for building the GUI

**Installation:**

```bash
git clone https://github.com/Cuuper22/Erdos.git
cd Erdos
pip install -r requirements.txt
python -m src.environment --install    # sets up Lean toolchain
```

Set an API key (Google Gemini recommended):
```bash
export GOOGLE_API_KEY="your-api-key-here"
# Alternatively: OPENAI_API_KEY, ANTHROPIC_API_KEY, or OLLAMA_URL for local models
```

Run the solver:
```bash
python -m src.solver --manifest manifest.json
python -m src.solver --manifest manifest.json --problem-id Erdos1024   # specific problem
```

For testing without an API key:
```bash
export ERDOS_MOCK_MODE=1
python -m src.solver --manifest manifest.json
```

## Supported LLM Providers

- **Google Gemini** (Recommended, implemented) - Fast, accurate, cost-effective
  - Default model: `gemini-2.0-flash`
  - Set `GOOGLE_API_KEY` environment variable
  - Get API key from: https://ai.google.dev/
  
- **Mock Provider** (For testing only)
  - No API key required
  - Set `ERDOS_MOCK_MODE=1`
  - Returns dummy proofs for testing the pipeline

- **Planned** (Not yet implemented):
  - OpenAI GPT-4
  - Anthropic Claude
  - Local models via Ollama


## LLM Provider Architecture

Erdos uses a modular LLM provider system with multiple backends:

### Gemini (Google AI) - **Recommended** (Official SDK)

**Status:** Fully implemented using official  SDK

- **Free tier:** 1500 requests/day, generous quotas
- **Models:** `gemini-2.0-flash` (default, fastest), `gemini-pro` (more capable)
- **Get API key:** https://ai.google.dev/
- **Setup:** `export GEMINI_API_KEY="your-key"` or `export GOOGLE_API_KEY="your-key"`

**Why the official SDK?**
- Better error handling and automatic retries
- Accurate token counting for cost management
- Support for latest Gemini features
- More robust than direct REST calls

### Other Providers (Coming Soon)

- **OpenAI:** Planned
- **Anthropic:** Planned  
- **Ollama (local):** Planned
- **Mock (testing):** Built-in, no API key needed

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

## Building from Source

### Desktop GUI

```bash
cd gui
npm install
npm run tauri dev      # development mode with hot reload
npm run tauri build    # production build
```

The built application will be in `gui/src-tauri/target/release/`.

### Running Tests

```bash
# Python tests
python -m pytest tests/

# Or with unittest
python -m unittest discover tests/
```

## Development

**Project Structure:**
- `src/` - Python backend (solver, validator, sandbox manager)
- `gui/` - Tauri desktop application (Rust + React)
- `tests/` - Test suite
- `examples/` - Example problem sets

**Contributing:**
1. Fork the repository
2. Create a feature branch
3. Add tests for new features
4. Run the test suite
5. Submit a pull request

See [Plan.md](Plan.md) for the full roadmap.

## License

Open source. See LICENSE.
