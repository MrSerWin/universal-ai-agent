#!/usr/bin/env bash
set -euo pipefail

# ============================================================
# aide — Local AI Code Agent — WSL2 Setup Script
#
# Requirements: WSL2 with Ubuntu, NVIDIA GPU with 16GB+ VRAM
#
# What this script does:
#   1. Checks GPU, RAM, NVIDIA drivers
#   2. Installs system packages (build-essential, python3, etc.)
#   3. Installs Ollama (LLM server)
#   4. Downloads models: Qwen2.5-Coder-32B, 7B, nomic-embed-text
#   5. Creates Python venv and installs dependencies
#   6. Installs the `aide` CLI command
#   7. Configures Ollama for LAN access
#
# Usage:
#   bash scripts/setup-wsl.sh
#
# Time: ~25-45 minutes (mostly model downloads)
# ============================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log()  { echo -e "${GREEN}[+]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }
err()  { echo -e "${RED}[✗]${NC} $1"; exit 1; }
info() { echo -e "${BLUE}[i]${NC} $1"; }

# ---- Pre-flight checks ----
check_prerequisites() {
    log "Checking prerequisites..."

    if ! command -v nvidia-smi &>/dev/null; then
        err "nvidia-smi not found. Install NVIDIA drivers for WSL2 first:
  https://developer.nvidia.com/cuda/wsl"
    fi

    GPU_NAME=$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -1)
    GPU_MEM=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits 2>/dev/null | head -1)
    log "GPU detected: ${GPU_NAME} (${GPU_MEM} MB)"

    TOTAL_RAM=$(free -g | awk '/^Mem:/{print $2}')
    log "RAM: ${TOTAL_RAM} GB"

    if [ "$TOTAL_RAM" -lt 32 ]; then
        warn "Less than 32GB RAM detected. 32B model may be slow with offloading."
    fi
}

# ---- System packages ----
install_system_deps() {
    log "Installing system dependencies..."
    sudo apt-get update -qq
    sudo apt-get install -y -qq \
        build-essential \
        cmake \
        curl \
        git \
        python3 \
        python3-pip \
        python3-venv \
        wget \
        jq \
        tree-sitter-cli 2>/dev/null || true
}

# ---- Ollama ----
install_ollama() {
    if command -v ollama &>/dev/null; then
        log "Ollama already installed: $(ollama --version)"
        return
    fi

    log "Installing Ollama..."
    curl -fsSL https://ollama.com/install.sh | sh

    log "Ollama installed: $(ollama --version)"

    # Start and wait for Ollama to be ready
    start_ollama_service
}

start_ollama_service() {
    if curl -sf http://localhost:11434/api/tags >/dev/null 2>&1; then
        log "Ollama service already running."
        return
    fi

    log "Starting Ollama service..."
    sudo systemctl start ollama 2>/dev/null || ollama serve &>/dev/null &

    log "Waiting for Ollama to be ready..."
    for i in $(seq 1 30); do
        if curl -sf http://localhost:11434/api/tags >/dev/null 2>&1; then
            log "Ollama is ready."
            return
        fi
        sleep 1
    done

    err "Ollama failed to start after 30 seconds. Try running 'ollama serve' manually."
}

# ---- Pull models ----
pull_models() {
    log "Pulling AI models (this will take a while)..."

    # Primary: Qwen2.5-Coder 32B
    info "Pulling Qwen2.5-Coder 32B (Q4_K_M) — ~20GB..."
    ollama pull qwen2.5-coder:32b-instruct-q4_K_M || {
        warn "Exact tag not found, trying default 32b tag..."
        ollama pull qwen2.5-coder:32b
    }

    # Fast: Qwen2.5-Coder 7B
    info "Pulling Qwen2.5-Coder 7B — ~4.5GB..."
    ollama pull qwen2.5-coder:7b-instruct-q8_0 || {
        warn "Exact tag not found, trying default 7b tag..."
        ollama pull qwen2.5-coder:7b
    }

    # Embedding model
    info "Pulling nomic-embed-text — ~0.3GB..."
    ollama pull nomic-embed-text

    log "All models pulled successfully."
    echo ""
    ollama list
}

# ---- Python environment ----
setup_python_env() {
    log "Setting up Python virtual environment..."

    cd "$PROJECT_DIR"

    python3 -m venv .venv
    source .venv/bin/activate

    pip install --upgrade pip -q

    if [ -f "requirements.txt" ]; then
        pip install -r requirements.txt -q
        log "Python dependencies installed."
    else
        warn "requirements.txt not found, installing core deps..."
        pip install -q \
            httpx \
            pyyaml \
            rich \
            click \
            chromadb \
            tree-sitter \
            tree-sitter-languages \
            watchdog
    fi

    log "Python env ready at: ${PROJECT_DIR}/.venv"
}

