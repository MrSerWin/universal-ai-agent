# Setup Guide

## Prerequisites

### 1. WSL2

Make sure WSL2 is installed and up to date:

```powershell
# PowerShell (as administrator)
wsl --install
wsl --update
wsl --set-default-version 2
```

Recommended distro: **Ubuntu 24.04 LTS**

```powershell
wsl --install -d Ubuntu-24.04
```

### 2. NVIDIA Drivers

Install the latest drivers **on Windows** (not inside WSL):
- Download from https://www.nvidia.com/drivers/
- Make sure you have the latest Game Ready / Studio driver

Verify inside WSL:

```bash
nvidia-smi
```

Should display the GPU and driver version. If it doesn't work, restart WSL:

```powershell
wsl --shutdown
wsl
```

### 3. CUDA in WSL

The CUDA toolkit is installed **automatically** via Windows drivers. Do not install CUDA separately inside WSL — it may cause conflicts.

Verify:

```bash
nvcc --version  # may not exist — that's fine
nvidia-smi      # this is what matters — must work
```

## Automatic Installation

```bash
# Clone the project
git clone git@github.com:MrSerWin/universal-ai-agent.git ~/aide
cd ~/aide

# Run the setup script (does everything)
bash scripts/setup-wsl.sh
```

### What the Script Does

1. **Checks hardware** — GPU, RAM, drivers
2. **Installs system packages** — build-essential, cmake, python3, git
3. **Installs Ollama** — LLM model server
4. **Downloads models:**
   - Qwen2.5-Coder-32B (~20GB) — primary model
   - Qwen2.5-Coder-7B (~4.5GB) — fast model
   - nomic-embed-text (~0.3GB) — embeddings
5. **Sets up Python environment** — venv + dependencies
6. **Installs the CLI** — `aide` command added to PATH
7. **Configures network access** — Ollama listens on 0.0.0.0

### Installation Time

| Step | Time |
|------|------|
| System packages | ~2 min |
| Ollama | ~1 min |
| Model downloads | ~20-40 min (depends on internet speed) |
| Python environment | ~2 min |
| **Total** | **~25-45 min** |

## Manual Installation

If the script doesn't suit your needs, install components manually:

### Ollama

```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama serve &
```

### Models

```bash
# Primary (32B)
ollama pull qwen2.5-coder:32b

# Fast (7B)
ollama pull qwen2.5-coder:7b

# Embeddings
ollama pull nomic-embed-text

# Alternative (16B) — optional
ollama pull deepseek-coder-v2:16b-lite-instruct-q8_0
```

### Python

```bash
cd ~/aide
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
```

### Verify

```bash
aide status
```

## Updating

### Update Models

```bash
ollama pull qwen2.5-coder:32b  # downloads new version if available
```

### Update the Agent

```bash
cd ~/aide
git pull
source .venv/bin/activate
pip install -e .
```

## Uninstallation

```bash
# Remove models
ollama rm qwen2.5-coder:32b
ollama rm qwen2.5-coder:7b
ollama rm nomic-embed-text

# Remove Ollama
sudo systemctl stop ollama
sudo rm /usr/local/bin/ollama
sudo rm -rf /usr/share/ollama

# Remove the agent
rm -rf ~/aide
rm ~/.local/bin/aide
```

## WSL Performance Tuning

Create `C:\Users\<username>\.wslconfig`:

```ini
[wsl2]
memory=48GB
processors=16
swap=8GB
localhostForwarding=true

[experimental]
autoMemoryReclaim=gradual
```

Adjust `memory` and `processors` values to match your hardware. Leave ~8GB for Windows.

After changes:

```powershell
wsl --shutdown
wsl
```
