#!/usr/bin/env bash
# ============================================================
#  Aria — AI Agent Installer v1.3
#  curl -sL https://raw.githubusercontent.com/MADE-ADI/aria-agent/master/install.sh | bash
# ============================================================
set -euo pipefail

REPO="https://github.com/MADE-ADI/aria-agent.git"
ARIA_HOME="${ARIA_HOME:-$HOME/.aria}"
SRC_DIR="$ARIA_HOME/src"
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
echo -e "${CYAN}║  🤖 Aria — AI Agent Installer v1.3   ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════╝${NC}"
echo ""

# ---- Check dependencies ----
info "Checking dependencies..."

command -v python3 >/dev/null 2>&1 || fail "python3 not found. Install it first."
command -v pip3 >/dev/null 2>&1 || command -v pip >/dev/null 2>&1 || fail "pip not found. Install it first."
command -v git >/dev/null 2>&1 || fail "git not found. Install it first."

PYTHON_VER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
ok "Python $PYTHON_VER"

# ---- Create ~/.aria structure ----
info "Setting up ~/.aria ..."
mkdir -p "$ARIA_HOME"/{skills,memory,sessions,logs}

# ---- Clone or update source ----
if [ -d "$SRC_DIR/.git" ]; then
    info "Updating source code..."
    cd "$SRC_DIR"
    git pull --ff-only origin "$BRANCH" 2>/dev/null || {
        warn "Git pull failed, re-cloning..."
        cd /
        rm -rf "$SRC_DIR"
        git clone --depth 1 -b "$BRANCH" "$REPO" "$SRC_DIR"
    }
