#!/bin/bash
# mesh-deploy.sh — Sovereign Stack Universal Node Deployer
# Usage: bash mesh-deploy.sh --role [model|gateway|web|operator]
# Or:    curl https://axismundi.fun/mesh-deploy.sh | bash -s -- --role model
#
# Owner: marcus / axismundi.fun

set -e

REPO="https://github.com/Kelushael/sovereign-stack.git"
MESH_GATEWAY="https://axismundi.fun"
SOV_KEY="SOV-A8FB-3C9A-570C-656B"
STACK_DIR="$HOME/sovereign-stack"
ROLE=""

# ── MESH TRUST KEY ────────────────────────────────────────────────────────────
# This is the sovereign mesh public key. Any node holding the private key
# (id_ollama on the entry node) can SSH in without a password.
# If you're inside the mesh, all doors are open. Zero friction, zero re-auth.
MESH_PUBKEY="ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIAo4YZ4eDIHVnH9eSkzkzjrsif6YhHLDXJgZYpgmQJAb ollama-agent"

install_mesh_trust() {
  mkdir -p ~/.ssh
  chmod 700 ~/.ssh
  touch ~/.ssh/authorized_keys
  chmod 600 ~/.ssh/authorized_keys
  # add mesh key if not already there
  if ! grep -qF "$MESH_PUBKEY" ~/.ssh/authorized_keys 2>/dev/null; then
    echo "$MESH_PUBKEY" >> ~/.ssh/authorized_keys
    echo "  ✓ mesh trust key installed — entry node has keyless access"
  else
    echo "  ✓ mesh trust key already present"
  fi
  # also ensure sshd allows pubkey auth
  sed -i 's/^#*PubkeyAuthentication.*/PubkeyAuthentication yes/' /etc/ssh/sshd_config 2>/dev/null || true
  systemctl reload sshd 2>/dev/null || service ssh reload 2>/dev/null || true
}

# ── parse args ──────────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
  case "$1" in
    --role)  ROLE="$2"; shift 2 ;;
    --trust) install_mesh_trust; echo "✅ Mesh trust installed on $(hostname -I | awk '{print $1}')"; exit 0 ;;
    *) shift ;;
  esac
done

# ── detect OS ────────────────────────────────────────────────────────────────
if command -v apt &>/dev/null; then
  PKG_MGR="apt"
  INSTALL="apt-get install -y -q"
  UPDATE="apt-get update -q"
elif command -v dnf &>/dev/null; then
  PKG_MGR="dnf"
  INSTALL="dnf install -y -q"
  UPDATE="dnf check-update -q || true"
else
  echo "❌ Unsupported OS"; exit 1
fi

echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║     SOVEREIGN STACK — MESH NODE DEPLOYER         ║"
echo "╚══════════════════════════════════════════════════╝"
echo "  Role    : $ROLE"
echo "  OS      : $PKG_MGR"
echo "  Host    : $(hostname)"
echo "  IP      : $(hostname -I | awk '{print $1}')"
echo ""

# ── auto-detect role if not provided ─────────────────────────────────────────
if [[ -z "$ROLE" ]]; then
  RAM=$(free -g | awk '/Mem:/{print $2}')
  CPUS=$(nproc)
  HAS_OLLAMA=$(command -v ollama 2>/dev/null && echo 1 || echo 0)
  HAS_NGINX=$(command -v nginx 2>/dev/null && echo 1 || echo 0)

  if [[ "$HAS_OLLAMA" == "1" ]]; then
    ROLE="model"
  elif [[ "$RAM" -ge 16 && "$CPUS" -ge 8 ]]; then
    ROLE="operator"
  elif [[ "$HAS_NGINX" == "1" ]]; then
    ROLE="web"
  else
    ROLE="web"
  fi
  echo "  ℞ Auto-detected role: $ROLE"
fi

# ── install base deps ────────────────────────────────────────────────────────
base_deps() {
  echo "→ Installing base dependencies..."
  $UPDATE >/dev/null 2>&1
  $INSTALL git python3 python3-pip curl wget unzip >/dev/null 2>&1
  echo "  ✓ base deps"
}

# ── clone / update sovereign stack ───────────────────────────────────────────
deploy_stack() {
  echo "→ Syncing sovereign-stack..."
  if [[ -d "$STACK_DIR/.git" ]]; then
    cd "$STACK_DIR" && git pull -q origin main
    echo "  ✓ updated"
  else
    git clone -q "$REPO" "$STACK_DIR"
    echo "  ✓ cloned"
  fi
}

