#!/usr/bin/env bash
# EdgeCaster uninstaller
set -euo pipefail

echo "=== EdgeCaster Uninstaller ==="

# Stop services
echo ">>> Stopping services..."
systemctl stop edgecaster mediamtx 2>/dev/null || true
systemctl disable edgecaster mediamtx 2>/dev/null || true

# Remove systemd units
echo ">>> Removing systemd units..."
rm -f /etc/systemd/system/edgecaster.service
rm -f /etc/systemd/system/mediamtx.service
systemctl daemon-reload

# Remove Nginx config
echo ">>> Removing Nginx config..."
rm -f /etc/nginx/sites-enabled/edgecaster
rm -f /etc/nginx/sites-available/edgecaster
nginx -t 2>/dev/null && systemctl reload nginx 2>/dev/null || true

# Remove application
echo ">>> Removing application files..."
rm -rf /opt/edgecaster

echo ""
echo "=== EdgeCaster uninstalled ==="
echo ""
echo "Configuration preserved at: /etc/edgecaster/"
echo "State data preserved at: /var/lib/edgecaster/"
echo "Logs preserved at: /var/log/edgecaster/"
echo ""
echo "To fully remove all data:"
echo "  sudo rm -rf /etc/edgecaster /var/lib/edgecaster /var/log/edgecaster"
echo "  sudo userdel edgecaster"
