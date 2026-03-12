#!/usr/bin/env bash
# EdgeCaster first-boot setup — runs once after initial image flash
set -euo pipefail

LOG="/var/log/edgecaster/first-boot.log"
mkdir -p /var/log/edgecaster
exec &> >(tee -a "$LOG")

echo "=== EdgeCaster First Boot — $(date) ==="

# 1. Expand root partition to fill SD card
echo ">>> Expanding root filesystem..."
ROOT_DEV=$(findmnt -n -o SOURCE /)
ROOT_DISK=$(lsblk -no PKNAME "$ROOT_DEV")
ROOT_PART=$(echo "$ROOT_DEV" | grep -oP '\d+$')

if command -v growpart &>/dev/null; then
    growpart "/dev/$ROOT_DISK" "$ROOT_PART" || true
    resize2fs "$ROOT_DEV" || true
    echo "Root filesystem expanded"
else
    echo "growpart not found, skipping partition resize"
fi

# 2. Regenerate SSH host keys if missing
if [ ! -f /etc/ssh/ssh_host_ed25519_key ]; then
    echo ">>> Generating SSH host keys..."
    ssh-keygen -A
fi

# 3. Set hostname
echo ">>> Setting hostname to edgecaster..."
hostnamectl set-hostname edgecaster
echo "127.0.1.1 edgecaster" >> /etc/hosts

# 4. Enable services
echo ">>> Enabling EdgeCaster services..."
systemctl enable mediamtx edgecaster edgecaster-update.timer
systemctl start mediamtx
systemctl start edgecaster
systemctl start edgecaster-update.timer

# 5. Remove first-boot sentinel so this never runs again
echo ">>> Removing first-boot sentinel..."
rm -f /opt/edgecaster/.first-boot
systemctl disable edgecaster-firstboot.service

echo "=== First boot complete — $(date) ==="
