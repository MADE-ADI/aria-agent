#!/usr/bin/env bash
# ============================================================
#  Aria — AI Agent Installer
#  curl -sL https://raw.githubusercontent.com/MADE-ADI/aria-agent/master/install.sh | bash
# ============================================================
set -euo pipefail

REPO="https://github.com/MADE-ADI/aria-agent.git"
INSTALL_DIR="$HOME/.aria"
BIN_LINK="/usr/local/bin/aria"
BRANCH="master"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

info()  { echo -e "${CYAN}[INFO]${NC} $1"; }
ok()    { echo -e "${GREEN}[OK]${NC} $1"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
fail()  { echo -e "${RED}[FAIL]${NC} $1"; exit 1; }

echo ""
echo -e "${CYAN}╔══════════════════════════════════════╗${NC}"
echo -e "${CYAN}║  🤖 Aria — AI Agent Installer        ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════╝${NC}"
echo ""

# ---- Check dependencies ----
info "Checking dependencies..."

command -v python3 >/dev/null 2>&1 || fail "python3 not found. Install it first."
command -v pip3 >/dev/null 2>&1 || command -v pip >/dev/null 2>&1 || fail "pip not found. Install it first."
command -v git >/dev/null 2>&1 || fail "git not found. Install it first."

PYTHON_VER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
ok "Python $PYTHON_VER"

# ---- Clone or update ----
if [ -d "$INSTALL_DIR" ]; then
    info "Updating existing installation..."
    cd "$INSTALL_DIR"
    git pull --ff-only origin "$BRANCH" 2>/dev/null || {
        warn "Git pull failed, re-cloning..."
        cd /
        rm -rf "$INSTALL_DIR"
        git clone --depth 1 -b "$BRANCH" "$REPO" "$INSTALL_DIR"
    }
else
    info "Installing to $INSTALL_DIR..."
    git clone --depth 1 -b "$BRANCH" "$REPO" "$INSTALL_DIR"
fi
ok "Source ready at $INSTALL_DIR"

# ---- Install Python dependencies ----
info "Installing Python dependencies..."
cd "$INSTALL_DIR"

PIP_FLAGS=""
# Detect if we need --break-system-packages (PEP 668, Python 3.11+)
if python3 -c "import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)" 2>/dev/null; then
    PIP_FLAGS="--break-system-packages"
fi

pip3 install -q $PIP_FLAGS -r requirements.txt 2>/dev/null || pip install -q $PIP_FLAGS -r requirements.txt 2>/dev/null
ok "Dependencies installed"

# ---- Create launcher script ----
info "Creating 'aria' command..."

cat > "$INSTALL_DIR/aria" << 'LAUNCHER'
#!/usr/bin/env bash
# Aria launcher — run from anywhere
ARIA_HOME="${ARIA_HOME:-$HOME/.aria}"
cd "$ARIA_HOME"
exec python3 main.py "$@"
LAUNCHER

chmod +x "$INSTALL_DIR/aria"
chmod +x "$INSTALL_DIR/main.py"

# ---- Symlink to PATH ----
if [ -w "/usr/local/bin" ] || [ "$(id -u)" = "0" ]; then
    ln -sf "$INSTALL_DIR/aria" "$BIN_LINK"
    ok "Command installed: $BIN_LINK"
else
    # Try with sudo
    if command -v sudo >/dev/null 2>&1; then
        sudo ln -sf "$INSTALL_DIR/aria" "$BIN_LINK"
        ok "Command installed: $BIN_LINK (sudo)"
    else
        # Fallback to user bin
        USER_BIN="$HOME/.local/bin"
        mkdir -p "$USER_BIN"
        ln -sf "$INSTALL_DIR/aria" "$USER_BIN/aria"
        ok "Command installed: $USER_BIN/aria"
        warn "Add to PATH if needed: export PATH=\"\$HOME/.local/bin:\$PATH\""
    fi
fi

# ---- Config check ----
echo ""
if [ -z "${LLM_API_KEY:-}" ]; then
    warn "LLM_API_KEY not set. Configure before running:"
    echo ""
    echo "  Option 1: Set environment variables"
    echo "    export LLM_API_KEY=your-api-key"
    echo "    export LLM_MODEL=gpt-4o"
    echo "    export LLM_BASE_URL=https://api.openai.com/v1"
    echo ""
    echo "  Option 2: Edit config directly"
    echo "    nano $INSTALL_DIR/config/settings.py"
    echo ""
fi

# ---- Done ----
echo -e "${GREEN}╔══════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  ✅ Aria installed successfully!     ║${NC}"
echo -e "${GREEN}║                                      ║${NC}"
echo -e "${GREEN}║  Run:  aria                          ║${NC}"
echo -e "${GREEN}║  Help: aria --help                   ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════╝${NC}"
echo ""
