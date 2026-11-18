#!/bin/bash
# Full head unit backup — run BEFORE installing any plugins.
# Usage: ./backup_headunit.sh 169.254.X.X [--legacy]
#
# Creates a timestamped backup directory with:
# - Firmware version and system info
# - Existing plugin directory (complete copy)
# - Framework libraries (needed for building)
# - iDrive configuration
# - Display resolution and HMI state
# - SHA256 checksums of everything

set -e

HEAD_IP="${1:?Usage: $0 HEAD_IP [--legacy]}"
LEGACY=""
if [ "$2" = "--legacy" ]; then
    LEGACY="-o HostKeyAlgorithms=+ssh-rsa -o KexAlgorithms=+diffie-hellman-group14-sha1,diffie-hellman-group1-sha1 -o Ciphers=+aes128-cbc,aes256-cbc,3des-cbc -o MACs=+hmac-sha1,hmac-sha1-96"
fi

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="$HOME/m5_backup_${TIMESTAMP}"
SSH_CMD="ssh -T -o StrictHostKeyChecking=accept-new -o ConnectTimeout=10 $LEGACY root@${HEAD_IP}"

echo "============================================"
echo "  BMW Head Unit Backup"
echo "  Target: ${HEAD_IP}"
echo "  Backup: ${BACKUP_DIR}"
echo "  Time:   $(date)"
echo "============================================"
echo ""

# Test connection
echo "[1/8] Testing SSH connection..."
$SSH_CMD 'echo "SSH OK: $(uname -a)"' || {
    echo "ERROR: Cannot SSH to ${HEAD_IP}"
    echo "Make sure:"
    echo "  1. ENET cable is plugged in"
    echo "  2. Bavarian SSH Client has been run"
    echo "  3. WiFi is OFF on your Mac"
    exit 1
}

mkdir -p "$BACKUP_DIR"

# System info
echo "[2/8] Capturing system info..."
$SSH_CMD 'uname -a' > "$BACKUP_DIR/uname.txt"
$SSH_CMD 'cat /opt/sys/etc/nbt_version.txt 2>/dev/null || cat /etc/nbt_version.txt 2>/dev/null || echo "UNKNOWN"' > "$BACKUP_DIR/firmware.txt"
$SSH_CMD 'df -h 2>/dev/null' > "$BACKUP_DIR/disk_usage.txt" 2>/dev/null || true
$SSH_CMD 'ps -ef 2>/dev/null' > "$BACKUP_DIR/processes.txt" 2>/dev/null || true
echo "  Firmware: $(cat $BACKUP_DIR/firmware.txt)"

# Display info
echo "[3/8] Capturing display resolution..."
$SSH_CMD '/opt/sys/bin/LayerManagerControl get screen 0 2>/dev/null' > "$BACKUP_DIR/display.txt" 2>/dev/null || {
    # Split-node: try via OMAP
    $SSH_CMD 'on -f hu-omap sh -c "export LD_LIBRARY_PATH=/opt/sys/lib:/usr/lib:/lib; /opt/sys/bin/LayerManagerControl get screen 0" 2>/dev/null' > "$BACKUP_DIR/display.txt" 2>/dev/null || echo "Could not read display info" > "$BACKUP_DIR/display.txt"
}
echo "  Display: $(cat $BACKUP_DIR/display.txt | head -1)"

# Framework libraries
echo "[4/8] Backing up framework libraries..."
mkdir -p "$BACKUP_DIR/frameworks"
$SSH_CMD 'cat /opt/hmi/ID5/lib/libAppFramework.A.so' > "$BACKUP_DIR/frameworks/libAppFramework.A.so" 2>/dev/null || {
    # Split-node fallback
    for qnet_path in "/net/hu-omap/fs/sda0/repository/istep/opt/hmi/ID5/lib" "/net/hu-omap/fs/sda0/opt/hmi/ID5/lib"; do
        $SSH_CMD "cat ${qnet_path}/libAppFramework.A.so 2>/dev/null" > "$BACKUP_DIR/frameworks/libAppFramework.A.so" 2>/dev/null && break
    done
}
$SSH_CMD 'cat /opt/hmi/ID5/lib/libCoreFramework.A.so' > "$BACKUP_DIR/frameworks/libCoreFramework.A.so" 2>/dev/null || {
    for qnet_path in "/net/hu-omap/fs/sda0/repository/istep/opt/hmi/ID5/lib" "/net/hu-omap/fs/sda0/opt/hmi/ID5/lib"; do
        $SSH_CMD "cat ${qnet_path}/libCoreFramework.A.so 2>/dev/null" > "$BACKUP_DIR/frameworks/libCoreFramework.A.so" 2>/dev/null && break
    done
}

