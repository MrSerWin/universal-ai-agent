# Troubleshooting

## Ollama

### Ollama Won't Start

```bash
# Check status
systemctl status ollama

# View logs
journalctl -u ollama -n 50

# Start manually (for debugging)
ollama serve
```

**Common causes:**
- Port 11434 is in use → `lsof -i :11434`, kill the process
- No GPU permissions → `sudo usermod -aG video $USER`, then re-login

### nvidia-smi Works but Ollama Doesn't See the GPU

```bash
# Check that CUDA libraries are visible
ls /usr/lib/wsl/lib/libcuda*

# If files are missing — update Windows NVIDIA drivers
# Do NOT install CUDA toolkit separately inside WSL
```

### Model Won't Download

```bash
# Check available disk space
df -h

# Models are stored here:
ls -la ~/.ollama/models/

# Try a specific tag
ollama pull qwen2.5-coder:32b
```

### Model Runs on CPU Instead of GPU

```bash
# During generation:
nvidia-smi
# Should show an ollama process using VRAM

# If VRAM = 0 — Ollama can't see the GPU
# Fix:
export CUDA_VISIBLE_DEVICES=0
ollama serve
```

### Out of Memory (OOM) When Loading the 32B Model

```bash
# Check VRAM
nvidia-smi

# 32B Q4_K_M requires ~20GB VRAM
# If not enough — switch to 16B:
# In config/models.yaml: strategy: alternative

# Or reduce context length:
# context_length: 16384 (instead of 32768)
```

## Agent (aide)

### `aide: command not found`

```bash
# Check PATH
echo $PATH | tr ':' '\n' | grep local

# Add if missing
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc

# Or run directly
python -m agent.cli chat
```

### `ModuleNotFoundError: No module named 'agent'`

```bash
# Activate venv
source ~/aide/.venv/bin/activate

# Reinstall
cd ~/aide
pip install -e .
```

### `httpx.ConnectError` — Can't Connect to Ollama

```bash
# Check that Ollama is running
curl http://localhost:11434/api/tags

# If error — start it:
ollama serve &

# If using a different host:
export OLLAMA_HOST=http://192.168.1.100:11434
aide chat
```

### Slow Generation

**Check the model is on GPU:**
```bash
# During generation
nvidia-smi
# The ollama line should show GPU Memory Usage > 0
```

**Reduce context length:**
```yaml
# config/models.yaml
context_length: 16384  # instead of 32768
```

**Switch to the fast model:**
```yaml
routing:
  strategy: fast_only
```

**Or use the 16B alternative:**
```yaml
routing:
  strategy: alternative
```

### Agent Gets Stuck in Tool-Calling Loop

The max iteration limit is 15. If the agent hits the limit:
- Rephrase your request more specifically
- Use `--no-tools` for simple chat
- Break the task into smaller steps

## RAG

### Indexing Hangs

```bash
# Check that the embedding model is loaded
ollama list | grep nomic

# If not there — download it
ollama pull nomic-embed-text

# For large projects, indexing can take 10-15 minutes
```

### Poor Search Results

- Make sure the project is indexed: `aide init .`
- Force re-index (delete `.aide/chroma_db/`)
- Check that files aren't in the exclusion list (node_modules, etc.)

### `.aide/` Takes Up Too Much Space

```bash
# Check size
du -sh .aide/

# Delete and re-index
rm -rf .aide/
aide init .
```

## WSL

### WSL Is Slow

Create `C:\Users\<username>\.wslconfig`:

```ini
[wsl2]
memory=48GB
processors=16
swap=8GB

[experimental]
autoMemoryReclaim=gradual
```

```powershell
wsl --shutdown
wsl
```

### File System Is Slow

WSL2 is slow with files on the Windows drive (`/mnt/c/`).

**Solution:** Keep projects in the Linux file system:

```bash
# Bad (slow):
cd /mnt/c/Users/user/projects/my-app

# Good (fast):
cd ~/projects/my-app
```

### Ollama Not Accessible from Windows

```bash
# In WSL — find the IP
hostname -I

# From Windows — check access
curl http://172.x.x.x:11434/api/tags
```

If it doesn't work — check Windows Firewall.

### GPU Not Visible in WSL

1. Update NVIDIA drivers on **Windows** to the latest version
2. Update WSL: `wsl --update`
3. Restart: `wsl --shutdown`, then `wsl`
4. Verify: `nvidia-smi`

## Networking

### Ollama Not Accessible on LAN

```bash
# Check what it's listening on
ss -tlnp | grep 11434

# Should be 0.0.0.0:11434, not 127.0.0.1:11434
# If 127.0.0.1 — configure:
sudo systemctl edit ollama
# Add:
# [Service]
# Environment="OLLAMA_HOST=0.0.0.0:11434"
sudo systemctl restart ollama
```

### Connecting from Another Device

```bash
# Find the machine's IP
hostname -I

# From another device
curl http://<IP>:11434/api/tags
```

For VS Code on another machine — specify the IP in Continue.dev settings.

## Updating

### Update Ollama

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

### Update Models

```bash
ollama pull qwen2.5-coder:32b   # downloads update if available
ollama pull qwen2.5-coder:7b
ollama pull nomic-embed-text
```

### Update aide

```bash
cd ~/aide
git pull
source .venv/bin/activate
pip install -e .
```