# ── ROLE: model ──────────────────────────────────────────────────────────────
deploy_model() {
  echo ""
  echo "╔══════════════════════╗"
  echo "║   ROLE: MODEL NODE   ║"
  echo "╚══════════════════════╝"
  echo "  Pure inference. Nothing else."
  echo ""

  install_mesh_trust
  base_deps
  deploy_stack

  # install ollama
  if ! command -v ollama &>/dev/null; then
    echo "→ Installing ollama..."
    curl -fsSL https://ollama.ai/install.sh | sh >/dev/null 2>&1
    systemctl enable ollama --now 2>/dev/null || ollama serve &>/dev/null &
    sleep 3
    echo "  ✓ ollama installed"
  fi

  # pull models
  echo "→ Pulling models..."
  RAM=$(free -g | awk '/Mem:/{print $2}')
  if [[ $RAM -ge 32 ]]; then
    ollama pull dolphin-mistral:latest &
    ollama pull glm4:latest &
    wait
    echo "  ✓ dolphin-mistral + glm4 (32GB full stack)"
  elif [[ $RAM -ge 16 ]]; then
    ollama pull dolphin-mistral:latest
    echo "  ✓ dolphin-mistral (16GB)"
  elif [[ $RAM -ge 8 ]]; then
    ollama pull phi4:latest
    echo "  ✓ phi4 (8GB)"
  else
    ollama pull deepseek-r1:1.5b
    echo "  ✓ deepseek:1.5b (4GB nano)"
  fi

  # start amallo_controller
  echo "→ Starting amallo_controller..."
  APID=$(pgrep -f amallo_controller 2>/dev/null || true)
  [[ -n "$APID" ]] && kill "$APID" && sleep 1
  nohup python3 "$STACK_DIR/amallo_controller.py" > /tmp/amallo.log 2>&1 &
  sleep 2
  echo "  ✓ amallo_controller running (port 8200)"

  # nginx — SSL proxy only to 8200
  if command -v nginx &>/dev/null; then
    echo "→ Configuring nginx (inference proxy only)..."
    cat > /etc/nginx/sites-available/amallo << 'NGINX'
server {
    listen 80;
    server_name _;
    return 301 https://$host$request_uri;
}
server {
    listen 443 ssl;
    server_name _;
    ssl_certificate     /etc/ssl/amallo/cert.pem;
    ssl_certificate_key /etc/ssl/amallo/key.pem;
    location / {
        proxy_pass http://127.0.0.1:8200;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_read_timeout 300;
    }
}
NGINX
    echo "  ✓ nginx configured for inference proxy"
  fi

  echo ""
  echo "✅ MODEL NODE ready"
  echo "   Inference: http://$(hostname -I | awk '{print $1}'):8200/v1/chat/completions"
  echo "   Key: $SOV_KEY"
  echo "   Models: $(ollama list 2>/dev/null | tail -n+2 | awk '{print $1}' | tr '\n' ' ')"
}

# ── ROLE: gateway ─────────────────────────────────────────────────────────────
deploy_gateway() {
  echo ""
  echo "╔═══════════════════════════╗"
  echo "║   ROLE: GATEWAY NODE      ║"
  echo "╚═══════════════════════════╝"
  echo "  Routes all traffic to mesh. No compute here."
  echo ""

  install_mesh_trust
  base_deps
  deploy_stack

  # nginx on AlmaLinux or Ubuntu
  if [[ "$PKG_MGR" == "dnf" ]]; then
    $INSTALL nginx certbot python3-certbot-nginx >/dev/null 2>&1
  else
    $INSTALL nginx certbot python3-certbot-nginx >/dev/null 2>&1
  fi

  echo "→ Writing gateway nginx config..."
  cat > /etc/nginx/conf.d/sovereign-mesh.conf << 'NGINX'
# Sovereign Mesh Gateway — axismundi.fun
# Routes: /v1/ /amallo/ → model node
#         /clank /dashboard → web node
#         /operate /green-team → operator node

upstream model_node {
    server 187.77.208.28:443;
    keepalive 32;
}
upstream web_node {
    server 185.28.23.43:80;
    keepalive 16;
}
upstream operator_node {
    server 72.61.78.161:8300;
    keepalive 8;
}

server {
    listen 80;
    server_name axismundi.fun;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    server_name axismundi.fun;

    ssl_certificate     /etc/letsencrypt/live/axismundi.fun/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/axismundi.fun/privkey.pem;
    ssl_protocols       TLSv1.2 TLSv1.3;
    ssl_prefer_server_ciphers on;

    add_header Access-Control-Allow-Origin *;

    # AI inference
    location ~ ^/(v1|amallo)/ {
        proxy_pass https://model_node;
        proxy_ssl_verify off;
        proxy_set_header Host axismundi.fun;
        proxy_set_header Authorization $http_authorization;
        proxy_read_timeout 300;
    }

    # WebSocket vision
    location /v1/vision/ws {
        proxy_pass https://model_node;
        proxy_ssl_verify off;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 3600;
    }

    # Web UI
    location ~ ^/(clank|dashboard|assets) {
        proxy_pass http://web_node;
        proxy_set_header Host $host;
    }

    # Operator
    location ~ ^/(operate|green-team) {
        proxy_pass http://operator_node;
        proxy_set_header Host $host;
        proxy_read_timeout 300;
    }

    # Mesh deploy script
    location /mesh-deploy.sh {
        alias /root/sovereign-stack/tools/mesh-deploy.sh;
        add_header Content-Type text/plain;
    }

    # Root — serve amallo landing
    location / {
        proxy_pass http://web_node;
        proxy_set_header Host $host;
    }
}
NGINX

  nginx -t 2>/dev/null && systemctl reload nginx 2>/dev/null || \
    (nginx -t && nginx -s reload)
  echo "  ✓ gateway nginx configured"

  echo ""
  echo "✅ GATEWAY NODE ready"
  echo "   Routes: /v1/* → model | /clank → web | /operate → operator"
}

