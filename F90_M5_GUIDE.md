# iDrive 6 Custom Apps — F90 M5 / M5 Competition Guide

The definitive guide for installing and running custom iDrive 6 apps on the **2018-2020 BMW F90 M5 and M5 Competition** (pre-LCI, S63B44T4 engine).

> **Status**: Work in progress. First F90 M5 to run these apps. Contributions welcome.

---

## Table of Contents
- [Is My Car Compatible?](#is-my-car-compatible)
- [What You Need](#what-you-need)
- [F90-Specific Differences](#f90-specific-differences)
- [S63 Signal Map](#s63-signal-map)
- [Display Resolution](#display-resolution)
- [Installation Steps](#installation-steps)
- [App Notes for M5 Owners](#app-notes-for-m5-owners)
- [Known Issues](#known-issues)
- [FAQ](#faq)

---

## Is My Car Compatible?

| | Supported | Notes |
|---|---|---|
| 2018-2020 F90 M5 | ✅ Expected | Pre-LCI, NBT Evo (iDrive 6) |
| 2018-2020 F90 M5 Competition | ✅ Expected | Same head unit as standard M5 |
| 2021+ F90 M5 LCI | ❓ Unknown | May have MGU (iDrive 7) — check your head unit |
| F90 M5 CS | ❓ Unknown | Limited production, needs verification |

**How to check**: If your iDrive home screen has the classic tile layout (not the new curved display), you have iDrive 6 / NBT Evo.

**IMPORTANT**: Your specific firmware version needs to be captured and checked against the compatibility list before installing. The [backup script](#installation-steps) does this automatically.

---

## What You Need

| Item | Purpose | Cost |
|------|---------|------|
| **ENET cable** (OBD2 → RJ45 Ethernet) | Wired connection to the head unit | ~$20-30 Amazon |
| **USB Ethernet adapter** | Connects ENET cable to your Mac/PC | ~$15-20 (you may already have one) |
| **Bavarian SSH Client** | Enables temporary SSH on the head unit | Free — [ssh.bavarian-aa.uk](https://ssh.bavarian-aa.uk/) |
| **Laptop** (Mac or PC) | Runs the tools | — |
| **30 minutes** | Parked, iDrive awake | — |

**You do NOT need:**
- WiFi OBD adapter (that's for MHD/BimmerCode, not this)
- BimmerCode or any coding tool
- Any tune (MHD/BM3) — the gauge apps work on stock cars
- Your phone connected to the car

---

## F90-Specific Differences

The F90 M5 differs from the reference B58 340i in several important ways:

### Engine: S63B44T4 (4.4L Twin-Turbo V8)
- **Redline**: 7,200 RPM (vs 6,500 on B58)
- **Different diagnostic IDs (DIDs)** for many sensors — see [Signal Map](#s63-signal-map)
- **Oil temperature available** (DID 4402) — the B58 apps don't have this
- **Engine power readable** (DID 4520) — real-time kW output
- **Transmission temp from DME** (DID 4650) — no need to query the EGS separately
- **Dual-bank exhaust**: Lambda probes per bank, not a single lambda

### Transmission: ZF 8HP76 (heavier duty than B58's 8HP50)
- Same diagnostic protocol as the B58 transmission
- Trans temp DID (4650) reads from DME directly

### xDrive
- **Factory xDrive modes** (4WD / 4WD Sport / 2WD) already built into M1/M2 setup
- The xDrive Control app is **NOT needed** — your car already has this feature natively
- Do NOT install xDrive Control — it could conflict with your factory M xDrive settings

### Display Resolution
- Most F90 M5s have a **1440 × 540** display (wider than the F30's 1280 × 480)
- Apps built for 1280×480 will have the **right edge clipped** on your screen
- This guide includes 1440×540 layout variants that fit correctly

### Shift Points
- B58 apps default to 6,000-6,500 RPM shift points — too low for the S63
- This guide's ShiftDeck uses **6,200 / 6,500 / 6,700 / 7,000 / 7,200 RPM**
- Default: 6,500 RPM (optimal for peak power at 6,000 RPM + gear ratio math)

---

## S63 Signal Map

These diagnostic IDs (DIDs) are verified for the S63 DME. Read via UDS service `22` over HSFZ port 6801.

### Confirmed Working (Community Verified)

| Gauge | DID | Data Type | Conversion | Notes |
|-------|-----|-----------|------------|-------|
| **Boost pressure** | `4205` | unsigned int | × 0.078125 = hPa | Same DID as B58, different scale |
| **Ambient pressure** | `4201` | unsigned int | × 0.0390625 = hPa | Same DID as B58 |
| **Coolant temp** | `4300` | unsigned char | × 0.75 − 48 = °C | Same DID and formula as B58 |
| **Oil temp (filtered)** | `4402` | unsigned int | × 0.75 − 48 = °C | **S63-specific** — not on B58 |
| **Oil pressure** | `4436` | unsigned int | × 1 = hPa absolute | Different DID from B58 (was 586F) |
| **Trans temp** | `4650` | unsigned char | × 0.75 − 48 = °C | From DME directly, no EGS query needed |
| **Engine power** | `4520` | unsigned int | × 0.01525879 = kW | **S63-specific** |
| **Engine RPM** | `4807` | unsigned int | × 0.25 = RPM | Alternative to OBD 01 0C |
| **Throttle position** | `4600` | signed int | × 0.02441406 = % | Throttle valve angle |
| **Oil sump temp** | `4425` | signed int | × 0.1 = °C | More accurate than 4402 |
| **Oil temp unfiltered** | `4408` | signed int | × 0.1 = °C | Fastest response |
| **Wastegate duty** | `4651` | unsigned int | × 0.00152588 = % | Turbo health indicator |
| **Battery voltage** | `460A` | unsigned int | × 0.015 = V | Electrical monitoring |
| **Gearbox speed** | `4682` | signed int | × 0.5 = RPM | High-res speed source |
| **Fuel mass flow** | `4521` | unsigned int | × 0.1 = kg/h | Fuel consumption |
| **Boost delta bank 1** | `4536` | signed int | × 0.125 = hPa | Boost leak detection |

### Standard OBD PIDs (Universal)

| PID | Gauge | Conversion |
|-----|-------|------------|
| `01 0C` | Engine RPM | 2 bytes ÷ 4 |
| `01 0D` | Vehicle speed | 1 byte = km/h |
| `01 05` | Coolant temp | 1 byte − 40 = °C |
| `01 0F` | Intake air temp | 1 byte − 40 = °C |

### Needs Verification at the Car

| DID | What | B58 DID | Status |
|-----|------|---------|--------|
| `580F` | Intake air temp | Same | Probe needed |
| `56D7` | Rail pressure | Same | Probe needed |
| `4A49` | Ignition timing | Same | S63 may use per-cylinder DIDs |
| `5889` | AFR / Lambda | Same | S63 may use `4702` (probe voltage) instead |
| DSC lateral accel | G-force | N/A | ECU address unknown, probe needed |
| DSC longitudinal accel | G-force | N/A | ECU address unknown, probe needed |

### Data Sources Reference
- [Nekocorp S63 PID database](https://git.nekocorp.fr/leo/bmw_pid_data/src/branch/master/s63_pid_data.csv)
- [obd-gauge-cluster BMW-STATUS](https://github.com/cheeseprince/obd-gauge-cluster/blob/main/docs/BMW-STATUS.md)
- [Pelican BMW M5 OBD-II PIDs](https://pelican.clutch.engineering/cars/bmw/m5)

---

## Display Resolution

| Resolution | Cars | Layout Files |
|-----------|------|-------------|
| 1280 × 480 | F30/F31/F32/F33/F34, F36, some F10/F06 | `BoostDeck.xml`, `ShiftDeck.xml`, `EngineCodes.xml` |
| **1440 × 540** | **F90 M5**, G30, G05, some F15 | `BoostDeck_1440.xml`, `ShiftDeck_1440.xml`, `EngineCodes_1440.xml` |

The capture script automatically detects your resolution. Use the matching XML files.

---

## Installation Steps

### Prerequisites
1. Download [Bavarian SSH Client](https://ssh.bavarian-aa.uk/) for your OS
2. Have your ENET cable + USB Ethernet adapter ready
3. Clone this repo: `git clone https://github.com/pvass24/ID6_apps_prerelease.git`
4. Switch to the glass-upgrade branch: `git checkout glass-upgrade`

### At the Car

```bash
cd ~/Projects/ID6_apps_prerelease

# Step 1: Connect ENET cable, turn WiFi OFF, open Bavarian SSH Client
# Write down the SSH IP it gives you

# Step 2: Turn WiFi back on, verify route
route get 169.254.X.X  # should show interface: en8

# Step 3: Backup everything (also grabs framework .so files)
./backup_headunit.sh 169.254.X.X --legacy

# Step 4: Profile the system (memory, storage, display)
./profile_headunit.sh 169.254.X.X --legacy

# Step 5: Run ABI compatibility audit
cd source
python3 native/tools/audit_framework_abi.py \
  --fingerprint native/framework-fingerprint.json \
  --installed-dir ~/m5_backup_*/frameworks \
  --report ~/m5_backup_*/abi-report.json

# Step 6: If audit passes, install STOCK apps first (baseline test)
# Follow INSTALL_SAFETY.md for staged installation

# Step 7: Probe S63 signals
python3 tools/probe_signals.py \
  --local 169.254.10.2 \
  --gateway 169.254.X.X \
  --ecu 12 \
  224205 224201 224300 224402 224436 224650 224807 224520
```

### After Installation
- Navigate to **My Vehicle** in iDrive
- Custom apps appear in the list (BoostDeck, ShiftDeck, Engine Fault Codes)
- Press **OPTIONS** on the iDrive controller for settings (color theme, units, shift point)
- Test everything **while parked** before driving

---

## App Notes for M5 Owners

### BoostDeck
- Boost, coolant temp, and ambient pressure work with stock S63 DIDs
- Oil TEMPERATURE is available (DID 4402) — the B58 shows oil PRESSURE instead
- Oil pressure uses DID 4436 (hPa) — different conversion from B58
- Trans temp reads from DME (4650) — works even over MOST fallback
- AFR may show blank until verified (S63 may use a different lambda DID)

### ShiftDeck
- RPM and speed use universal OBD PIDs — **works immediately**
- Shift points adjusted for S63 redline (6,200-7,200 RPM)
- Default shift point: 6,500 RPM (mathematically optimal for S63 power curve)

### Engine Fault Codes
- Uses standard UDS service 19/14 — **works on any BMW engine**
- Can read fault codes even when DME refuses to clear them
- S63-specific fault code descriptions may be limited (hex codes always shown)

### HUD Gauges
- **Only tested on F3X vehicles** — F90 HUD hardware compatibility unknown
- The F90 M5 has a wider, higher-resolution HUD than the F3X
- Install and test while parked before relying on it

### Apps NOT Recommended for M5
- **xDrive Control** — your M5 already has factory M xDrive modes (4WD/4WD Sport/2WD). Installing this app could conflict with the factory DSC calibration.
- **MHD+ Suite** — only works with MHD tunes. If you don't have MHD, don't install.
- **Bootmod3 Suite** — only works with BM3 CustomROM tunes. Beta.

---

## Known Issues

| Issue | Severity | Status |
|-------|----------|--------|
| 1440×540 layout clipping | Medium | Fixed — use `_1440` XML files |
| Speed-lock (apps lock while driving) | Medium | Unknown on F90 US-market — test at car |
| S63 gauge values blank | Expected | Need to probe and port S63 DIDs |
| 69MB asset ZIP may not load | Medium | Tiered approach: start at 7MB (Tier 1) |
| HUD compatibility on F90 | Unknown | F3X only tested — probe at car |
| Split-node head unit | Low | Capture script auto-detects |

---

## FAQ

**Q: Will this void my warranty?**
A: Plugins are files in a directory — fully reversible by removing the folder and restarting iDrive. Uninstall before dealer visits. BMW diagnostic could theoretically detect modifications, but no permanent changes are made to any ECU or firmware.

**Q: Can this brick my car?**
A: No. The head unit (infotainment) is completely separate from the engine, transmission, brakes, and all driving systems. Even a completely broken head unit = car still drives, just no navigation/media/settings.

**Q: Do I need a tune (MHD/BM3)?**
A: No. BoostDeck, ShiftDeck, and Engine Fault Codes work on completely stock cars. The tuning suites (MHD+/BM3) are separate apps only for tuned cars.

**Q: Will gauges work immediately on my S63?**
A: Some will (RPM, speed, coolant, boost). Others need signal probing to discover the correct S63 DIDs. See the [Signal Map](#s63-signal-map).

**Q: I have a 2021+ M5 LCI — will this work?**
A: Maybe not. The LCI may have MGU (iDrive 7) which uses a completely different app system. Check if your iDrive has the classic tile layout (iDrive 6) or the new curved interface (iDrive 7/8).

**Q: My ENET cable connects but nothing responds.**
A: Turn WiFi OFF on your laptop. Check that you're using the wired ENET cable (not a WiFi OBD adapter). See [ENET_SETUP.md](ENET_SETUP.md).

**Q: Can I use my WiFi OBD adapter instead of the ENET cable?**
A: No. WiFi OBD adapters only support basic OBD-II protocol. Installing apps and SSH require the wired ENET connection with BMW's HSFZ protocol.

---

## Contributing

This is the first F90 M5 to run custom iDrive 6 apps. If you have an F90 M5 and want to help:

1. **Report your firmware version** — run `capture_headunit.py` and share the output
2. **Test apps** — install and report what works/doesn't
3. **Probe signals** — run `probe_signals.py` with the S63 DIDs and share results
4. **Share your display resolution** — helps build correct layouts

Open an issue or PR on this repo with your findings.

---

*Built by [@pvass24](https://github.com/pvass24) with a 2019 F90 M5 Competition. Glass aesthetic upgrade by design.*
