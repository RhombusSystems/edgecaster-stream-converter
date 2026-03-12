#!/usr/bin/env bash
# EdgeCaster installer — idempotent, run with sudo
set -euo pipefail

INSTALL_DIR="/opt/edgecaster"
CONFIG_DIR="/etc/edgecaster"
STATE_DIR="/var/lib/edgecaster"
LOG_DIR="/var/log/edgecaster"
SERVICE_USER="edgecaster"
MEDIAMTX_VERSION="1.9.3"

# Detect architecture
ARCH=$(uname -m)
case "$ARCH" in
    aarch64|arm64) MEDIAMTX_ARCH="arm64v8" ;;
    x86_64|amd64)  MEDIAMTX_ARCH="amd64" ;;
    armv7l)        MEDIAMTX_ARCH="armv7" ;;
    *)             echo "Unsupported architecture: $ARCH"; exit 1 ;;
esac

echo "=== EdgeCaster Installer ==="
echo "Install dir: $INSTALL_DIR"
echo "Architecture: $ARCH ($MEDIAMTX_ARCH)"

# 1. Install system dependencies
echo ">>> Installing system packages..."
apt-get update -qq
apt-get install -y -qq python3 python3-pip python3-venv ffmpeg nginx curl

# 2. Install MediaMTX if not present
if ! command -v mediamtx &>/dev/null && [ ! -f /usr/local/bin/mediamtx ]; then
    echo ">>> Installing MediaMTX v${MEDIAMTX_VERSION}..."
    MEDIAMTX_URL="https://github.com/bluenviron/mediamtx/releases/download/v${MEDIAMTX_VERSION}/mediamtx_v${MEDIAMTX_VERSION}_linux_${MEDIAMTX_ARCH}.tar.gz"
    TMP_DIR=$(mktemp -d)
    curl -sL "$MEDIAMTX_URL" -o "$TMP_DIR/mediamtx.tar.gz"
    tar -xzf "$TMP_DIR/mediamtx.tar.gz" -C "$TMP_DIR"
    install -m 755 "$TMP_DIR/mediamtx" /usr/local/bin/mediamtx
    rm -rf "$TMP_DIR"
    echo "MediaMTX installed to /usr/local/bin/mediamtx"
else
    echo ">>> MediaMTX already installed, skipping"
fi

# 3. Install Node.js if not present (for frontend build)
if ! command -v node &>/dev/null; then
    echo ">>> Installing Node.js..."
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
    apt-get install -y -qq nodejs
else
    echo ">>> Node.js already installed: $(node --version)"
fi

# 4. Create service user
if ! id "$SERVICE_USER" &>/dev/null; then
    echo ">>> Creating service user: $SERVICE_USER"
    useradd --system --shell /usr/sbin/nologin --home-dir "$INSTALL_DIR" "$SERVICE_USER"
else
    echo ">>> Service user $SERVICE_USER already exists"
fi

# 5. Create directories
echo ">>> Creating directories..."
mkdir -p "$CONFIG_DIR" "$STATE_DIR" "$LOG_DIR" "$INSTALL_DIR"

# 6. Copy application code
echo ">>> Installing application..."
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
rsync -a --exclude='.git' --exclude='node_modules' --exclude='venv' \
    --exclude='__pycache__' --exclude='data' --exclude='frontend/dist' \
    "$SCRIPT_DIR/" "$INSTALL_DIR/"

# 7. Create Python virtual environment and install deps
echo ">>> Setting up Python environment..."
python3 -m venv "$INSTALL_DIR/venv"
"$INSTALL_DIR/venv/bin/pip" install --quiet --upgrade pip
"$INSTALL_DIR/venv/bin/pip" install --quiet -r "$INSTALL_DIR/requirements.txt"

# 8. Build frontend
echo ">>> Building frontend..."
cd "$INSTALL_DIR/frontend"
npm install --silent
npm run build
cd -

# 9. Install default config if missing
if [ ! -f "$CONFIG_DIR/config.yaml" ]; then
    echo ">>> Installing default configuration..."
    cp "$INSTALL_DIR/packaging/edgecaster.default.yaml" "$CONFIG_DIR/config.yaml"
fi

# Install MediaMTX config
cp "$INSTALL_DIR/packaging/mediamtx.yml" "$CONFIG_DIR/mediamtx.yml"

# 10. Install Nginx config
echo ">>> Configuring Nginx..."
cp "$INSTALL_DIR/packaging/nginx.example.conf" /etc/nginx/sites-available/edgecaster
ln -sf /etc/nginx/sites-available/edgecaster /etc/nginx/sites-enabled/edgecaster
# Remove default site if it conflicts
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx

# 11. Set ownership
echo ">>> Setting permissions..."
chown -R "$SERVICE_USER:$SERVICE_USER" "$CONFIG_DIR" "$STATE_DIR" "$LOG_DIR" "$INSTALL_DIR"

# 12. Install systemd services
echo ">>> Installing systemd services..."
cp "$INSTALL_DIR/packaging/mediamtx.service" /etc/systemd/system/mediamtx.service
cp "$INSTALL_DIR/packaging/edgecaster.service" /etc/systemd/system/edgecaster.service
cp "$INSTALL_DIR/packaging/edgecaster-update.service" /etc/systemd/system/edgecaster-update.service
cp "$INSTALL_DIR/packaging/edgecaster-update.timer" /etc/systemd/system/edgecaster-update.timer

# Install logrotate config
cp "$INSTALL_DIR/packaging/edgecaster-logrotate.conf" /etc/logrotate.d/edgecaster

# Install first-boot service if sentinel exists
if [ -f "$INSTALL_DIR/.first-boot" ]; then
    cp "$INSTALL_DIR/packaging/edgecaster-firstboot.service" /etc/systemd/system/edgecaster-firstboot.service
fi

systemctl daemon-reload

# 13. Enable and start services
echo ">>> Starting services..."
systemctl enable mediamtx edgecaster edgecaster-update.timer
systemctl restart mediamtx
systemctl restart edgecaster
systemctl start edgecaster-update.timer

echo ""
echo "=== EdgeCaster installed successfully! ==="
echo ""
echo "Access the web UI at:"
echo "  http://$(hostname).local"
echo "  http://$(hostname -I | awk '{print $1}')"
echo ""
echo "RTSP streams will be available at:"
echo "  rtsp://$(hostname -I | awk '{print $1}'):8554/<camera_name>"
echo ""
echo "Logs: journalctl -u edgecaster -f"
echo "Config: $CONFIG_DIR/config.yaml"