# Verify frameworks are actual ELF files (not empty/error)
for lib in libAppFramework.A.so libCoreFramework.A.so; do
    size=$(wc -c < "$BACKUP_DIR/frameworks/$lib" 2>/dev/null || echo 0)
    if [ "$size" -lt 1000 ]; then
        echo "  WARNING: $lib is only ${size} bytes — may not have transferred correctly"
    else
        echo "  $lib: ${size} bytes OK"
    fi
done

# Existing plugins
echo "[5/8] Backing up existing plugins..."
mkdir -p "$BACKUP_DIR/plugins"
PLUGIN_LIST=$($SSH_CMD 'ls /var/opt/hmi/data/ID5/Plugins/ 2>/dev/null' || echo "")
if [ -z "$PLUGIN_LIST" ]; then
    echo "  No existing plugins found (clean install)"
else
    echo "  Found plugins: $PLUGIN_LIST"
    for plugin in $PLUGIN_LIST; do
        echo "  Backing up: $plugin"
        mkdir -p "$BACKUP_DIR/plugins/$plugin"
        # Get file list first
        files=$($SSH_CMD "ls /var/opt/hmi/data/ID5/Plugins/$plugin/ 2>/dev/null" || echo "")
        for f in $files; do
            $SSH_CMD "cat /var/opt/hmi/data/ID5/Plugins/$plugin/$f" > "$BACKUP_DIR/plugins/$plugin/$f" 2>/dev/null || true
        done
    done
fi

# HMI configuration
echo "[6/8] Backing up HMI configuration..."
mkdir -p "$BACKUP_DIR/config"
$SSH_CMD 'ls -la /var/opt/hmi/data/ID5/ 2>/dev/null' > "$BACKUP_DIR/config/id5_listing.txt" 2>/dev/null || true
$SSH_CMD 'cat /var/opt/hmi/data/ID5/Plugins/.settings 2>/dev/null' > "$BACKUP_DIR/config/plugin_settings.txt" 2>/dev/null || true

# Network info (for reference)
echo "[7/8] Capturing network info..."
$SSH_CMD 'ifconfig 2>/dev/null' > "$BACKUP_DIR/network.txt" 2>/dev/null || true

# Generate checksums
echo "[8/8] Generating checksums..."
cd "$BACKUP_DIR"
find . -type f ! -name "SHA256SUMS" -exec shasum -a 256 {} \; > SHA256SUMS
echo "  $(wc -l < SHA256SUMS | tr -d ' ') files checksummed"

echo ""
echo "============================================"
echo "  Backup complete: ${BACKUP_DIR}"
echo "  Firmware: $(cat firmware.txt)"
echo "  Plugins: $(echo $PLUGIN_LIST | wc -w | tr -d ' ') found"
echo "  Frameworks: $(ls frameworks/ | wc -l | tr -d ' ') libraries"
echo "============================================"
echo ""
echo "Framework hashes (needed for ABI audit):"
shasum -a 256 frameworks/*.so 2>/dev/null
echo ""
echo "NEXT STEPS:"
echo "  1. Copy frameworks to build directory:"
echo "     cp ${BACKUP_DIR}/frameworks/*.so ~/Projects/ID6_apps_prerelease/source/native/frameworks/"
echo "  2. Run ABI audit:"
echo "     cd ~/Projects/ID6_apps_prerelease/source"
echo "     python3 native/tools/audit_framework_abi.py \\"
echo "       --fingerprint native/framework-fingerprint.json \\"
echo "       --installed-dir ${BACKUP_DIR}/frameworks \\"
echo "       --plugin native/out/libBoostDeck.so \\"
echo "       --report ${BACKUP_DIR}/abi-report.json"
echo "  3. If audit passes, build the plugins:"
echo "     cd ~/Projects/ID6_apps_prerelease/source/native"
echo "     docker run --rm --platform linux/amd64 \\"
echo "       -v \"\$PWD/qnx650:/opt/qnx650\" -v \"\$PWD:/build\" \\"
echo "       qnx650-glass sh build_glass.sh"
