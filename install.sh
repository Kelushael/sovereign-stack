#!/usr/bin/env bash
# ╔══════════════════════════════════════════════════════════════════╗
# ║  SOV — SOVEREIGN STACK  ·  ZERO-FAIL UNIVERSAL INSTALLER        ║
# ║                                                                  ║
# ║  Linux / macOS:                                                  ║
# ║    curl -fsSL https://raw.githubusercontent.com/Kelushael/      ║
# ║    sovereign-stack/main/install.sh | bash                        ║
# ║                                                                  ║
# ║  Windows (PowerShell as Admin):                                  ║
# ║    iwr https://raw.githubusercontent.com/Kelushael/             ║
# ║    sovereign-stack/main/install.ps1 -OutFile i.ps1; .\i.ps1     ║
# ╚══════════════════════════════════════════════════════════════════╝

set -euo pipefail

ORG='\033[38;2;255;120;0m'
AMB='\033[38;2;255;180;0m'
YEL='\033[38;2;255;240;0m'
GRN='\033[38;2;0;255;157m'
RED='\033[38;2;255;70;70m'
DIM='\033[38;2;80;50;20m'
RST='\033[0m'
BOLD='\033[1m'
W=58

say()  { printf "  ${AMB}▸${RST}  %s\n" "$*"; }
ok()   { printf "  ${GRN}✓${RST}  %s\n" "$*"; }
warn() { printf "  ${YEL}⚠${RST}  %s\n" "$*"; }
fail() { printf "  ${RED}✗${RST}  %s\n" "$*"; exit 1; }
sep()  { printf "  ${ORG}"; printf '─%.0s' $(seq 1 $W); printf "${RST}\n"; }

printf "\n${ORG}${BOLD}"
printf "  ╔══════════════════════════════════════════════════════════╗\n"
printf "  ║  SOV  ·  SOVEREIGN STACK  ·  INSTALLER                  ║\n"
printf "  ║  AMALLO ENGINE  ·  axismundi.fun  ·  zero config         ║\n"
printf "  ╚══════════════════════════════════════════════════════════╝\n"
printf "${RST}\n"

REPO="https://github.com/Kelushael/sovereign-stack"
INSTALL_DIR="$HOME/.sovereign"
BIN_DIR="$HOME/.local/bin"
GIT_FALLBACK=0
PY=""

OS="$(uname -s 2>/dev/null || echo Windows)"
say "OS: ${OS}"
sep

# ── PURGE OLD CONFLICTING SCRIPTS ────────────────────────────────────────────
say "Removing old sovereign scripts that conflict with new sov stack…"
OLD_CMDS="sovereign cherub herald node sov-exec amallo axis marshal nexus oracle"
for cmd in $OLD_CMDS; do
  for loc in "$BIN_DIR/$cmd" "/usr/local/bin/$cmd" "/usr/bin/$cmd"; do
    if [[ -f "$loc" ]]; then
      rm -f "$loc" && warn "removed old: $loc"
    fi
  done
done
# remove old pip-installed packages that may conflict
for pkg in sovereign-stack amallo-agent sovereign-agent; do
  python3 -m pip uninstall -y "$pkg" 2>/dev/null || true
done
ok "Old scripts purged"
sep

# ── PYTHON ────────────────────────────────────────────────────────────────────
say "Checking Python 3.10+…"
for candidate in python3.12 python3.11 python3.10 python3 python; do
  if command -v "$candidate" &>/dev/null; then
    if "$candidate" -c "import sys; assert sys.version_info>=(3,10)" 2>/dev/null; then
      PY="$candidate"; ok "Python: $($PY --version)"; break
    fi
  fi
done

if [[ -z "$PY" ]]; then
  warn "Python 3.10+ not found — installing…"
  case "$OS" in
    Linux)
      command -v apt-get &>/dev/null && sudo apt-get update -qq && sudo apt-get install -y python3 python3-pip python3-venv -qq
      command -v dnf     &>/dev/null && sudo dnf install -y python3 python3-pip
      command -v pacman  &>/dev/null && sudo pacman -Sy --noconfirm python python-pip
      ;;
    Darwin)
      command -v brew &>/dev/null && brew install python@3.12 || warn "Install Homebrew: https://brew.sh"
      ;;
  esac
  for candidate in python3.12 python3.11 python3.10 python3 python; do
    if command -v "$candidate" &>/dev/null; then
      if "$candidate" -c "import sys; assert sys.version_info>=(3,10)" 2>/dev/null; then
        PY="$candidate"; break
      fi
    fi
  done
  [[ -z "$PY" ]] && fail "Python 3.10+ required. Install: https://python.org"
  ok "Python: $($PY --version)"
