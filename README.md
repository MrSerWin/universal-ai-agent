# aide — Local AI Code Agent

Fully local AI agent for software development. Runs on your hardware with no cloud APIs.

## Features

- **Interactive chat** with full project context
- **Code review** — find bugs, quality issues, anti-patterns
- **Security audit** — vulnerability analysis (OWASP Top 10)
- **Smart commit** — auto-generated commit messages
- **RAG indexing** — agent understands the entire project via vector search
- **Auto model routing** — router picks the best model for each task
- **VS Code integration** — via Continue.dev or built-in tasks
- **LAN access** — API accessible on local network

## Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| GPU | 16GB VRAM (16B model) | 24GB VRAM (32B model) |
| RAM | 32GB | 64GB |
| Disk | 50GB free | 100GB free |
| OS | WSL2 / Linux | WSL2 + Windows 11 |
| CUDA | 12.0+ | 12.4+ |

**Tested on:** NVIDIA RTX series GPU with 24GB VRAM, 64GB system RAM

## Quick Start

```bash
# Clone the project
git clone https://github.com/MrSerWin/universal-ai-agent.git ~/aide
cd ~/aide

# Run setup (pick one)
bash scripts/setup-mac.sh    # macOS (Apple Silicon)
bash scripts/setup-wsl.sh    # Windows (WSL2 + NVIDIA GPU)

# Check status
aide status

# Index your project
cd /path/to/your/project
aide init .

# Start working
aide chat
```

## Commands

| Command | Description |
|---------|-------------|
| `aide chat` | Interactive chat with the agent |
| `aide review <file>` | Code review a file |
| `aide review --all` | Code review all changes (git diff) |
| `aide security <file>` | Security audit |
| `aide commit` | Auto-generate commit message and commit |
| `aide init <path>` | Initialize and index a project |
| `aide status` | Status: models, Ollama health, system info |

## Models

| Model | Size | Speed | Used for |
|-------|------|-------|----------|
| Qwen2.5-Coder-32B (Q4_K_M) | ~20GB VRAM | ~25-30 tok/s | Main work: generation, review, refactoring |
| Qwen2.5-Coder-7B (Q8) | ~8GB VRAM | ~100+ tok/s | Fast tasks: autocomplete, classification, commits |
| DeepSeek-Coder-V2-16B (Q8) | ~17GB VRAM | ~50-60 tok/s | Alternative to 32B: faster, slightly lower quality |
| Qwen2.5-Coder-32B (Q8) | ~35GB RAM | ~15-20 tok/s | Mac primary: higher quality with unified memory |
| Llama 3.1 70B (Q4_K_M) | ~42GB RAM | ~8-12 tok/s | Complex architecture tasks (96GB+ Mac) |
| nomic-embed-text | ~0.3GB | — | Embeddings for RAG indexing |

## Stack

- **Python 3.11+** — agent core
- **Ollama** — model server
- **ChromaDB** — vector DB for RAG
- **Rich + Click** — CLI interface
- **Continue.dev** — VS Code integration

## Documentation

- [Setup Guide — WSL/Linux](docs/setup.md)
- [Setup Guide — macOS](docs/mac-setup.md)
- [Architecture](docs/architecture.md)
- [Commands Reference](docs/commands.md)
- [Configuration](docs/configuration.md)
- [VS Code Integration](docs/vscode.md)
- [RAG System](docs/rag.md)
- [Troubleshooting](docs/troubleshooting.md)

## License

MIT
