#!/bin/sh
# Creates the symlinks and license files that the QNX installer would normally create.
# Run this inside the Docker container after mounting qnx650/ to /opt/qnx650.
set -eu

QNX_BIN="${QNX_HOST}/usr/bin"

# Create ntoarm-gcc symlink expected by build.sh
cd "$QNX_BIN"
for full in arm-unknown-nto-qnx6.5.0-gcc-4.4.2 arm-unknown-nto-qnx6.5.0-g++-4.4.2; do
    short=$(echo "$full" | sed 's/arm-unknown-nto-qnx6.5.0-/ntoarm-/' | sed 's/-4\.4\.2$//')
    if [ -f "$full" ] && [ ! -e "$short" ]; then
        ln -s "$full" "$short"
        echo "Created symlink: $short -> $full"
    fi
done

# Also create ntoarm-gcc (without version suffix) -> ntoarm-gcc-4.4.2 style
if [ -f "arm-unknown-nto-qnx6.5.0-gcc-4.4.2" ] && [ ! -e "ntoarm-gcc" ]; then
    ln -s "arm-unknown-nto-qnx6.5.0-gcc-4.4.2" "ntoarm-gcc"
    echo "Created symlink: ntoarm-gcc"
fi
if [ -f "arm-unknown-nto-qnx6.5.0-g++-4.4.2" ] && [ ! -e "ntoarm-g++" ]; then
    ln -s "arm-unknown-nto-qnx6.5.0-g++-4.4.2" "ntoarm-g++"
    echo "Created symlink: ntoarm-g++"
fi

# Generate a license file if the license generator exists
LICENSE_DIR="/opt/qnx650"
if [ -f "$LICENSE_DIR/activate_license.sh" ]; then
    echo "License activation script found. Running..."
    sh "$LICENSE_DIR/activate_license.sh" 2>/dev/null || true
fi

# Verify the toolchain works
echo ""
echo "=== Toolchain Verification ==="
echo "qcc location: $(which qcc 2>/dev/null || echo 'NOT FOUND')"
echo "ntoarm-gcc: $(which ntoarm-gcc 2>/dev/null || echo 'NOT FOUND')"
ntoarm-gcc -dumpversion 2>/dev/null || echo "ntoarm-gcc failed to run"
ntoarm-gcc -dumpmachine 2>/dev/null || echo "ntoarm-gcc failed dumpmachine"
echo "=== Done ==="