fi

# ── PIP ───────────────────────────────────────────────────────────────────────
say "Checking pip…"
$PY -m pip --version &>/dev/null || \
  $PY -m ensurepip --upgrade 2>/dev/null || \
  curl -fsSL https://bootstrap.pypa.io/get-pip.py | $PY
ok "pip ready"

# ── GIT ───────────────────────────────────────────────────────────────────────
say "Checking git…"
if ! command -v git &>/dev/null; then
  warn "git missing — installing…"
  command -v apt-get &>/dev/null && sudo apt-get install -y git -qq || true
  command -v dnf     &>/dev/null && sudo dnf install -y git || true
  command -v pacman  &>/dev/null && sudo pacman -Sy --noconfirm git || true
  command -v brew    &>/dev/null && brew install git || true
fi
command -v git &>/dev/null && ok "git: $(git --version)" || { warn "git unavailable — zip fallback"; GIT_FALLBACK=1; }
sep

# ── CLONE / UPDATE ────────────────────────────────────────────────────────────
say "Installing sovereign-stack to ${INSTALL_DIR}…"

if [[ "$GIT_FALLBACK" == "1" ]]; then
  ZIP="${REPO}/archive/refs/heads/main.zip"
  TMP="/tmp/sov-main.zip"
  curl -fsSL "$ZIP" -o "$TMP" || \
    $PY -c "import urllib.request; urllib.request.urlretrieve('${ZIP}','${TMP}')"
  $PY -c "
import zipfile, shutil, os
z = zipfile.ZipFile('${TMP}')
z.extractall('/tmp/')
src = '/tmp/sovereign-stack-main'
dst = '${INSTALL_DIR}'
if os.path.exists(dst): shutil.rmtree(dst)
shutil.copytree(src, dst)
"
  ok "Downloaded and extracted"
elif [[ -d "$INSTALL_DIR/.git" ]]; then
  say "Updating existing install…"
  git -C "$INSTALL_DIR" fetch origin main --quiet
  git -C "$INSTALL_DIR" reset --hard origin/main --quiet
  ok "Updated to latest"
else
  [[ -d "$INSTALL_DIR" ]] && rm -rf "$INSTALL_DIR"
  git clone --quiet "$REPO" "$INSTALL_DIR"
  ok "Cloned sovereign-stack"
fi
sep

# ── PIP INSTALL ───────────────────────────────────────────────────────────────
say "Registering sov commands (pip install -e .)…"
cd "$INSTALL_DIR"
$PY -m pip install -e . -q 2>/dev/null || \
$PY -m pip install -e . -q --user 2>/dev/null || \
$PY -m pip install -e . -q --break-system-packages 2>/dev/null || \
fail "pip install failed. Run manually: cd $INSTALL_DIR && $PY -m pip install -e ."
ok "sov, sov-ide, sov-ui, sov-ggufwomb registered"

# ── RUNTIME DEPS ──────────────────────────────────────────────────────────────
say "Installing runtime deps…"
$PY -m pip install -q requests 2>/dev/null && ok "requests" || warn "requests failed (retry manually)"
for dep in fastapi uvicorn httpx; do
  $PY -m pip install -q "$dep" 2>/dev/null || true
done
ok "Optional deps attempted (failures are silent — features degrade gracefully)"
sep

# ── PATH ──────────────────────────────────────────────────────────────────────
say "Wiring PATH…"
mkdir -p "$BIN_DIR"
for rc in "$HOME/.bashrc" "$HOME/.zshrc" "$HOME/.profile" "$HOME/.bash_profile"; do
  [[ -f "$rc" ]] || [[ "$rc" == "$HOME/.bashrc" ]] || continue
  grep -q ".local/bin" "$rc" 2>/dev/null || \
    echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$rc"
