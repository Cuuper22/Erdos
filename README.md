# Erdos Proof Mining System

A consumer-grade desktop application that utilizes user-provided compute and API credits to solve formalized mathematical conjectures in Lean 4.

## Overview

The Erdos Proof Mining System is designed to help mathematicians and proof engineers solve formal mathematical problems by leveraging Large Language Models (LLMs). The system follows the philosophy of "Trust the Compiler, Verify the Intent" - producing verified, compiled proof artifacts that have passed adversarial review.

## Features

- **Multi-Agent Architecture**: Uses a Prover agent to generate proofs and a Critic agent to validate quality
- **Theorem Integrity Protection**: SHA-256 hashing ensures theorem statements cannot be modified
- **Cost Management**: Built-in budget controls to prevent runaway API costs
- **Sandboxed Execution**: Isolated build environments prevent corruption of the main installation
- **Automatic Environment Setup**: Installs Lean/elan automatically in a localized directory
- **Desktop GUI**: Cross-platform Tauri application with live logs and solution gallery

## Project Structure

```
Erdos/
├── Plan.md                     # Development plan and architecture
├── README.md                   # This file
├── src/                        # Python Backend
│   ├── config.py               # Configuration management
│   ├── solver.py               # Main Prover/Critic loop
│   ├── sandbox.py              # Lake build process manager
│   ├── validator.py            # Theorem hash validation
│   └── environment.py          # Lean/elan environment manager
├── gui/                        # Tauri Desktop Application
│   ├── src/                    # React frontend
│   └── src-tauri/              # Rust backend
├── manifest.json               # Problem queue definition
└── .github/workflows/          # CI/CD for builds
```

## Quick Start

### Option 1: Desktop Application (Recommended)

Download the latest release for your platform:
- **Windows**: `.msi` or `.exe` installer
- **macOS**: `.dmg` disk image  
- **Linux**: `.AppImage` or `.deb` package

### Option 2: Command Line

#### Prerequisites

- Python 3.11+
- Lean 4 / Elan (can be auto-installed)
- An API key for OpenAI, Anthropic, or a local Ollama instance

#### Installation

1. Clone the repository:
```bash
git clone https://github.com/Cuuper22/Erdos.git
cd Erdos
```

2. Install Python dependencies:
```bash
pip install -r requirements.txt
```

3. Set up Lean environment (automatic):
```bash
python -m src.environment --install
```

4. Set up your API key:
```bash
export OPENAI_API_KEY="your-api-key-here"
# OR
export ANTHROPIC_API_KEY="your-api-key-here"
# OR
export OLLAMA_URL="http://localhost:11434"
```

#### Usage

Run the solver with a manifest file:
```bash
python -m src.solver --manifest manifest.json
```

Solve a specific problem:
```bash
python -m src.solver --manifest manifest.json --problem-id Erdos1024
```

Check environment status:
```bash
python -m src.environment --status
```

### Configuration

Create a `config.json` file to customize settings:

```json
{
  "llm": {
    "provider": "openai",
    "model": "gpt-4",
    "temperature_prover": 0.7,
    "temperature_critic": 0.1
  },
  "cost": {
    "max_cost_usd": 5.0
  },
  "solver": {
    "max_retries": 10,
    "build_timeout_seconds": 60
  }
}
```

Or use environment variables:
- `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` / `OLLAMA_URL`
- `LLM_MODEL` - Model to use (default: gpt-4)
- `MAX_COST_USD` - Maximum spending limit (default: $5)
- `MAX_RETRIES` - Maximum proof attempts per problem (default: 10)
- `BUILD_TIMEOUT` - Lean build timeout in seconds (default: 60)

## Development

### Building the Desktop App

```bash
cd gui
npm install
npm run tauri build
```

### Running in Development Mode

```bash
cd gui
npm install
npm run tauri dev
```

## Architecture

The system consists of three main components:

1. **Python Backend** (`src/`): Core proof mining logic
   - Multi-agent Prover/Critic loop
   - Theorem integrity validation
   - Sandbox build management

2. **Environment Manager** (`src/environment.py`): Lean toolchain management
   - Automatic elan installation
   - Repository cloning and caching
   - Toolchain version management

3. **Tauri GUI** (`gui/`): Desktop application
   - Settings panel for API keys and models
   - Live log streaming
   - Solutions gallery

## Development Phases

See [Plan.md](Plan.md) for the complete development roadmap.

- ✅ **Phase 1**: Headless MVP with core solver logic
- ✅ **Phase 2**: Environment manager for automated Lean installation  
- ✅ **Phase 3**: Desktop GUI with Tauri + CI/CD for builds

## Contributing

Contributions are welcome! Please read the plan document to understand the architecture before submitting changes.

## License

This project is open source. See LICENSE for details.
