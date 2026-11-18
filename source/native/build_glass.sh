#!/bin/sh
# Build the glass-upgrade iDrive 6 plugins.
# Runs inside Docker (qnx650-glass image) with the QNX EABI toolchain.
# Requires: native/frameworks/libAppFramework.A.so and libCoreFramework.A.so
# (pulled from the head unit via SSH — see BUILD.md)
set -eu
cd "$(dirname "$0")"

frameworks="${NBTEVO_FRAMEWORKS_DIR:-$PWD/frameworks}"
runtime="${NBTEVO_RUNTIME_DIR:-$PWD/runtime}"
for lib in libAppFramework.A.so libCoreFramework.A.so; do
    test -f "$frameworks/$lib" || {
        echo "Missing: $frameworks/$lib"
        echo ""
        echo "You need to pull these from your head unit via SSH:"
        echo "  ssh root@HEAD_IP 'cat /opt/hmi/ID5/lib/$lib' > frameworks/$lib"
        echo ""
        echo "See BUILD.md for details."
        exit 1
    }
done

BIN="$QNX_HOST/usr/bin"
TARGET="$QNX_TARGET"

# Set up EABI cross-tools directory
CROSS_DIR="$QNX_HOST/usr/arm-unknown-nto-qnx6.5.0eabi/bin"
mkdir -p "$CROSS_DIR"
for tool in as ld ar nm objcopy strip ranlib; do
    versioned=$(ls "$BIN/arm-unknown-nto-qnx6.5.0eabi-${tool}-"* 2>/dev/null | head -1)
    [ -n "$versioned" ] && ln -sf "$versioned" "$CROSS_DIR/${tool}"
done

# Create prefixed symlinks without version suffix
cd "$BIN"
for tool in as ld ar nm; do
    versioned="arm-unknown-nto-qnx6.5.0eabi-${tool}-2.19"
    [ -f "$versioned" ] && ln -sf "$versioned" "arm-unknown-nto-qnx6.5.0eabi-${tool}"
done
ln -sf arm-unknown-nto-qnx6.5.0eabi-gcc-4.4.2 ntoarm-gcc
ln -sf arm-unknown-nto-qnx6.5.0eabi-g++-4.4.2 ntoarm-g++

# Replace system assembler with QNX ARM one
cp "$BIN/arm-unknown-nto-qnx6.5.0eabi-as-2.19" /usr/bin/as

cd /build

# Compiler wrappers using EABI GCC directly (bypasses qcc license)
GCC="arm-unknown-nto-qnx6.5.0eabi-gcc-4.4.2"
GXX="arm-unknown-nto-qnx6.5.0eabi-g++-4.4.2"
SYSROOT="--sysroot=$TARGET"

c() { $GCC $SYSROOT -Wc,-std=c99 -Wall -Wextra -Werror "$@"; }
cxx() { $GXX $SYSROOT -lang-c++ -std=gnu++98 -Wall -Wextra -Werror "$@"; }

mkdir -p out

# Runtime library symlinks
for pair in libm.so:libm.so.2 libsocket.so:libsocket.so.3 libstdc++.so:libstdc++.so.6; do
    name=${pair%:*}
    versioned=${pair#*:}
    if test -f "$runtime/$versioned"; then ln -sf "$runtime/$versioned" "out/$name"; fi
done

echo "=== Compiler version ==="
ntoarm-gcc -dumpversion
ntoarm-gcc -dumpmachine

echo "=== Building BoostDeck ==="
# gauge_core.o
c -DPERF_LAB -Isrc -O2 -fPIC -c src/gauge_core.c -o out/core.o
echo "  gauge_core.o OK"

# libBoostDeck.so (plugin shared library)
cxx -DPERF_LAB -Isrc -Isdk -O2 -fno-strict-aliasing -fno-exceptions -fPIC -shared src/plugin.cpp out/core.o \
    "$frameworks/libAppFramework.A.so" "$frameworks/libCoreFramework.A.so" -Lout -lm -lsocket \
    -Wl,--allow-shlib-undefined -Wl,-soname,libBoostDeck.so -o out/libBoostDeck.so
echo "  libBoostDeck.so OK"

# boostdeck-collector-qnx (diagnostic worker)
worker() { c -Isrc -O2 "$@" src/diag_link.c src/most/*.c -Lout -lm -lsocket; }
worker -DNATIVE_FAST -DPERF_LAB src/collector.c out/core.o -o out/boostdeck-collector-qnx
echo "  boostdeck-collector-qnx OK"

echo "=== Building ShiftDeck ==="
cxx -DNATIVE_SHIFT_SMOOTH -Isrc -Isdk -O2 -fno-strict-aliasing -fno-exceptions -fPIC -shared \
    -DSHIFT_DECK_ONLY src/plugin.cpp \
    "$frameworks/libAppFramework.A.so" "$frameworks/libCoreFramework.A.so" -Lout -lm -lsocket \
    -Wl,--allow-shlib-undefined -Wl,-soname,libShiftDeck.so -o out/libShiftDeck.so 2>&1 || \
    echo "  ShiftDeck plugin: skipped (may need SHIFT_DECK_ONLY in separate source)"

# ShiftDeck uses collector.c with SHIFT_DECK_ONLY
worker -DNATIVE_FAST -DNATIVE_SHIFT_SMOOTH -DSHIFT_DECK_ONLY src/collector.c out/core.o -o out/shift-deck-qnx 2>&1 || \
    echo "  shift-deck-qnx: skipped"
echo "  ShiftDeck build attempted"

echo "=== Building EngineCodes ==="
# engine-codes worker
worker -DENGINE_CODES_ONLY src/collector.c -o out/engine-codes-qnx 2>&1 || \
    echo "  engine-codes-qnx: skipped"

# libEngineCodes.so
cxx -DENGINE_CODES_ONLY -Isrc -Isdk -O2 -fno-strict-aliasing -fno-exceptions -fPIC -shared \
    src/engine_codes.cpp \
    "$frameworks/libAppFramework.A.so" "$frameworks/libCoreFramework.A.so" -Lout -lm -lsocket \
    -Wl,--allow-shlib-undefined -Wl,-soname,libEngineCodes.so -o out/libEngineCodes.so 2>&1 || \
    echo "  libEngineCodes.so: skipped"
echo "  EngineCodes build attempted"

echo ""
echo "=== Build complete ==="
ls -la out/*.so out/*-qnx 2>/dev/null
echo ""
echo "Output binaries in native/out/"
file out/*.so out/*-qnx 2>/dev/null