done
# try system-wide symlinks (non-fatal)
for cmd in sov sov-ide sov-ui sov-ggufwomb; do
  src=$(command -v "$cmd" 2>/dev/null || true)
  [[ -n "$src" && -w "/usr/local/bin" ]] && ln -sfn "$src" "/usr/local/bin/$cmd" 2>/dev/null || true
done
ok "PATH wired"

# ── DEFAULT CONFIG ────────────────────────────────────────────────────────────
CFG="$HOME/.config/axis-mundi"
mkdir -p "$CFG"
if [[ ! -f "$CFG/config.json" ]]; then
  cat > "$CFG/config.json" << 'EOF'
{
  "server":     "https://axismundi.fun",
  "model":      "axis-model",
  "ui_port":    7071,
  "ide_port":   7070,
  "womb_port":  8300,
  "sandbox_dir":"~/.sov/sandbox"
}
EOF
  ok "Config written → $CFG/config.json"
else
  ok "Config exists — not overwritten"
fi
sep

# ── DONE ──────────────────────────────────────────────────────────────────────
printf "\n${GRN}${BOLD}"
printf "  ╔══════════════════════════════════════════════════════════╗\n"
printf "  ║  ✓  SOVEREIGN STACK INSTALLED                           ║\n"
printf "  ╚══════════════════════════════════════════════════════════╝\n"
printf "${RST}\n"
printf "  ${GRN}✓${RST}  ${AMB}sov${RST}              →  AMALLO CLI agent\n"
printf "  ${GRN}✓${RST}  ${AMB}sov --ui${RST}         →  agent + live preview window\n"
printf "  ${GRN}✓${RST}  ${AMB}sov --ide${RST}        →  full IDE\n"
printf "  ${GRN}✓${RST}  ${AMB}sov --womb${RST}       →  GGUF model server\n"
printf "  ${GRN}✓${RST}  ${AMB}sov --fast${RST}       →  skip boot animation\n"
printf "\n  ${YEL}Reload shell:${RST}  source ~/.bashrc\n"
printf "  ${YEL}Then just:${RST}     ${ORG}${BOLD}sov${RST}\n\n"

set -euo pipefail

# ── colours ──────────────────────────────────────────────────────────────────
ORG='\033[38;2;255;120;0m'
AMB='\033[38;2;255;180;0m'
YEL='\033[38;2;255;240;0m'
GRN='\033[38;2;0;255;157m'
RED='\033[38;2;255;70;70m'
DIM='\033[38;2;80;50;20m'
RST='\033[0m'
BOLD='\033[1m'

W=60
bar(){ printf "${ORG}"; printf '█%.0s' $(seq 1 $1); printf "${DIM}"; printf '░%.0s' $(seq 1 $(($W-$1))); printf "${RST}"; }

say()  { printf "  ${AMB}▸${RST}  $*\n"; }
ok()   { printf "  ${GRN}✓${RST}  $*\n"; }
warn() { printf "  ${YEL}⚠${RST}  $*\n"; }
fail() { printf "  ${RED}✗${RST}  $*\n"; exit 1; }
sep()  { printf "  ${ORG}$(printf '─%.0s' $(seq 1 $W))${RST}\n"; }

# ── banner ────────────────────────────────────────────────────────────────────
printf "\n${ORG}${BOLD}"
printf "  ╔══════════════════════════════════════════════════════════╗\n"
printf "  ║  SOV  ·  SOVEREIGN STACK  ·  INSTALLER                  ║\n"
printf "  ║  AMALLO ENGINE  ·  axismundi.fun  ·  zero config         ║\n"
printf "  ╚══════════════════════════════════════════════════════════╝\n"
printf "${RST}\n"

REPO="https://github.com/Kelushael/sovereign"
INSTALL_DIR="$HOME/.sovereign"
BIN_DIR="$HOME/.local/bin"
PY=""

# ── detect OS ─────────────────────────────────────────────────────────────────
OS="$(uname -s 2>/dev/null || echo Windows)"
say "Detected OS: ${OS}"
sep

# ── step 1: ensure Python 3.10+ ───────────────────────────────────────────────
say "Checking Python…"
for candidate in python3.12 python3.11 python3.10 python3 python; do
  if command -v "$candidate" &>/dev/null; then
    ver=$("$candidate" -c "import sys; print(sys.version_info[:2])" 2>/dev/null)
    if "$candidate" -c "import sys; assert sys.version_info>=(3,10)" 2>/dev/null; then
      PY="$candidate"
      ok "Python: $($PY --version)"
      break
    fi
  fi
