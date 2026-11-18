#!/bin/bash
# Profile the head unit — run AFTER backup, BEFORE installing anything.
# Tells us memory, storage, CPU, running processes, and ZIP size limits.
# Usage: ./profile_headunit.sh 169.254.X.X [--legacy]
set -e

HEAD_IP="${1:?Usage: $0 HEAD_IP [--legacy]}"
LEGACY=""
if [ "$2" = "--legacy" ]; then
    LEGACY="-o HostKeyAlgorithms=+ssh-rsa -o KexAlgorithms=+diffie-hellman-group14-sha1,diffie-hellman-group1-sha1 -o Ciphers=+aes128-cbc,aes256-cbc,3des-cbc -o MACs=+hmac-sha1,hmac-sha1-96"
fi

SSH_CMD="ssh -T -o StrictHostKeyChecking=accept-new -o ConnectTimeout=10 $LEGACY root@${HEAD_IP}"

echo "============================================"
echo "  Head Unit System Profile"
echo "  Target: ${HEAD_IP}"
echo "============================================"
echo ""

# System info
echo "=== PLATFORM ==="
$SSH_CMD 'uname -a' 2>/dev/null
echo ""

# CPU
echo "=== CPU ==="
$SSH_CMD 'pidin info 2>/dev/null || cat /proc/cpuinfo 2>/dev/null || echo "CPU info unavailable"' 2>/dev/null
echo ""

# Memory — this is what we need to know for ZIP size limits
echo "=== MEMORY ==="
$SSH_CMD 'pidin mem 2>/dev/null | head -5 || showmem 2>/dev/null | head -10 || echo "Memory info unavailable"' 2>/dev/null
echo ""
$SSH_CMD 'pidin info 2>/dev/null | grep -i mem || echo ""' 2>/dev/null
echo ""

# More detailed memory
echo "=== MEMORY (detailed) ==="
$SSH_CMD 'cat /proc/meminfo 2>/dev/null || pidin -F "%N %M" 2>/dev/null | head -20 || echo "Detailed memory unavailable"' 2>/dev/null
echo ""

# Disk / filesystem
echo "=== STORAGE ==="
$SSH_CMD 'df -h 2>/dev/null || df 2>/dev/null || echo "Storage info unavailable"' 2>/dev/null
echo ""

# Plugin directory space
echo "=== PLUGIN DIRECTORY ==="
$SSH_CMD 'ls -la /var/opt/hmi/data/ID5/Plugins/ 2>/dev/null || echo "No Plugins directory"' 2>/dev/null
echo ""
$SSH_CMD 'du -sh /var/opt/hmi/data/ID5/ 2>/dev/null || echo "Cannot measure ID5 directory"' 2>/dev/null
echo ""

# Running processes — see what's using memory
echo "=== TOP PROCESSES (by memory) ==="
$SSH_CMD 'pidin -F "%N %M %J" 2>/dev/null | sort -k2 -rn | head -20 || ps -ef 2>/dev/null | head -20 || echo "Process list unavailable"' 2>/dev/null
echo ""

# HMI process specifically
echo "=== HMI PROCESS ==="
$SSH_CMD 'pidin -F "%N %M %J" 2>/dev/null | grep -i hmi || ps -ef 2>/dev/null | grep -i hmi || echo "HMI process not found"' 2>/dev/null
echo ""

# Check for existing image ZIPs and their sizes
echo "=== EXISTING IMAGE ARCHIVES ==="
$SSH_CMD 'find /var/opt/hmi/data/ID5/Plugins -name "*_ALL_Images.zip" -exec ls -lh {} \; 2>/dev/null || echo "No image archives found"' 2>/dev/null
echo ""

# Check the filesystem type and mount options
echo "=== FILESYSTEM ==="
$SSH_CMD 'mount 2>/dev/null | head -20' 2>/dev/null
echo ""

# Check available temp space (for uploads)
echo "=== TEMP SPACE ==="
$SSH_CMD 'df -h /tmp 2>/dev/null || echo "Temp space unknown"' 2>/dev/null
echo ""

# Network interfaces
echo "=== NETWORK ==="
$SSH_CMD 'ifconfig 2>/dev/null | grep -A2 "^[a-z]" | head -20' 2>/dev/null
echo ""

# Check if this is a split-node unit
echo "=== NODE TYPE ==="
NODE=$($SSH_CMD 'uname -n 2>/dev/null' 2>/dev/null)
echo "Hostname: $NODE"
if echo "$NODE" | grep -qi jacinto; then
    echo "*** SPLIT-NODE DETECTED (Jacinto) ***"
    echo "SSH landed on Jacinto processor. HMI runs on OMAP."
    echo "Plugins install via Qnet path or OMAP SSH."
    $SSH_CMD 'ls /net/hu-omap/ 2>/dev/null && echo "Qnet path available" || echo "Qnet path not available"' 2>/dev/null
    $SSH_CMD 'on -f hu-omap uname -a 2>/dev/null || echo "Cannot reach OMAP"' 2>/dev/null
elif echo "$NODE" | grep -qi omap; then
    echo "Direct HMI node (OMAP) — standard install path"
else
    echo "Unknown node type — assuming standard install path"
fi
echo ""

# Display resolution
echo "=== DISPLAY ==="
$SSH_CMD '/opt/sys/bin/LayerManagerControl get screen 0 2>/dev/null' 2>/dev/null || \
$SSH_CMD 'on -f hu-omap sh -c "export LD_LIBRARY_PATH=/opt/sys/lib:/usr/lib:/lib; /opt/sys/bin/LayerManagerControl get screen 0" 2>/dev/null' 2>/dev/null || \
echo "Display info unavailable"
echo ""

# Summary
echo "============================================"
echo "  SUMMARY"
echo "============================================"
echo ""
echo "Key questions answered:"
echo "  1. Memory: Check 'MEMORY' section above"
echo "     - If total RAM > 1GB: Tier 3 (69MB) likely safe"
echo "     - If total RAM 512MB-1GB: Use Tier 2 (14MB)"
echo "     - If total RAM < 512MB: Use Tier 1 (7MB)"
echo ""
echo "  2. Storage: Check 'STORAGE' section"
echo "     - Need at least 100MB free for Tier 3"
echo "     - Need at least 30MB free for Tier 2"
echo "     - Need at least 15MB free for Tier 1"
echo ""
echo "  3. Display: Check 'DISPLAY' section"
echo "     - 1280x480 → use standard XMLs"
echo "     - 1440x540 → use _1440 XMLs"
echo ""
echo "  4. Node type: Check 'NODE TYPE' section"
echo "     - Standard → install to /var/opt/hmi/data/ID5/Plugins/"
echo "     - Split-node → need OMAP path for install"
echo ""
echo "  5. Speed-lock: Can only test by installing an app and driving"
