# S63 V8 Signal Map — 2019 F90 M5 Competition

## Known S63 DIDs (Community Verified)

Source: [Nekocorp S63 PID database](https://git.nekocorp.fr/leo/bmw_pid_data/src/branch/master/s63_pid_data.csv), [obd-gauge-cluster BMW-STATUS](https://github.com/cheeseprince/obd-gauge-cluster/blob/main/docs/BMW-STATUS.md)

### BoostDeck Gauges — S63 Mapping

| Gauge | B58 DID | S63 DID | S63 Conversion | Notes |
|-------|---------|---------|----------------|-------|
| **Boost pressure** | 4205 | **4205** | unsigned int × 0.078125 = hPa | SAME DID, different scale (B58 uses ÷128 for kPa, S63 uses ×0.078125 for hPa) |
| **Ambient pressure** | 4201 | **4201** | unsigned int × 0.0390625 = hPa | SAME DID, different scale |
| **Coolant temp** | 4300 | **4300** | unsigned char × 0.75 − 48 = °C | SAME DID, SAME formula |
| **Oil temperature** | (none) | **4402** | unsigned int × 0.75 − 48 = °C | NEW — oil temp after filter. B58 used 586F for oil PRESSURE |
| **Oil pressure** | 586F | **4436** | unsigned int × 1 = hPa (absolute) | DIFFERENT DID and unit (hPa not bar) |
| **Intake air temp** | 580F | **TBD** | Probe needed | May use same DID or different |
| **Trans temp** | DA12 (EGS) | **4650** | unsigned char × 0.75 − 48 = °C | Available from DME directly on S63! No need to query EGS separately |
| **Rail pressure** | 56D7 | **TBD** | Probe needed | May use same DID |
| **AFR / Lambda** | 5889 | **4702** | unsigned int × 0.00048828 = V (probe voltage) | Different approach — raw probe voltage, not lambda directly |
| **Ignition timing** | 4A49 | **TBD** | Probe per-cylinder DIDs exist | S63 has per-cylinder timing |

### Additional S63-Specific Gauges Available

| DID | Description | Conversion | Useful for |
|-----|-------------|------------|------------|
| **4807** | Engine speed | unsigned int × 0.25 = RPM | Alternative to OBD 01 0C |
| **4808** | Target idle speed | unsigned int × 0.25 = RPM | Diagnostic |
| **4520** | Effective engine power | unsigned int × 0.01525879 | Power gauge! |
| **4521** | Fuel mass flow | unsigned int × 0.1 = kg/h | Fuel consumption |
| **4425** | Oil sump temperature | signed int × 0.1 = °C | More accurate than 4402 |
| **4408** | Oil temp unfiltered | signed int × 0.1 = °C | Fastest response |
| **4651** | Wastegate duty cycle | unsigned int × 0.00152588 = % | Turbo health |
| **4536** | Boost control difference bank 1 | signed int × 0.125 = hPa | Boost leak detection |
| **480B** | Accelerator pedal | unsigned int × 0.0015259 = % | Throttle position |
| **4600** | Throttle valve angle | signed int × 0.02441406 = % | Actual throttle |
| **460A** | Battery voltage | unsigned int × 0.015 = V | Electrical |
| **4682** | Gearbox speed sensor | signed int × 0.5 = RPM | Trans |

### Standard OBD PIDs (Universal — Work on ALL BMWs)

| PID | Description | Conversion |
|-----|-------------|------------|
| 01 0C | Engine RPM | 2 bytes ÷ 4 |
| 01 0D | Vehicle speed | 1 byte = km/h |
| 01 05 | Coolant temp | 1 byte − 40 = °C |
| 01 0F | Intake air temp | 1 byte − 40 = °C |
| 01 0B | Intake manifold pressure | 1 byte = kPa |

## Key Differences: S63 vs B58

1. **Boost scaling is different**: B58 uses ÷128 for kPa, S63 uses ×0.078125 for hPa. Same DID (4205), different math.
2. **Oil temp exists** (DID 4402) — B58 BoostDeck showed oil PRESSURE, S63 has both oil temp AND pressure.
3. **Trans temp from DME**: S63 reports trans temp at DID 4650 directly from the DME. No need to query the EGS (ECU 18) separately. This is simpler and works over MOST fallback.
4. **Oil pressure is in hPa** at DID 4436, not bar like B58's 586F. Conversion: hPa ÷ 1000 = bar.
5. **Lambda probe is raw voltage** (4702) not direct lambda (5889). Need to convert: V → lambda via Nernst equation, or just display voltage.
6. **Engine power is available** (DID 4520) — could add a kW/hp gauge!

## Probe Commands (When at the Car)

### Step 1: Verify Known S63 DIDs
```bash
python3 tools/probe_signals.py \
  --local 169.254.10.2 \
  --gateway 169.254.10.3 \
  --ecu 12 \
  224205 224201 224300 224402 224436 224650 224807 224520
```

Expected: all should return positive (62 XX XX ...) responses.

### Step 2: Test B58 DIDs That May Also Work on S63
```bash
python3 tools/probe_signals.py \
  --local 169.254.10.2 \
  --gateway 169.254.10.3 \
  --ecu 12 \
  225889 224A49 22580F 2256D7 22586F
```

These are B58-specific — some may respond on S63, some won't.

### Step 3: Standard OBD (Should All Work)
```bash
python3 tools/probe_signals.py \
  --local 169.254.10.2 \
  --gateway 169.254.10.3 \
  --ecu 12 \
  010C 010D 0105 010F 010B
```

### Step 4: Record & Validate
For every DID that returns a positive reply:
1. Record the raw hex response
2. Apply the conversion formula from the table above
3. Compare against a known reference (dashboard display, MHD, OBD scanner)
4. If the value makes sense → confirmed for use

## C Code Changes for S63 Support

Once DIDs are verified, modify these files:

**collector.c (line ~366)** — update the DID array:
```c
const unsigned dids[] = {
    0x4201,  // ambient pressure (same as B58)
    0x4205,  // boost pressure (same DID, different scale)
    0x4702,  // lambda probe voltage (was 0x5889 on B58)
    0x4A49,  // ignition timing (probe to verify)
    0x580F,  // intake air temp (probe to verify)
    0x4650,  // trans temp from DME (was 0xDA12 on EGS)
    0x56D7,  // rail pressure (probe to verify)
    0x4436,  // oil pressure in hPa (was 0x586F on B58)
    0x4300,  // coolant temp (same as B58)
};
```

**gauge_core.c** — update `bd_decode_did()`:
```c
case 0x4436: // S63 oil pressure in hPa → bar
    x = r / 1000.0; lo = 0; hi = 20; break;
case 0x4650: // S63 trans temp from DME
    x = r * 0.75 - 48; lo = -48; hi = 180; break;
case 0x4402: // S63 oil temp (could add as extra gauge)
    x = r * 0.75 - 48; lo = -48; hi = 180; break;
```

## Bonus: Gauges Only Available on S63

With the S63 DID database, we could add gauges that the B58 BoostDeck doesn't have:
- **Engine Power (kW)** — DID 4520
- **Oil Sump Temperature** — DID 4425
- **Wastegate Duty Cycle** — DID 4651 (turbo health indicator)
- **Throttle Position** — DID 4600
- **Battery Voltage** — DID 460A