done

if [[ -z "$PY" ]]; then
  warn "Python 3.10+ not found — installing…"
  case "$OS" in
    Linux)
      if command -v apt-get &>/dev/null; then
        sudo apt-get update -qq && sudo apt-get install -y python3 python3-pip python3-venv 2>/dev/null
      elif command -v dnf &>/dev/null; then
        sudo dnf install -y python3 python3-pip 2>/dev/null
      elif command -v pacman &>/dev/null; then
        sudo pacman -Sy --noconfirm python python-pip 2>/dev/null
      fi
      ;;
    Darwin)
      if command -v brew &>/dev/null; then
        brew install python@3.12 2>/dev/null
      else
        warn "Install Homebrew first: https://brew.sh"
        warn "Then re-run this installer."
        # try system python anyway
        true
      fi
      ;;
  esac
  # re-check
  for candidate in python3.12 python3.11 python3.10 python3 python; do
    if command -v "$candidate" &>/dev/null; then
      if "$candidate" -c "import sys; assert sys.version_info>=(3,10)" 2>/dev/null; then
        PY="$candidate"; break
      fi
    fi
  done
  [[ -z "$PY" ]] && fail "Could not find or install Python 3.10+. Install manually: https://python.org"
  ok "Python: $($PY --version)"
fi

# ── step 2: ensure pip ────────────────────────────────────────────────────────
say "Checking pip…"
if ! $PY -m pip --version &>/dev/null; then
  warn "pip missing — bootstrapping via ensurepip…"
  $PY -m ensurepip --upgrade 2>/dev/null || \
  curl -fsSL https://bootstrap.pypa.io/get-pip.py | $PY 2>/dev/null || \
  fail "Cannot install pip. Run: $PY -m ensurepip"
fi
ok "pip: $($PY -m pip --version | cut -d' ' -f1-2)"

# ── step 3: ensure git ────────────────────────────────────────────────────────
say "Checking git…"
if ! command -v git &>/dev/null; then
  warn "git missing — installing…"
  case "$OS" in
    Linux)
      if command -v apt-get &>/dev/null; then sudo apt-get install -y git -qq; fi
      if command -v dnf     &>/dev/null; then sudo dnf install -y git; fi
      if command -v pacman  &>/dev/null; then sudo pacman -Sy --noconfirm git; fi
      ;;
    Darwin)
      command -v brew &>/dev/null && brew install git || \
      warn "Install Xcode CLI tools: xcode-select --install"
      ;;
  esac
fi
if command -v git &>/dev/null; then
  ok "git: $(git --version)"
else
  # fallback: download zip without git
  warn "git unavailable — will download zip instead"
  GIT_FALLBACK=1
fi

sep

# ── step 4: clone / update repo ───────────────────────────────────────────────
say "Installing sovereign stack to ${INSTALL_DIR}…"

if [[ "${GIT_FALLBACK:-0}" == "1" ]]; then
  ZIP_URL="${REPO}/archive/refs/heads/main.zip"
  TMP_ZIP="/tmp/sovereign-main.zip"
  say "Downloading zip: ${ZIP_URL}"
  curl -fsSL "$ZIP_URL" -o "$TMP_ZIP" 2>/dev/null || \
  $PY -c "import urllib.request; urllib.request.urlretrieve('${ZIP_URL}','${TMP_ZIP}')"
  $PY -c "import zipfile,shutil; z=zipfile.ZipFile('${TMP_ZIP}'); z.extractall('/tmp/'); shutil.copytree('/tmp/sovereign-main','${INSTALL_DIR}',dirs_exist_ok=True)"
  ok "Downloaded and extracted"
elif [[ -d "$INSTALL_DIR/.git" ]]; then
  say "Updating existing install…"
  git -C "$INSTALL_DIR" pull --ff-only --quiet
  ok "Updated to latest"
else
  [[ -d "$INSTALL_DIR" ]] && rm -rf "$INSTALL_DIR"
  git clone --quiet "$REPO" "$INSTALL_DIR"
  ok "Cloned to ${INSTALL_DIR}"