# ---- Install the agent as CLI ----
install_agent_cli() {
    log "Installing agent CLI..."

    cd "$PROJECT_DIR"
    source .venv/bin/activate

    pip install -e . -q 2>/dev/null || {
        warn "pyproject.toml not ready yet, skipping editable install."
        # Create a symlink for now
        AGENT_BIN="${HOME}/.local/bin/aide"
        mkdir -p "$(dirname "$AGENT_BIN")"
        cat > "$AGENT_BIN" << 'WRAPPER'
#!/usr/bin/env bash
SCRIPT_DIR="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
PROJECT_DIR="PLACEHOLDER_PROJECT_DIR"
source "${PROJECT_DIR}/.venv/bin/activate"
python -m agent.cli "$@"
WRAPPER
        sed -i "s|PLACEHOLDER_PROJECT_DIR|${PROJECT_DIR}|g" "$AGENT_BIN"
        chmod +x "$AGENT_BIN"
        log "CLI wrapper installed at: ${AGENT_BIN}"
    }

    # Add to PATH if needed
    if [[ ":$PATH:" != *":${HOME}/.local/bin:"* ]]; then
        echo 'export PATH="${HOME}/.local/bin:${PATH}"' >> ~/.bashrc
        warn "Added ~/.local/bin to PATH. Run: source ~/.bashrc"
    fi
}

# ---- Configure Ollama for network access ----
configure_network_access() {
    log "Configuring Ollama for LAN access..."

    # Create systemd override for Ollama to listen on all interfaces
    sudo mkdir -p /etc/systemd/system/ollama.service.d
    sudo tee /etc/systemd/system/ollama.service.d/override.conf > /dev/null << 'EOF'
[Service]
Environment="OLLAMA_HOST=0.0.0.0:11434"
Environment="OLLAMA_ORIGINS=*"
EOF

    sudo systemctl daemon-reload 2>/dev/null || true
    sudo systemctl restart ollama 2>/dev/null || {
        warn "systemd not available (WSL1?). Set OLLAMA_HOST=0.0.0.0 manually."
    }

    LOCAL_IP=$(hostname -I | awk '{print $1}')
    log "Ollama API available at: http://${LOCAL_IP}:11434"
    info "Agent API will be at: http://${LOCAL_IP}:8800"
}

# ---- Verify installation ----
verify() {
    log "Verifying installation..."

    echo ""
    echo "  ┌─────────────────────────────────────┐"
    echo "  │     Local AI Code Agent — Ready      │"
    echo "  ├─────────────────────────────────────┤"

    # Check Ollama
    if curl -sf http://localhost:11434/api/tags >/dev/null 2>&1; then
        echo "  │  ✓ Ollama service running           │"
    else
        echo "  │  ✗ Ollama service NOT running        │"
    fi

    # Check GPU
    if nvidia-smi >/dev/null 2>&1; then
        echo "  │  ✓ NVIDIA GPU accessible             │"
    else
        echo "  │  ✗ NVIDIA GPU not detected            │"
    fi

    # Check Python
    if [ -f "${PROJECT_DIR}/.venv/bin/python" ]; then
        echo "  │  ✓ Python venv ready                 │"
    else
        echo "  │  ✗ Python venv missing                │"
    fi

    # Check models
    MODEL_COUNT=$(ollama list 2>/dev/null | grep -c "qwen2.5-coder" || echo 0)
    echo "  │  ✓ Models installed: ${MODEL_COUNT}             │"

    echo "  ├─────────────────────────────────────┤"
    echo "  │  Usage:                              │"
    echo "  │    aide init <project-path>          │"
    echo "  │    aide review <file>                │"
    echo "  │    aide chat                         │"
    echo "  │    aide security <file>              │"
    echo "  └─────────────────────────────────────┘"
    echo ""
}

# ---- Main ----
main() {
    echo ""
    echo "  ╔═════════════════════════════════════╗"
    echo "  ║  Local AI Code Agent Setup (WSL2)   ║"
    echo "  ╠═════════════════════════════════════╣"
    echo "  ║  Qwen2.5-Coder-32B + 7B + RAG        ║"
    echo "  ║  Ollama + ChromaDB + Python          ║"
    echo "  ╚═════════════════════════════════════╝"
    echo ""

    check_prerequisites
    install_system_deps
    install_ollama
    pull_models
    setup_python_env
    install_agent_cli
    configure_network_access
    verify

    log "Setup complete! Run 'aide --help' to get started."
}

main "$@"