# ── ROLE: web ─────────────────────────────────────────────────────────────────
deploy_web() {
  echo ""
  echo "╔═══════════════════════╗"
  echo "║   ROLE: WEB NODE      ║"
  echo "╚═══════════════════════╝"
  echo "  Serves CLANK, dashboard, static assets."
  echo ""

  install_mesh_trust
  base_deps
  deploy_stack

  $INSTALL nginx >/dev/null 2>&1

  # copy clank.html to web root
  WEB_ROOT="/var/www/html"
  mkdir -p "$WEB_ROOT"
  cp "$STACK_DIR/clank.html" "$WEB_ROOT/clank.html"
  cp "$STACK_DIR/index.html" "$WEB_ROOT/index.html" 2>/dev/null || true

  echo "→ Writing web nginx config..."
  cat > /etc/nginx/sites-available/sovereign-web << 'NGINX'
server {
    listen 80 default_server;
    server_name _;
    root /var/www/html;
    index index.html;

    location /clank { try_files /clank.html =404; }
    location /health { return 200 '{"status":"ok","role":"web"}'; add_header Content-Type application/json; }
    location / { try_files $uri $uri/ /index.html; }
}
NGINX

  ln -sf /etc/nginx/sites-available/sovereign-web /etc/nginx/sites-enabled/sovereign-web 2>/dev/null || true
  rm -f /etc/nginx/sites-enabled/default 2>/dev/null || true
  nginx -t 2>/dev/null && systemctl reload nginx 2>/dev/null || \
    (nginx -t && nginx -s reload)

  echo "  ✓ CLANK served at http://$(hostname -I | awk '{print $1}')/clank"
  echo "  ✓ Dashboard at http://$(hostname -I | awk '{print $1}')/"

  echo ""
  echo "✅ WEB NODE ready"
}

# ── ROLE: operator ────────────────────────────────────────────────────────────
deploy_operator() {
  echo ""
  echo "╔════════════════════════════╗"
  echo "║   ROLE: OPERATOR NODE      ║"
  echo "╚════════════════════════════╝"
  echo "  axis relay, AXISCHROME, green-team, kernel-mustard."
  echo ""

  install_mesh_trust
  base_deps
  deploy_stack

  # Python deps for axis tools
  pip3 install playwright aiohttp websockets pillow --break-system-packages -q 2>/dev/null || \
    pip3 install playwright aiohttp websockets pillow -q 2>/dev/null || true

  # playwright chromium
  python3 -m playwright install chromium 2>/dev/null || true

  # start axis relay on port 8300
  echo "→ Starting axis relay..."
  RPID=$(pgrep -f axis_relay 2>/dev/null || true)
  [[ -n "$RPID" ]] && kill "$RPID" && sleep 1
  nohup python3 "$STACK_DIR/axis_relay.py" > /tmp/axis-relay.log 2>&1 &
  sleep 1
  echo "  ✓ axis relay (port 8300)"

  # start vision-ws if present
  if [[ -f "$STACK_DIR/tools/vision-ws.py" ]]; then
    VPID=$(pgrep -f vision-ws 2>/dev/null || true)
    [[ -n "$VPID" ]] && kill "$VPID" && sleep 1
    nohup python3 "$STACK_DIR/tools/vision-ws.py" > /tmp/vision-ws.log 2>&1 &
    sleep 1
    echo "  ✓ vision-ws (port 8201)"
  fi

  echo ""
  echo "✅ OPERATOR NODE ready"
  echo "   Relay:      http://$(hostname -I | awk '{print $1}'):8300"
  echo "   AXISCHROME: http://$(hostname -I | awk '{print $1}'):8600"
}

# ── DISPATCH ──────────────────────────────────────────────────────────────────
case "$ROLE" in
  model)    deploy_model    ;;
  gateway)  deploy_gateway  ;;
  web)      deploy_web      ;;
  operator) deploy_operator ;;
  *)
    echo "Usage: bash mesh-deploy.sh --role [model|gateway|web|operator]"
    echo ""
    echo "Nodes:"
    echo "  model    — 187.77.208.28 (srv1399361) — pure AI inference"
    echo "  gateway  — 76.13.24.113  (axismundi.fun) — nginx mesh router"
    echo "  web      — 185.28.23.43  (srv1397652) — CLANK UI, dashboard"
    echo "  operator — 72.61.78.161  (srv1339155) — axis relay, AXISCHROME"
    exit 1
    ;;
esac

echo ""
echo "Mesh registered at: $MESH_GATEWAY"
echo "Key: $SOV_KEY"
echo ""
echo "╔══════════════════════════════════╗"
echo "║  SOVEREIGN NODE ONLINE           ║"
echo "╚══════════════════════════════════╝"