else
    # Handle upgrade from v1.2 (source was in ~/.aria directly)
    if [ -d "$ARIA_HOME/.git" ]; then
        info "Upgrading from v1.2 layout..."
        # Move git repo to src/
        mkdir -p "$SRC_DIR"
        # Move everything except user data dirs
        for item in "$ARIA_HOME"/*; do
            base=$(basename "$item")
            case "$base" in
                src|skills|memory|sessions|logs|config.yaml) continue ;;
                *) mv "$item" "$SRC_DIR/" 2>/dev/null || true ;;
            esac
        done
        # Move hidden git files
        for item in "$ARIA_HOME"/.[!.]*; do
            [ -e "$item" ] || continue
            base=$(basename "$item")
            case "$base" in
                .) continue ;;
                ..) continue ;;
                *) mv "$item" "$SRC_DIR/" 2>/dev/null || true ;;
            esac
        done
        cd "$SRC_DIR"
        git pull --ff-only origin "$BRANCH" 2>/dev/null || true
    else
        info "Cloning source to $SRC_DIR..."
        git clone --depth 1 -b "$BRANCH" "$REPO" "$SRC_DIR"
    fi
fi
ok "Source ready at $SRC_DIR"

# ---- Install Python dependencies ----
info "Installing Python dependencies..."
cd "$SRC_DIR"

PIP_FLAGS=""
if python3 -c "import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)" 2>/dev/null; then
    PIP_FLAGS="--break-system-packages"
fi

pip3 install -q $PIP_FLAGS -r requirements.txt 2>/dev/null || pip install -q $PIP_FLAGS -r requirements.txt 2>/dev/null
ok "Dependencies installed"

# ---- Create default config ----
if [ ! -f "$ARIA_HOME/config.yaml" ]; then
    info "Creating default config..."
    cat > "$ARIA_HOME/config.yaml" << 'CONFIG'
# ══════════════════════════════════════════
#  Aria — Configuration
#  Edit this file to customize your agent
# ══════════════════════════════════════════

# LLM Provider
llm:
  provider: openai
  api_key: ""            # or set LLM_API_KEY env var
  model: gpt-4o          # model name
  base_url: https://api.openai.com/v1

# Agent
agent:
  name: Aria
  max_iterations: 10

# Logging (DEBUG, INFO, WARNING, ERROR)
log_level: WARNING
CONFIG
    ok "Config created: $ARIA_HOME/config.yaml"
else
    ok "Config exists: $ARIA_HOME/config.yaml"
fi

# ---- Create launcher script ----
info "Creating 'aria' command..."

cat > "$ARIA_HOME/aria" << LAUNCHER
#!/usr/bin/env bash
# Aria launcher v1.3
ARIA_HOME="\${ARIA_HOME:-\$HOME/.aria}"
ARIA_SRC="\$ARIA_HOME/src"
cd "\$ARIA_SRC"
exec python3 main.py "\$@"
LAUNCHER

chmod +x "$ARIA_HOME/aria"

# ---- Symlink to PATH ----
if [ -w "/usr/local/bin" ] || [ "$(id -u)" = "0" ]; then
    ln -sf "$ARIA_HOME/aria" "$BIN_LINK"
    ok "Command installed: $BIN_LINK"
else
    if command -v sudo >/dev/null 2>&1; then
        sudo ln -sf "$ARIA_HOME/aria" "$BIN_LINK"
        ok "Command installed: $BIN_LINK (sudo)"
    else
        USER_BIN="$HOME/.local/bin"
        mkdir -p "$USER_BIN"
        ln -sf "$ARIA_HOME/aria" "$USER_BIN/aria"
        ok "Command installed: $USER_BIN/aria"
        warn "Add to PATH if needed: export PATH=\"\$HOME/.local/bin:\$PATH\""
    fi
fi

# ---- Create example user skill ----
EXAMPLE_SKILL="$ARIA_HOME/skills/hello"
if [ ! -d "$EXAMPLE_SKILL" ]; then
    mkdir -p "$EXAMPLE_SKILL"
    cat > "$EXAMPLE_SKILL/skill.json" << 'SKILLJSON'
{
    "name": "hello",
    "description": "A simple example skill — greets the user",
    "triggers": ["hello skill", "test skill", "example skill"],
    "parameters": {
        "name": {
            "type": "string",
            "description": "Name to greet",
            "required": false
        }
    },
    "examples": [
        "hello skill",
        "test skill"
    ]
}
SKILLJSON

    cat > "$EXAMPLE_SKILL/main.py" << 'SKILLPY'
"""Example user skill — copy this pattern to create your own!"""

def execute(name: str = "World", **kwargs) -> str:
    """Greet someone. This is a minimal skill example."""
    return f"Hello, {name}! 👋 This is a custom user skill from ~/.aria/skills/"
SKILLPY
    ok "Example skill created: ~/.aria/skills/hello/"
fi

# ---- Config check ----
echo ""
if [ -z "${LLM_API_KEY:-}" ]; then
    # Check if config has api_key set
    if grep -q 'api_key: ""' "$ARIA_HOME/config.yaml" 2>/dev/null; then
        warn "LLM_API_KEY not set. Configure before running:"
        echo ""
        echo "  Option 1: Edit config"
        echo "    nano ~/.aria/config.yaml"
        echo ""
        echo "  Option 2: Set environment variable"
        echo "    export LLM_API_KEY=your-api-key"
        echo ""
    fi
fi

# ---- Done ----
echo -e "${GREEN}╔══════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  ✅ Aria v1.3 installed!             ║${NC}"
echo -e "${GREEN}║                                      ║${NC}"
echo -e "${GREEN}║  Run:    aria                        ║${NC}"
echo -e "${GREEN}║  Help:   aria --help                 ║${NC}"
echo -e "${GREEN}║  Config: ~/.aria/config.yaml         ║${NC}"
echo -e "${GREEN}║  Skills: ~/.aria/skills/             ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════╝${NC}"
echo ""
echo "  ~/.aria/"
echo "  ├── config.yaml    ← your settings"
echo "  ├── skills/        ← custom skills go here"
echo "  ├── memory/        ← agent memory"
echo "  ├── sessions/      ← session history"
echo "  └── src/           ← source code (auto-updated)"
echo ""
