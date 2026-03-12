#!/usr/bin/env bash
# build-image.sh — Build an EdgeCaster SD card image for Raspberry Pi 5
#
# Usage:
#   sudo ./iso/build-image.sh                  # Cloud-init mode (needs internet on first boot)
#   sudo ./iso/build-image.sh --prebaked       # Pre-baked mode (larger image, no internet needed)
#
# Output: edgecaster-<version>.img.xz  (flashable with Pi Imager)
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
WORK_DIR="$(mktemp -d)"

# Ubuntu Server 24.04 LTS for arm64 (Raspberry Pi)
UBUNTU_VERSION="24.04.2"
UBUNTU_URL="https://cdimage.ubuntu.com/releases/${UBUNTU_VERSION}/release/ubuntu-${UBUNTU_VERSION}-preinstalled-server-arm64+raspi.img.xz"
UBUNTU_IMG="ubuntu-${UBUNTU_VERSION}-preinstalled-server-arm64+raspi.img"

VERSION=$(git -C "$PROJECT_DIR" describe --tags --always 2>/dev/null || echo "dev")
OUTPUT_NAME="edgecaster-${VERSION}.img"
PREBAKED=false

trap 'cleanup' EXIT

cleanup() {
    echo ">>> Cleaning up..."
    # Unmount if mounted
    if mountpoint -q "$WORK_DIR/mnt/boot" 2>/dev/null; then
        umount "$WORK_DIR/mnt/boot" || true
    fi
    if mountpoint -q "$WORK_DIR/mnt/root" 2>/dev/null; then
        umount "$WORK_DIR/mnt/root" || true
    fi
    # Detach loop devices
    if [ -n "${LOOP_DEV:-}" ]; then
        kpartx -d "$LOOP_DEV" 2>/dev/null || true
        losetup -d "$LOOP_DEV" 2>/dev/null || true
    fi
    rm -rf "$WORK_DIR"
}

usage() {
    echo "Usage: sudo $0 [--prebaked]"
    echo ""
    echo "  --prebaked    Pre-install all packages inside the image (larger, no internet needed)"
    echo "  (default)     Cloud-init mode: installs on first boot (smaller, needs internet)"
    exit 1
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        --prebaked) PREBAKED=true; shift ;;
        -h|--help) usage ;;
        *) echo "Unknown option: $1"; usage ;;
    esac
done

# Must run as root
if [[ $EUID -ne 0 ]]; then
    echo "Error: This script must be run as root (sudo)"
    exit 1
fi

# Check dependencies
for cmd in wget xz losetup kpartx mount; do
    if ! command -v "$cmd" &>/dev/null; then
        echo "Error: Required command '$cmd' not found. Install it first."
        exit 1
    fi
done

echo "=== EdgeCaster Image Builder ==="
echo "Version:  $VERSION"
echo "Mode:     $([ "$PREBAKED" = true ] && echo "Pre-baked" || echo "Cloud-init")"
echo "Work dir: $WORK_DIR"
echo ""

# 1. Download base image
echo ">>> Downloading Ubuntu Server ${UBUNTU_VERSION} arm64..."
if [ -f "/tmp/$UBUNTU_IMG.xz" ]; then
    echo "    (using cached download)"
    cp "/tmp/$UBUNTU_IMG.xz" "$WORK_DIR/"
else
    wget -q --show-progress -O "$WORK_DIR/$UBUNTU_IMG.xz" "$UBUNTU_URL"
    cp "$WORK_DIR/$UBUNTU_IMG.xz" "/tmp/$UBUNTU_IMG.xz"
fi

echo ">>> Decompressing image..."
xz -d "$WORK_DIR/$UBUNTU_IMG.xz"

# 2. Set up loop device and mount
echo ">>> Mounting image..."
LOOP_DEV=$(losetup --find --show --partscan "$WORK_DIR/$UBUNTU_IMG")
echo "    Loop device: $LOOP_DEV"

# Wait for partitions to appear
sleep 1
kpartx -a "$LOOP_DEV"

# Find partition devices (p1 = boot, p2 = root)
MAPPER_NAME=$(basename "$LOOP_DEV")
BOOT_PART="/dev/mapper/${MAPPER_NAME}p1"
ROOT_PART="/dev/mapper/${MAPPER_NAME}p2"

