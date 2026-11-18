# S63 V8 Signal Probe Plan — 2019 F90 M5 Competition

## Prerequisites
- ENET cable connected (OBD2 → laptop Ethernet)
- Car parked, ignition ON, engine running (for live signal readings)
- SSH enabled via Bavarian SSH Client
- Python 3 on laptop

## Step 1: Verify Head Unit Compatibility

```bash
cd /Users/patrickvassell/Projects/ID6_apps_prerelease/source

# Run the capture utility (replace IP with your head unit's SSH IP)
python3 tools/capture_headunit.py \
  --head 169.254.X.X \
  --out ~/m5_capture \
  --include-frameworks \
  --legacy
```

This pulls: firmware version, display resolution, framework SHA-256 hashes, split-node detection.

## Step 2: Probe B58 DIDs Against S63 DME

Test all 8 B58 gauge DIDs to see which the S63 responds to:

```bash
python3 tools/probe_signals.py \
  --local 169.254.10.2 \
  --gateway 169.254.10.3 \
  --ecu 12 \
  224205 224201 225889 224A49 22580F 2256D7 22586F 224300
```

Expected outcomes per DID:
| DID | Gauge | Likely S63 Result |
|-----|-------|-------------------|
| 4205 | Absolute boost (kPa) | May respond — common across platforms |
| 4201 | Ambient pressure (kPa) | May respond — common |
| 5889 | AFR / Lambda | Unknown — may use different DID |
| 4A49 | Ignition timing | Unknown |
| 580F | Intake air temp | Possibly — common sensor format |
| 56D7 | Rail pressure | Unknown — different fuel system |
| 586F | Oil pressure | Unknown |
| 4300 | Coolant temp | Possibly — common format |

Also test OBD standard PIDs (these should work universally):

```bash
python3 tools/probe_signals.py \
  --local 169.254.10.2 \
  --gateway 169.254.10.3 \
  --ecu 12 \
  010C 010D 0105
```

- 01 0C = RPM (should work)
- 01 0D = Speed (should work)
- 01 05 = Coolant temp via OBD (should work)

## Step 3: Probe EGS (Transmission) 

The ZF 8HP is shared between B58 and S63:

```bash
python3 tools/probe_signals.py \
  --local 169.254.10.2 \
  --gateway 169.254.10.3 \
  --ecu 18 \
  22DA12
```

- DA12 = Transmission temp — should work (same ZF 8HP76)

## Step 4: Record and Validate

For every DID that returns a positive reply (starts with `62`):
1. Record the raw hex response
2. Compare the decoded value against a known reference (ISTA, MHD, OBD scanner)
3. Validate the conversion formula from SIGNALS.md works
4. If the value doesn't match, the DID responds but uses different scaling

For rejected DIDs (returns `7f 22 31`):
- These need S63-specific DID discovery
- Common S63 DIDs to try (from BMW ISTA documentation):
  - Boost: 4202, 4203, 4206, 4207
  - Lambda bank 1/2: 5886, 5887, 5888
  - Oil temp: 5850, 5860
  - Charge air: 580E, 5810

## Step 5: Build S63 Signal Profile

Once validated DIDs are found, the changes go in two files:

**collector.c** (line ~366) — update DID array:
```c
// Gate by ECU identification so B58 profile is preserved
const unsigned dids[] = {0x4201, 0x4205, ...S63 replacements...};
```

**gauge_core.c** (`bd_decode_did` function) — add S63 decoders if scaling differs:
```c
case 0xNEW_DID: x = raw * NEW_FACTOR; lo = X; hi = Y; break;
```

## Notes
- probe_signals.py is READ ONLY — no writes to any ECU
- Max 12 requests per run
- 200ms spacing between requests
- Separate TCP connection per request (prevents cross-contamination)
- Engine should be running for meaningful boost/AFR/timing readings
- Engine OFF for trans temp (so trans is at a known state)
