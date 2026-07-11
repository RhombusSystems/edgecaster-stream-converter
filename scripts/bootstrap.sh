#!/usr/bin/env bash
# EdgeCaster one-line bootstrap installer.
#
# Run on any Debian/Ubuntu Linux machine (Raspberry Pi, mini-PC, VM):
#
#   curl -fsSL https://raw.githubusercontent.com/RhombusSystems/edgecaster-stream-converter/main/scripts/bootstrap.sh | sudo bash
#
# It installs git if needed, downloads EdgeCaster, and runs the full installer.
# Trouble? Email support@rhombus.com
set -euo pipefail

REPO="https://github.com/RhombusSystems/edgecaster-stream-converter.git"
SRC="/opt/edgecaster-src"

if [ "$(id -u)" -ne 0 ]; then
    echo "Please run with sudo:  curl -fsSL <url>/scripts/bootstrap.sh | sudo bash"
    exit 1
fi

echo "=== EdgeCaster Bootstrap ==="

# 1. Ensure git is available.
if ! command -v git >/dev/null 2>&1; then
    echo ">>> Installing git..."
    apt-get update -qq
    apt-get install -y -qq git
fi

# 2. Fetch the latest EdgeCaster source.
echo ">>> Downloading EdgeCaster..."
if [ -d "$SRC/.git" ]; then
    git -C "$SRC" fetch origin main --quiet
    git -C "$SRC" reset --hard origin/main --quiet
else
    rm -rf "$SRC"
    git clone --quiet "$REPO" "$SRC"
fi

# 3. Run the installer (handles all dependencies and services).
echo ">>> Running installer..."
bash "$SRC/scripts/install.sh"

echo ""
echo "=== Done! Open http://$(hostname -I | awk '{print $1}') in a browser. ==="
echo "Need help? Email support@rhombus.com"
