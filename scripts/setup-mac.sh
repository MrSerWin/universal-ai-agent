#!/usr/bin/env bash
set -euo pipefail

# ============================================================
# aide — Local AI Code Agent — macOS Setup Script
#
# Requirements: macOS with Apple Silicon (M1/M2/M3/M4), 32GB+ RAM
#
# What this script does:
#   1. Checks hardware (chip, RAM)
#   2. Installs Homebrew (if missing) and system packages
#   3. Installs Ollama (LLM server)
#   4. Downloads models based on available RAM
#   5. Creates Python venv and installs dependencies
#   6. Installs the `aide` CLI command
#   7. Applies Mac-optimized model config
#
# Usage:
#   bash scripts/setup-mac.sh
#
# Time: ~20-40 minutes (mostly model downloads)
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

    # Check macOS
    if [[ "$(uname)" != "Darwin" ]]; then
        err "This script is for macOS only. Use setup-wsl.sh for Linux/WSL."
    fi

    # Check Apple Silicon
    CHIP=$(sysctl -n machdep.cpu.brand_string 2>/dev/null || echo "Unknown")
    if [[ "$CHIP" != *"Apple"* ]]; then
        warn "Intel Mac detected. Performance will be significantly worse than Apple Silicon."
        warn "Chip: ${CHIP}"
    else
        log "Chip: ${CHIP}"
    fi

    # Check RAM
    TOTAL_RAM_BYTES=$(sysctl -n hw.memsize)
    TOTAL_RAM_GB=$((TOTAL_RAM_BYTES / 1073741824))
    log "RAM: ${TOTAL_RAM_GB} GB (unified memory)"

    if [ "$TOTAL_RAM_GB" -lt 16 ]; then
        err "At least 16GB RAM required. You have ${TOTAL_RAM_GB}GB."
    elif [ "$TOTAL_RAM_GB" -lt 32 ]; then
        warn "32GB+ recommended for 32B models. You have ${TOTAL_RAM_GB}GB."
        warn "Will use smaller models."
    fi

    # Determine model tier
    if [ "$TOTAL_RAM_GB" -ge 96 ]; then
        MODEL_TIER="xl"    # 32B Q8 + 70B Q4
        log "Model tier: XL (32B Q8 + 70B available)"
    elif [ "$TOTAL_RAM_GB" -ge 64 ]; then
        MODEL_TIER="large"  # 32B Q8
        log "Model tier: Large (32B Q8)"
    elif [ "$TOTAL_RAM_GB" -ge 32 ]; then
        MODEL_TIER="medium" # 32B Q4
        log "Model tier: Medium (32B Q4)"
    else
        MODEL_TIER="small"  # 14B Q8
        log "Model tier: Small (14B Q8)"
    fi
}

# ---- Homebrew and system packages ----
install_system_deps() {
    log "Installing system dependencies..."

    # Install Homebrew if missing
    if ! command -v brew &>/dev/null; then
        log "Installing Homebrew..."
        /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    fi

    brew install python@3.12 jq git cmake 2>/dev/null || true
    log "System dependencies installed."
}

# ---- Ollama ----
install_ollama() {
    if ! command -v ollama &>/dev/null; then
        log "Installing Ollama..."

        # Check if Ollama.app exists
        if [ -d "/Applications/Ollama.app" ]; then
            log "Ollama.app found in Applications."
        else
            # Install via Homebrew (recommended on Mac)
            brew install ollama 2>/dev/null || {
                # Fallback: download from website
                info "Downloading Ollama from ollama.com..."
                curl -fsSL https://ollama.com/install.sh | sh
            }
        fi
    else
        log "Ollama already installed: $(ollama --version 2>/dev/null || echo 'unknown')"
    fi

    # Start Ollama service and wait until it's ready
    start_ollama_service
}

start_ollama_service() {
    # Check if already responding
    if curl -sf http://localhost:11434/api/tags >/dev/null 2>&1; then
        log "Ollama service already running."
        return
    fi

    log "Starting Ollama service..."

    # Try brew services first (cleanest on Mac)
    if command -v brew &>/dev/null; then
        brew services start ollama 2>/dev/null || true
    fi

    # If brew services didn't work, start manually
    if ! curl -sf http://localhost:11434/api/tags >/dev/null 2>&1; then
        ollama serve &>/dev/null &
        OLLAMA_PID=$!
        info "Started ollama serve (PID: ${OLLAMA_PID})"
    fi

    # Wait for Ollama to be ready (up to 30 seconds)
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

# ---- Pull models based on RAM tier ----
pull_models() {
    log "Pulling AI models (this will take a while)..."

    # Always pull: fast model + embeddings
    info "Pulling Qwen2.5-Coder 7B (Q8) — ~8GB..."
    ollama pull qwen2.5-coder:7b-instruct-q8_0 || {
        warn "Exact tag not found, trying default tag..."
        ollama pull qwen2.5-coder:7b
    }

    info "Pulling nomic-embed-text — ~0.3GB..."
    ollama pull nomic-embed-text

    # Tier-based primary model
    case "$MODEL_TIER" in
        xl|large)
            info "Pulling Qwen2.5-Coder 32B (Q8) — ~35GB..."
            ollama pull qwen2.5-coder:32b-instruct-q8_0 || {
                warn "Exact tag not found, trying default tag..."
                ollama pull qwen2.5-coder:32b
            }
            ;;
        medium)
            info "Pulling Qwen2.5-Coder 32B (Q4_K_M) — ~20GB..."
            ollama pull qwen2.5-coder:32b-instruct-q4_K_M || {
                warn "Exact tag not found, trying default tag..."
                ollama pull qwen2.5-coder:32b
            }
            ;;
        small)
            info "Pulling Qwen2.5-Coder 14B (Q8) — ~16GB..."
            ollama pull qwen2.5-coder:14b-instruct-q8_0 || {
                warn "Exact tag not found, trying default tag..."
                ollama pull qwen2.5-coder:14b
            }
            ;;
    esac

    # 70B for XL tier only
    if [ "$MODEL_TIER" = "xl" ]; then
        info "Pulling Llama 3.1 70B (Q4_K_M) — ~42GB..."
        info "This is optional. Press Ctrl+C to skip."
        ollama pull llama3.1:70b-instruct-q4_K_M || {
            warn "70B model skipped or not found."
        }
    fi

    log "All models pulled."
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
        warn "pyproject.toml not ready yet, creating wrapper..."
        AGENT_BIN="${HOME}/.local/bin/aide"
        mkdir -p "$(dirname "$AGENT_BIN")"
        cat > "$AGENT_BIN" << WRAPPER
