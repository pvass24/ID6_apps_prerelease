# M Performance App — Specification-Driven Design

## Purpose
Acceleration timer, braking distance, and G-force display for the iDrive 6
head unit on the 2019 F90 M5 Competition (S63B44T4).

## Constraints
- Speed from OBD `01 0D` is 1 km/h resolution — adequate for casual timing, not GPS-accurate
- Poll rate ~10Hz over HSFZ (100ms intervals)
- No direct GPS access from head unit plugins
- G-force from DSC acceleration sensors: availability TBD (probe at car)
- Fallback: longitudinal G derived from speed Δ (coarse)

## Pages

### Page 1: Drag Timer
**Trigger**: Speed crosses 3 km/h from standstill (debounced: 2 consecutive readings > 0).
**End**: All target splits captured, or speed drops > 10 km/h from peak.
**Splits**: 0-30, 0-60, 0-100 mph (0-48, 0-97, 0-161 km/h).
**1/4 mile**: Distance integrated from speed samples. Ends at 402m.
**Display**: Running timer (large), current speed, captured splits, status.
**Accuracy note**: Displayed as "EST" (estimated) — not GPS-verified.

### Page 2: Best Times
**Storage**: JSON file at `/var/opt/hmi/data/ID5/Plugins/MPerf/results.json`.
**Records**: Best 0-60, best 0-100, best 1/4 mile, plus last 8 runs.
**Display**: Glass card rows with date, time, trap speed.

### Page 3: G-Force (stretch — depends on sensor access)
**Data**: Longitudinal from speed derivative (always available).
Lateral from DSC accel sensor (probe needed — ECU `12` DID TBD).
**Display**: Numeric readouts + bar gauges. Friction circle only if lateral data available.
**Peak hold**: Session max per direction, resetable.

### Page 4: Brake Test
**Trigger**: Speed above 80 km/h AND deceleration > 3 km/h per sample (0.83 m/s²).
**End**: Speed reaches 0 (2 consecutive readings = 0).
**Splits**: 100-0 km/h, 60-0 mph (97-0 km/h).
**Distance**: Integrated from speed samples during braking.
**Display**: Distance (meters/feet), peak decel, time.

## Worker Architecture

```
[collector-perf-qnx]          [libMPerf.so]
  reads OBD speed/RPM           HMI plugin
  at 10Hz via HSFZ              swaps images + text
  computes timer state           displays results
  sends frames via UDP    →
  writes results.json
```

Timer state machine runs in the collector (not the HMI plugin) for
consistent timing regardless of display frame rate.

## Timer State Machine

```
IDLE → ARMED → RUNNING → DONE
  ↑                        |
  └────────────────────────┘ (reset)
```

- **IDLE**: Waiting. Display shows last result or "READY".
- **ARMED**: Speed = 0, user selected "Arm timer". Next motion starts the clock.
- **RUNNING**: Clock ticking, splits captured as thresholds crossed.
- **DONE**: All splits captured or run ended. Results displayed and saved.

## Data Structures

### Speed sample
```c
struct speed_sample {
    uint64_t timestamp_ms;  // monotonic clock
    unsigned kph;           // 0-255 from OBD
    unsigned rpm;           // from OBD 01 0C
};
```

### Run result
```c
struct run_result {
    uint64_t start_ms;
    uint64_t split_0_60_ms;    // 0 if not reached
    uint64_t split_0_100_ms;   // 0 if not reached
    uint64_t quarter_ms;       // 0 if not reached
    unsigned quarter_trap_kph; // speed at 402m
    unsigned peak_kph;
    double distance_m;         // integrated
    int valid;                 // completed all targets
};
```

### G-force sample
```c
struct g_sample {
    double longitudinal_g;  // positive = accel, negative = decel
    double lateral_g;       // positive = right, negative = left (if available)
    int lateral_valid;      // 0 if derived only
};
```

## Test Plan (TDD)

### Unit tests (host, no car):
1. `test_timer_state_machine` — IDLE→ARMED→RUNNING→DONE transitions
2. `test_split_capture` — verify 0-60 split at exactly 97 km/h crossing
3. `test_distance_integration` — known speed profile → expected distance
4. `test_quarter_mile_detection` — distance reaches 402m
5. `test_g_from_speed` — known Δv/Δt → expected longitudinal G
6. `test_brake_trigger` — decel detection from speed samples
7. `test_result_persistence` — write/read JSON results
8. `test_run_reset` — DONE→IDLE clears state correctly
9. `test_edge_cases` — speed jumps, missed samples, very fast runs, very slow runs

### Integration tests (at the car):
10. Verify OBD speed reads at expected rate
11. Verify timer starts/stops correctly with real motion
12. Compare results against phone GPS timer (Dragy or similar)
