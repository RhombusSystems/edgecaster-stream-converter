#!/usr/bin/env bash
# EdgeCaster updater — pull latest and restart
set -euo pipefail

INSTALL_DIR="/opt/edgecaster"

echo "=== EdgeCaster Update ==="

if [ ! -d "$INSTALL_DIR" ]; then
    echo "Error: EdgeCaster not installed at $INSTALL_DIR"
    echo "Run install.sh first."
    exit 1
fi

cd "$INSTALL_DIR"

# If it's a git repo, pull latest
if [ -d .git ]; then
    echo ">>> Pulling latest changes..."
    git pull --ff-only
else
    echo ">>> Not a git repository. For manual update, replace files in $INSTALL_DIR"
    echo ">>> Then re-run this script."
fi

# Update Python dependencies
echo ">>> Updating Python dependencies..."
"$INSTALL_DIR/venv/bin/pip" install --quiet -r requirements.txt

# Rebuild frontend
echo ">>> Rebuilding frontend..."
cd frontend
npm install --silent
npm run build
cd ..

# Fix permissions
chown -R edgecaster:edgecaster "$INSTALL_DIR"

# Restart services
echo ">>> Restarting services..."
systemctl restart mediamtx
systemctl restart edgecaster

echo ""
echo "=== EdgeCaster updated successfully ==="
echo "Check status: systemctl status edgecaster"