fi

# ── step 5: pip install -e . ──────────────────────────────────────────────────
sep
say "Installing Python package (sov entry points)…"

# try normal install, fall back to --user, fall back to --break-system-packages
cd "$INSTALL_DIR"
$PY -m pip install -e . -q 2>/dev/null || \
$PY -m pip install -e . -q --user 2>/dev/null || \
$PY -m pip install -e . -q --break-system-packages 2>/dev/null || \
fail "pip install failed. Try: cd $INSTALL_DIR && $PY -m pip install -e ."

ok "sovereign-stack installed"

# ── step 6: core python deps (non-fatal) ─────────────────────────────────────
say "Installing runtime deps (non-fatal)…"
DEPS="requests"
OPTIONAL="fastapi uvicorn httpx pyrealsense2 opencv-python"

$PY -m pip install -q $DEPS 2>/dev/null && ok "core deps: $DEPS" || warn "Some core deps failed (retry manually)"

for dep in $OPTIONAL; do
  $PY -m pip install -q "$dep" 2>/dev/null && true || true
done
ok "Optional deps attempted (missing ones are silent — features degrade gracefully)"

# ── step 7: PATH ──────────────────────────────────────────────────────────────
sep
say "Wiring PATH…"
mkdir -p "$BIN_DIR"

# find where pip put the entry points
SOV_BIN=$(command -v sov 2>/dev/null || $PY -c "import sysconfig; print(sysconfig.get_path('scripts'))" 2>/dev/null || echo "$BIN_DIR")

for shell_rc in "$HOME/.bashrc" "$HOME/.zshrc" "$HOME/.profile" "$HOME/.bash_profile"; do
  if [[ -f "$shell_rc" ]] || [[ "$shell_rc" == "$HOME/.bashrc" ]]; then
    if ! grep -q "$BIN_DIR" "$shell_rc" 2>/dev/null; then
      echo "export PATH=\"$BIN_DIR:\$PATH\"" >> "$shell_rc"
    fi
    if ! grep -q ".local/bin" "$shell_rc" 2>/dev/null; then
      echo "export PATH=\"\$HOME/.local/bin:\$PATH\"" >> "$shell_rc"
    fi
  fi
done
ok "PATH updated in shell profiles"

# also symlink into /usr/local/bin if writable (makes it available system-wide without PATH change)
for cmd in sov sov-ide sov-ui sov-ggufwomb; do
  src=$(command -v "$cmd" 2>/dev/null || echo "")
  if [[ -n "$src" ]] && [[ -w "/usr/local/bin" ]]; then
    ln -sfn "$src" "/usr/local/bin/$cmd" 2>/dev/null && true || true
  fi
done

# ── step 8: write config ──────────────────────────────────────────────────────
sep
say "Writing default config…"
CONFIG_DIR="$HOME/.config/axis-mundi"
mkdir -p "$CONFIG_DIR"

if [[ ! -f "$CONFIG_DIR/config.json" ]]; then
  cat > "$CONFIG_DIR/config.json" << 'EOF'
{
  "server": "https://axismundi.fun",
  "model": "axis-model",
  "ui_port": 7071,
  "ide_port": 7070,
  "womb_port": 8300,
  "sandbox_dir": "~/.sov/sandbox"
}
EOF
  ok "Config written to $CONFIG_DIR/config.json"
else
  ok "Config already exists — not overwritten"
fi

# ── done ──────────────────────────────────────────────────────────────────────
sep
printf "\n${GRN}${BOLD}"
printf "  ╔══════════════════════════════════════════════════════════╗\n"
printf "  ║  ✓  SOVEREIGN STACK INSTALLED                           ║\n"
printf "  ╚══════════════════════════════════════════════════════════╝\n"
printf "${RST}\n"

ok "  sov              →  AMALLO CLI agent"
ok "  sov --ui         →  agent + preview window"
ok "  sov --ide        →  full IDE"
ok "  sov --womb       →  GGUF model server"
ok "  sov --fast       →  skip boot animation"

printf "\n  ${YEL}Reload your shell or run:${RST}\n"
printf "  ${ORG}source ~/.bashrc${RST}   (Linux/macOS)\n"
printf "\n  ${AMB}Then just type:  ${ORG}${BOLD}sov${RST}\n\n"

