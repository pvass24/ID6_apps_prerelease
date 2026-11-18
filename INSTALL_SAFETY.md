# Glass Upgrade — Safe Installation Guide

## Prerequisites Checklist

Before going to the car, confirm:
- [ ] Bavarian SSH Client downloaded on laptop
- [ ] ENET cable (OBD2 → Ethernet) in hand
- [ ] Laptop charged or plugged in
- [ ] Car parked in a safe location (garage preferred)
- [ ] At least 30 minutes of uninterrupted time
- [ ] This repo cloned on laptop: `~/Projects/ID6_apps_prerelease`

---

## Phase 1: Connect & Verify (Read-Only — Zero Risk)

### Step 1: Enable SSH
1. Park the car, keep iDrive awake (don't let it sleep)
2. Connect ENET cable: laptop Ethernet → car OBD2 port
3. Open Bavarian SSH Client, follow its F90 instructions
4. Note the head unit SSH IP (169.254.X.X) and credentials

### Step 2: Capture Head Unit Info
```bash
cd ~/Projects/ID6_apps_prerelease/source

python3 tools/capture_headunit.py \
  --head 169.254.X.X \
  --out ~/m5_capture \
  --include-frameworks \
  --legacy
```

This is **read-only** — it only reads firmware version, display resolution, and framework hashes. Nothing is written.

**CHECK**: Review `~/m5_capture/compatibility.json`:
- `firmware`: should be an NBTevo_XXXXXXX code
- `display.width` × `display.height`: your screen resolution
- `frameworks`: SHA-256 hashes of both framework libraries

### Step 3: Run ABI Compatibility Audit
```bash
pip3 install pyelftools capstone

python3 native/tools/audit_framework_abi.py \
  --fingerprint native/framework-fingerprint.json \
  --installed-dir ~/m5_capture \
  --plugin native/out/libBoostDeck.so \
  --report ~/m5_capture/abi-report.json
```

**🛑 STOP GATE**: If the audit reports INCOMPATIBLE symbols or vtable mismatches, **DO NOT INSTALL**. The head unit framework doesn't match. Open a GitHub issue with your firmware code and the report.

**✅ PROCEED**: If the audit passes (all symbols matched, vtables aligned).

### Step 4: Pull Framework Libraries (For Building Plugins)
```bash
mkdir -p native/frameworks

ssh root@169.254.X.X 'cat /opt/hmi/ID5/lib/libAppFramework.A.so' > native/frameworks/libAppFramework.A.so
ssh root@169.254.X.X 'cat /opt/hmi/ID5/lib/libCoreFramework.A.so' > native/frameworks/libCoreFramework.A.so

# Verify they match the hashes from Step 2
shasum -a 256 native/frameworks/*.so
```

### Step 5: Build the Plugins
```bash
cd native

docker run --rm --platform linux/amd64 \
  -v "$PWD/qnx650:/opt/qnx650" \
  -v "$PWD:/build" \
  qnx650-glass sh build_glass.sh
```

**CHECK**: All binaries should be ARM EABI5 executables:
```bash
file native/out/*.so native/out/*-qnx
```

---

## Phase 2: Inventory Existing State (Read-Only)

### Step 6: Back Up Existing Plugins
```bash
ssh root@169.254.X.X 'ls -la /var/opt/hmi/data/ID5/Plugins/'
```

Record what's there. If there are existing plugins, back them up:
```bash
ssh root@169.254.X.X 'cp -r /var/opt/hmi/data/ID5/Plugins /var/opt/hmi/data/ID5/Plugins_backup_$(date +%Y%m%d)'
```

---

## Phase 3: Install (One App at a Time — Staged)

### ⚠️ Rules
- **Always parked, iDrive awake**
- **Install ONE app, test, then proceed to next**
- **If ANY app causes a crash, remove it immediately before trying another**
- **Keep SSH session open throughout — it's your escape hatch**

### Step 7: Install Engine Fault Codes FIRST (Safest)

This is the simplest app — one background image, read-only fault code scanning.

```bash
# Create the plugin folder
ssh root@169.254.X.X 'mkdir -p /var/opt/hmi/data/ID5/Plugins/EngineCodes'

# Upload files (from native/out/ and native/plugin/)
scp native/out/libEngineCodes.so root@169.254.X.X:/var/opt/hmi/data/ID5/Plugins/EngineCodes/
scp native/out/engine-codes-qnx root@169.254.X.X:/var/opt/hmi/data/ID5/Plugins/EngineCodes/
scp native/plugin/EngineCodes.xml root@169.254.X.X:/var/opt/hmi/data/ID5/Plugins/EngineCodes/
scp native/plugin/EngineCodes.manifest root@169.254.X.X:/var/opt/hmi/data/ID5/Plugins/EngineCodes/
scp native/plugin/EngineCodes_ALL_Images.zip root@169.254.X.X:/var/opt/hmi/data/ID5/Plugins/EngineCodes/

# Set worker executable
ssh root@169.254.X.X 'chmod +x /var/opt/hmi/data/ID5/Plugins/EngineCodes/engine-codes-qnx'

# Verify uploaded files
ssh root@169.254.X.X 'ls -la /var/opt/hmi/data/ID5/Plugins/EngineCodes/'
ssh root@169.254.X.X 'sha256sum /var/opt/hmi/data/ID5/Plugins/EngineCodes/*'
```

### Step 8: Restart iDrive & Test
1. **Hold the volume knob** until iDrive goes dark (~5 seconds)
2. Wait for iDrive to restart (~30-60 seconds)
3. Navigate to **My Vehicle** in iDrive menu
4. Look for **Engine Fault Codes** entry
5. Open it — you should see the glass design with health ring

**✅ If it works**: The framework is compatible. Proceed to Step 9.

**🛑 If iDrive crashes or doesn't restart within 2 minutes**:
```bash
# Emergency removal
ssh root@169.254.X.X 'mv /var/opt/hmi/data/ID5/Plugins/EngineCodes /var/opt/hmi/data/ID5/PluginBackups/'
# Force restart (hold volume knob again)
```

### Step 9: Install ShiftDeck (Second — Uses Standard OBD PIDs)
```bash
ssh root@169.254.X.X 'mkdir -p /var/opt/hmi/data/ID5/Plugins/ShiftDeck'

scp native/out/libShiftDeck.so root@169.254.X.X:/var/opt/hmi/data/ID5/Plugins/ShiftDeck/
scp native/out/shift-deck-qnx root@169.254.X.X:/var/opt/hmi/data/ID5/Plugins/ShiftDeck/
scp native/plugin/ShiftDeck.xml root@169.254.X.X:/var/opt/hmi/data/ID5/Plugins/ShiftDeck/
scp native/plugin/ShiftDeck.manifest root@169.254.X.X:/var/opt/hmi/data/ID5/Plugins/ShiftDeck/
scp native/plugin/ShiftDeck_ALL_Images.zip root@169.254.X.X:/var/opt/hmi/data/ID5/Plugins/ShiftDeck/
echo "169.254.21.3" | ssh root@169.254.X.X 'cat > /var/opt/hmi/data/ID5/Plugins/ShiftDeck/gateway-ip.txt'

ssh root@169.254.X.X 'chmod +x /var/opt/hmi/data/ID5/Plugins/ShiftDeck/shift-deck-qnx'
```

Restart iDrive, verify ShiftDeck appears and shows RPM/speed data while parked with engine running.

### Step 10: Install BoostDeck (Last — Most Complex, Continuous Polling)
```bash
ssh root@169.254.X.X 'mkdir -p /var/opt/hmi/data/ID5/Plugins/BoostDeck'

scp native/out/libBoostDeck.so root@169.254.X.X:/var/opt/hmi/data/ID5/Plugins/BoostDeck/
scp native/out/boostdeck-collector-qnx root@169.254.X.X:/var/opt/hmi/data/ID5/Plugins/BoostDeck/
scp native/plugin/BoostDeck.xml root@169.254.X.X:/var/opt/hmi/data/ID5/Plugins/BoostDeck/
scp native/plugin/BoostDeck.manifest root@169.254.X.X:/var/opt/hmi/data/ID5/Plugins/BoostDeck/
scp native/plugin/BoostDeck_ALL_Images.zip root@169.254.X.X:/var/opt/hmi/data/ID5/Plugins/BoostDeck/
echo "169.254.21.3" | ssh root@169.254.X.X 'cat > /var/opt/hmi/data/ID5/Plugins/BoostDeck/gateway-ip.txt'

ssh root@169.254.X.X 'chmod +x /var/opt/hmi/data/ID5/Plugins/BoostDeck/boostdeck-collector-qnx'
```

Restart iDrive, verify BoostDeck appears with arc gauges.

**NOTE**: On the S63 V8, most BoostDeck gauge values will be BLANK until we run the signal probe and port the S63 DIDs. ShiftDeck's RPM and speed should work immediately (standard OBD PIDs).

---

## Phase 4: Signal Probe (Read-Only)

### Step 11: Probe S63 DIDs
With engine running, from your laptop (NOT via SSH — direct ENET):
```bash
python3 tools/probe_signals.py \
  --local 169.254.10.2 \
  --gateway 169.254.10.3 \
  --ecu 12 \
  224205 224201 225889 224A49 22580F 2256D7 22586F 224300
```

This is **read-only** — UDS service 0x22 (ReadDataByIdentifier). No writes. Save the output for signal mapping.

---

## Emergency Procedures

### iDrive Won't Restart
```bash
# SSH should still work even if iDrive is frozen
ssh root@169.254.X.X

# Remove ALL custom plugins
mv /var/opt/hmi/data/ID5/Plugins/BoostDeck /var/opt/hmi/data/ID5/PluginBackups/ 2>/dev/null
mv /var/opt/hmi/data/ID5/Plugins/ShiftDeck /var/opt/hmi/data/ID5/PluginBackups/ 2>/dev/null
mv /var/opt/hmi/data/ID5/Plugins/EngineCodes /var/opt/hmi/data/ID5/PluginBackups/ 2>/dev/null

# Force restart
reboot
```

### Can't SSH In
1. Disconnect ENET cable
2. Turn car off completely (remove key from car for 2 minutes)
3. Car will cold-start iDrive on next ignition — plugins load fresh
4. If still broken: reconnect ENET, re-enable SSH via Bavarian SSH Client, remove plugins

### Nuclear Option (Factory Reset Plugins)
```bash
ssh root@169.254.X.X 'rm -rf /var/opt/hmi/data/ID5/Plugins/*'
# Restart iDrive — back to completely stock, no custom apps
```

---

## Before BMW Service Visits

**ALWAYS uninstall all custom plugins before taking the car to the dealer:**
```bash
ssh root@169.254.X.X
mv /var/opt/hmi/data/ID5/Plugins/BoostDeck /var/opt/hmi/data/ID5/PluginBackups/
mv /var/opt/hmi/data/ID5/Plugins/ShiftDeck /var/opt/hmi/data/ID5/PluginBackups/
mv /var/opt/hmi/data/ID5/Plugins/EngineCodes /var/opt/hmi/data/ID5/PluginBackups/
```

Restart iDrive. Re-install after service by moving the folders back.

---

## Summary of What's Safe

| What | Risk Level | Why |
|------|-----------|-----|
| Connecting ENET | None | Standard diagnostic port |
| Enabling SSH | Low | Temporary, no permanent changes |
| Running capture/probe scripts | None | Read-only |
| Installing plugins | Low | Files in a directory, fully reversible |
| Running BoostDeck/ShiftDeck | Low | Read-only diagnostic data |
| Engine Fault Codes (read) | None | Standard UDS read service |
| Engine Fault Codes (clear) | Low | Standard UDS clear, requires confirmation |
| The car's engine/drivetrain | Zero | Head unit has no control over powertrain |
