#!/usr/bin/env bash
# EdgeCaster auto-updater — checks update window, pulls latest, rebuilds, restarts.
# Designed to be run hourly via systemd timer.
set -euo pipefail

INSTALL_DIR="/opt/edgecaster"
CONFIG_FILE="/etc/edgecaster/config.yaml"
LOG_FILE="/var/log/edgecaster/update.log"
LOCK_FILE="/var/run/edgecaster-update.lock"

log() { echo "$(date '+%Y-%m-%d %H:%M:%S') $*" >> "$LOG_FILE"; }

# Ensure log directory exists
mkdir -p "$(dirname "$LOG_FILE")"

# Use flock to prevent concurrent runs
exec 200>"$LOCK_FILE"
if ! flock -n 200; then
    log "Another update is already running, skipping."
    exit 0
fi

# Check if EdgeCaster is installed
if [ ! -d "$INSTALL_DIR" ]; then
    log "Error: EdgeCaster not installed at $INSTALL_DIR"
    exit 1
fi

# Read update configuration from config.yaml
if [ -f "$CONFIG_FILE" ]; then
    read_config() {
        python3 -c "
import yaml, sys
with open('$CONFIG_FILE') as f:
    cfg = yaml.safe_load(f) or {}
print(cfg.get('auto_update_enabled', True))
print(cfg.get('update_hour_start', 2))
print(cfg.get('update_hour_end', 5))
"
    }
    CONFIG_OUTPUT=$(read_config 2>/dev/null || echo -e "True\n2\n5")
    AUTO_UPDATE_ENABLED=$(echo "$CONFIG_OUTPUT" | sed -n '1p')
    UPDATE_HOUR_START=$(echo "$CONFIG_OUTPUT" | sed -n '2p')
    UPDATE_HOUR_END=$(echo "$CONFIG_OUTPUT" | sed -n '3p')
else
    AUTO_UPDATE_ENABLED="True"
    UPDATE_HOUR_START=2
    UPDATE_HOUR_END=5
fi

# Check if auto-update is enabled
if [ "$AUTO_UPDATE_ENABLED" = "False" ] || [ "$AUTO_UPDATE_ENABLED" = "false" ]; then
    exit 0
fi

# Check if current hour is within the update window
CURRENT_HOUR=$(date +%-H)

in_window() {
    local now=$1 start=$2 end=$3
    if [ "$start" -le "$end" ]; then
        # Normal range: e.g., 2-5 means hours 2,3,4
        [ "$now" -ge "$start" ] && [ "$now" -lt "$end" ]
    else
        # Wraparound: e.g., 22-4 means hours 22,23,0,1,2,3
        [ "$now" -ge "$start" ] || [ "$now" -lt "$end" ]
    fi
}

if ! in_window "$CURRENT_HOUR" "$UPDATE_HOUR_START" "$UPDATE_HOUR_END"; then
    exit 0
fi

cd "$INSTALL_DIR"

# Only proceed if it's a git repo
if [ ! -d .git ]; then
    log "Not a git repository, skipping auto-update."
    exit 0
fi

# Check if there are actually new commits
git fetch origin main --quiet 2>/dev/null || { log "Git fetch failed"; exit 0; }
if git diff --quiet HEAD origin/main 2>/dev/null; then
    # No changes
    exit 0
fi

log "New updates available, starting update..."

# Pull latest
if ! git pull --ff-only --quiet 2>>"$LOG_FILE"; then
    log "Error: git pull failed (possible merge conflict). Manual intervention needed."
    exit 1
fi

# Update Python dependencies
log "Updating Python dependencies..."
"$INSTALL_DIR/venv/bin/pip" install --quiet -r requirements.txt 2>>"$LOG_FILE"

# Rebuild frontend
log "Rebuilding frontend..."
cd frontend
npm install --silent 2>>"$LOG_FILE"
npm run build 2>>"$LOG_FILE"
cd ..

# Fix permissions
chown -R edgecaster:edgecaster "$INSTALL_DIR"

# Restart services
log "Restarting services..."
systemctl restart mediamtx
systemctl restart edgecaster

log "Update completed successfully."