# Wait for devices
for i in $(seq 1 10); do
    [ -e "$BOOT_PART" ] && [ -e "$ROOT_PART" ] && break
    sleep 1
done

if [ ! -e "$BOOT_PART" ] || [ ! -e "$ROOT_PART" ]; then
    echo "Error: Partition devices not found"
    ls -la /dev/mapper/ || true
    exit 1
fi

mkdir -p "$WORK_DIR/mnt/boot" "$WORK_DIR/mnt/root"
mount "$ROOT_PART" "$WORK_DIR/mnt/root"
mount "$BOOT_PART" "$WORK_DIR/mnt/boot"

# 3. Inject cloud-init configs
echo ">>> Injecting cloud-init configuration..."
cp "$SCRIPT_DIR/cloud-init/user-data" "$WORK_DIR/mnt/boot/user-data"
cp "$SCRIPT_DIR/cloud-init/network-config" "$WORK_DIR/mnt/boot/network-config"
cp "$SCRIPT_DIR/cloud-init/meta-data" "$WORK_DIR/mnt/boot/meta-data"

# 4. Pre-baked mode: chroot and install everything
if [ "$PREBAKED" = true ]; then
    echo ">>> Pre-baked mode: installing packages inside image..."

    # Check for qemu-aarch64-static
    if [ ! -f /usr/bin/qemu-aarch64-static ]; then
        echo "Error: qemu-aarch64-static not found. Install qemu-user-static."
        exit 1
    fi

    cp /usr/bin/qemu-aarch64-static "$WORK_DIR/mnt/root/usr/bin/"

    # Bind system mounts for chroot
    mount --bind /dev "$WORK_DIR/mnt/root/dev"
    mount --bind /dev/pts "$WORK_DIR/mnt/root/dev/pts"
    mount --bind /proc "$WORK_DIR/mnt/root/proc"
    mount --bind /sys "$WORK_DIR/mnt/root/sys"
    mount --bind "$WORK_DIR/mnt/boot" "$WORK_DIR/mnt/root/boot/firmware"

    # Copy resolver
    cp /etc/resolv.conf "$WORK_DIR/mnt/root/etc/resolv.conf"

    # Clone repo and run installer inside chroot
    chroot "$WORK_DIR/mnt/root" /bin/bash -c "
        export DEBIAN_FRONTEND=noninteractive
        apt-get update -qq
        apt-get install -y -qq git python3 python3-pip python3-venv ffmpeg nginx curl nodejs npm

        git clone https://github.com/RhombusSystems/edgecaster-stream-converter.git /opt/edgecaster
        touch /opt/edgecaster/.first-boot
        cd /opt/edgecaster && bash scripts/install.sh
    "

    # Unmount bind mounts
    umount "$WORK_DIR/mnt/root/boot/firmware" || true
    umount "$WORK_DIR/mnt/root/sys" || true
    umount "$WORK_DIR/mnt/root/proc" || true
    umount "$WORK_DIR/mnt/root/dev/pts" || true
    umount "$WORK_DIR/mnt/root/dev" || true
    rm -f "$WORK_DIR/mnt/root/usr/bin/qemu-aarch64-static"

    # Remove cloud-init user-data (not needed for pre-baked)
    rm -f "$WORK_DIR/mnt/boot/user-data"
fi

# 5. Unmount and compress
echo ">>> Unmounting..."
sync
umount "$WORK_DIR/mnt/boot"
umount "$WORK_DIR/mnt/root"
kpartx -d "$LOOP_DEV"
losetup -d "$LOOP_DEV"
LOOP_DEV=""

echo ">>> Compressing image..."
xz -T0 -9 "$WORK_DIR/$UBUNTU_IMG"
mv "$WORK_DIR/$UBUNTU_IMG.xz" "$PROJECT_DIR/$OUTPUT_NAME.xz"

echo ""
echo "=== Build complete ==="
echo "Output: $PROJECT_DIR/$OUTPUT_NAME.xz"
echo ""
echo "Flash with Pi Imager or:"
echo "  xz -d $OUTPUT_NAME.xz && sudo dd if=$OUTPUT_NAME of=/dev/sdX bs=4M status=progress"