#!/usr/bin/env bash
source "${PROJECT_DIR}/.venv/bin/activate"
python -m agent.cli "\$@"
WRAPPER
        chmod +x "$AGENT_BIN"
        log "CLI wrapper installed at: ${AGENT_BIN}"
    }

    # Add to PATH if needed
    SHELL_RC="${HOME}/.zshrc"
    if [[ ":$PATH:" != *":${HOME}/.local/bin:"* ]]; then
        echo 'export PATH="${HOME}/.local/bin:${PATH}"' >> "$SHELL_RC"
        warn "Added ~/.local/bin to PATH. Run: source ${SHELL_RC}"
    fi
}

# ---- Apply Mac-specific model config ----
apply_mac_config() {
    log "Applying Mac-optimized model config..."

    CONFIG_SRC="${PROJECT_DIR}/config/models-mac.yaml"
    CONFIG_DST="${PROJECT_DIR}/config/models.yaml"

    if [ -f "$CONFIG_SRC" ]; then
        cp "$CONFIG_SRC" "$CONFIG_DST"
        log "Config: models-mac.yaml → models.yaml"
    else
        warn "models-mac.yaml not found, keeping default config."
    fi

    # For small tier, override primary model
    if [ "$MODEL_TIER" = "small" ]; then
        info "Adjusting config for 16-31GB RAM (14B as primary)..."
        # Simple sed replacement for the primary model
        if command -v gsed &>/dev/null; then
            SED_CMD="gsed"
        else
            SED_CMD="sed"
        fi
        $SED_CMD -i.bak 's/qwen2.5-coder:32b-instruct-q8_0/qwen2.5-coder:14b-instruct-q8_0/g' "$CONFIG_DST"
        rm -f "${CONFIG_DST}.bak"
    elif [ "$MODEL_TIER" = "medium" ]; then
        info "Adjusting config for 32-63GB RAM (32B Q4 as primary)..."
        if command -v gsed &>/dev/null; then
            SED_CMD="gsed"
        else
            SED_CMD="sed"
        fi
        $SED_CMD -i.bak 's/qwen2.5-coder:32b-instruct-q8_0/qwen2.5-coder:32b-instruct-q4_K_M/g' "$CONFIG_DST"
        rm -f "${CONFIG_DST}.bak"
    fi
}

# ---- Verify installation ----
verify() {
    log "Verifying installation..."

    echo ""
    echo "  ┌──────────────────────────────────────┐"
    echo "  │   Local AI Code Agent — Ready (Mac)   │"
    echo "  ├──────────────────────────────────────┤"

    # Check Ollama
    if curl -sf http://localhost:11434/api/tags >/dev/null 2>&1; then
        echo "  │  ✓ Ollama service running            │"
    else
        echo "  │  ✗ Ollama service NOT running         │"
    fi

    # Check Metal
    if system_profiler SPDisplaysDataType 2>/dev/null | grep -q "Metal"; then
        echo "  │  ✓ Metal GPU support available        │"
    else
        echo "  │  ✗ Metal GPU not detected              │"
    fi

    # Check Python
    if [ -f "${PROJECT_DIR}/.venv/bin/python" ]; then
        echo "  │  ✓ Python venv ready                  │"
    else
        echo "  │  ✗ Python venv missing                 │"
    fi

    # Check models
    MODEL_COUNT=$(ollama list 2>/dev/null | grep -c "qwen2.5-coder" || echo 0)
    echo "  │  ✓ Models installed: ${MODEL_COUNT}              │"
    echo "  │  ✓ Model tier: ${MODEL_TIER}                     │"

    echo "  ├──────────────────────────────────────┤"
    echo "  │  Usage:                               │"
    echo "  │    aide init <project-path>           │"
    echo "  │    aide review <file>                 │"
    echo "  │    aide chat                          │"
    echo "  │    aide security <file>               │"
    echo "  └──────────────────────────────────────┘"
    echo ""
}

# ---- Main ----
main() {
    echo ""
    echo "  ╔══════════════════════════════════════╗"
    echo "  ║  Local AI Code Agent Setup (macOS)   ║"
    echo "  ╠══════════════════════════════════════╣"
    echo "  ║  Qwen2.5-Coder + RAG + Metal         ║"
    echo "  ║  Ollama + ChromaDB + Python           ║"
    echo "  ╚══════════════════════════════════════╝"
    echo ""

    check_prerequisites
    install_system_deps
    install_ollama
    pull_models
    setup_python_env
    install_agent_cli
    apply_mac_config
    verify

    log "Setup complete! Run 'aide --help' to get started."
}

main "$@"
