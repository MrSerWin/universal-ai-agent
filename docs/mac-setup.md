# macOS Setup Guide

## Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| Chip | Apple M1 | Apple M1 Pro / M2 / M3 / M4 |
| RAM | 16GB | 64GB+ unified memory |
| Disk | 30GB free | 100GB free |
| macOS | 13+ (Ventura) | 14+ (Sonoma) |

## RAM Tiers

The setup script automatically selects models based on your available RAM:

| RAM | Tier | Primary Model | Speed | Quality |
|-----|------|---------------|-------|---------|
| 16-31GB | Small | Qwen2.5-Coder-14B Q8 | ~25-35 tok/s | Good |
| 32-63GB | Medium | Qwen2.5-Coder-32B Q4_K_M | ~20-25 tok/s | Very good |
| 64-95GB | Large | Qwen2.5-Coder-32B Q8 | ~15-20 tok/s | Excellent |
| 96GB+ | XL | Qwen2.5-Coder-32B Q8 + Llama 70B | ~15-20 / ~8-12 tok/s | Best |

## Quick Start

```bash
# Clone the project
git clone https://github.com/MrSerWin/universal-ai-agent.git ~/aide
cd ~/aide

# Run the Mac setup script
bash scripts/setup-mac.sh

# Verify
aide status
```

## What the Script Does

1. **Detects hardware** — chip type, RAM, determines model tier
2. **Installs Homebrew** (if missing) and packages (python3, git, cmake)
3. **Installs Ollama** — via Homebrew or direct download
4. **Downloads models** — based on your RAM tier:
   - Always: 7B (fast) + nomic-embed-text (embeddings)
   - Tier-dependent: 14B / 32B Q4 / 32B Q8 / 70B
5. **Sets up Python** — venv + dependencies
6. **Installs CLI** — `aide` command
7. **Applies Mac config** — copies `models-mac.yaml` → `models.yaml`

## Apple Silicon vs NVIDIA: Key Differences

| Aspect | Apple Silicon (Metal) | NVIDIA (CUDA) |
|--------|----------------------|---------------|
| Memory | Unified (all RAM available) | Dedicated VRAM (24GB typical) |
| Speed | ~15-20 tok/s for 32B | ~25-30 tok/s for 32B |
| Max model | 70B on 96GB, 32B on 32GB | 32B on 24GB VRAM |
| Quantization | Q8 (better quality) | Q4 (fits in VRAM) |
| Offloading | Not needed | Needed for 70B+ |

**Bottom line:** Mac is slower per token but can run larger models and at higher quantization because unified memory removes the VRAM bottleneck.

## Model Configs

### Default Mac config (`config/models-mac.yaml`)

For 64GB+ Macs. Uses **32B Q8** as primary — higher quality than Q4:

```yaml
models:
  primary:
    ollama_tag: qwen2.5-coder:32b-instruct-q8_0   # ~35GB RAM
  fast:
    ollama_tag: qwen2.5-coder:7b-instruct-q8_0     # ~8GB RAM
  alternative:
    ollama_tag: qwen2.5-coder:14b-instruct-q8_0    # ~16GB RAM
  heavy:
    ollama_tag: llama3.1:70b-instruct-q4_K_M        # ~42GB RAM (96GB+ only)
  embedding:
    ollama_tag: nomic-embed-text                     # ~0.3GB RAM
```

### Switching between configs

```bash
# Use Mac config
cp config/models-mac.yaml config/models.yaml

# Use WSL/NVIDIA config (default)
git checkout config/models.yaml
```

## Using the 70B Model

On 96GB+ Macs, the 70B model is available for complex architecture tasks. It's slower (~8-12 tok/s) but significantly smarter for:

- System architecture design
- Complex multi-file refactoring
- Code migration planning
- Deep debugging of intricate logic

To use 70B as the default for complex tasks, edit `config/models.yaml`:

```yaml
routing:
  complexity_threshold:
    simple: fast
    medium: primary      # 32B for regular work
    complex: heavy       # 70B for architecture tasks
```

## Performance Tips

### 1. Close memory-hungry apps

Ollama needs RAM for the model. Close Chrome/Electron apps before loading large models.

Check current memory pressure:

```bash
# Show available memory
vm_stat | head -5
```

### 2. Adjust context length

Smaller context = faster generation + less RAM:

```yaml
# In config/models.yaml
context_length: 16384   # instead of 32768
```

### 3. Use the fast model for routine tasks

The 7B model at ~40-50 tok/s handles most quick tasks well. The router does this automatically in `auto` mode.

### 4. Ollama keeps models loaded

Ollama keeps the last-used model in RAM by default. To free memory:

```bash
# Unload all models
curl http://localhost:11434/api/generate -d '{"model": "qwen2.5-coder:32b-instruct-q8_0", "keep_alive": 0}'
```

Or configure auto-unload timeout:

```bash
# Unload after 5 minutes of inactivity
OLLAMA_KEEP_ALIVE=5m ollama serve
```

## Troubleshooting

### Ollama not using Metal

```bash
# Verify Metal support
system_profiler SPDisplaysDataType | grep Metal
# Should show: Metal Support: Metal 3 (or Metal 4)
```

### Slow generation

- Check Activity Monitor → Memory tab. If swap is being used, the model is too large.
- Switch to a smaller model or lower quantization.
- Reduce `context_length` in config.

### `aide: command not found`

```bash
# zsh (default on Mac)
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc
```

### Ollama won't start

```bash
# If installed via Homebrew
brew services start ollama

# If installed as app
open /Applications/Ollama.app

# Manual start
ollama serve
```
