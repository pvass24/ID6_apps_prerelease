/* TDD tests for the M Performance timer core.
 * Build and run on host (no car, no QNX):
 *   cc -Isrc -DPERF_HOST_TEST tests/test_perf.c src/perf_core.c -lm -o tests/test_perf && tests/test_perf
 */
#include <assert.h>
#include <math.h>
#include <stdio.h>
#include <string.h>
#include "perf_core.h"

#define ASSERT_EQ(a, b) do { if ((a) != (b)) { fprintf(stderr, "FAIL %s:%d: %lld != %lld\n", __FILE__, __LINE__, (long long)(a), (long long)(b)); return 1; } } while(0)
#define ASSERT_NEAR(a, b, eps) do { if (fabs((a) - (b)) > (eps)) { fprintf(stderr, "FAIL %s:%d: %.6f != %.6f (eps %.6f)\n", __FILE__, __LINE__, (double)(a), (double)(b), (double)(eps)); return 1; } } while(0)
#define ASSERT_TRUE(x) do { if (!(x)) { fprintf(stderr, "FAIL %s:%d: %s\n", __FILE__, __LINE__, #x); return 1; } } while(0)
#define RUN(test) do { printf("  %-50s", #test); int r = test(); printf("%s\n", r ? "FAIL" : "ok"); fails += r; total++; } while(0)

/* ── Test 1: State machine transitions ── */
static int test_timer_state_machine(void) {
    struct perf_state st;
    perf_init(&st);
    ASSERT_EQ(st.state, PERF_IDLE);

    perf_arm(&st);
    ASSERT_EQ(st.state, PERF_ARMED);

    /* Feed speed=0 while armed — stays armed */
    perf_feed(&st, 0, 0, 1000);
    ASSERT_EQ(st.state, PERF_ARMED);

    /* First motion — transitions to RUNNING */
    perf_feed(&st, 3, 1200, 1100);
    perf_feed(&st, 5, 1500, 1200);
    ASSERT_EQ(st.state, PERF_RUNNING);
    ASSERT_TRUE(st.run.start_ms > 0);

    /* Reset from any state → IDLE */
    perf_reset(&st);
    ASSERT_EQ(st.state, PERF_IDLE);
    return 0;
}

/* ── Test 2: Split capture at speed thresholds ── */
static int test_split_capture(void) {
    struct perf_state st;
    perf_init(&st);
    perf_arm(&st);

    uint64_t t = 10000;
    /* Launch: speed ramps from 0 to 100+ km/h */
    perf_feed(&st, 0, 800, t); t += 100;
    perf_feed(&st, 3, 1200, t); t += 100;  /* start detected */

    /* Ramp to 97 km/h (60 mph) over ~3 seconds */
    for (unsigned kph = 5; kph < 97; kph += 3) {
        t += 100;
        perf_feed(&st, kph, 2000 + kph * 40, t);
    }
    /* Cross 97 km/h — should capture 0-60 split */
    t += 100;
    perf_feed(&st, 97, 5800, t);
    ASSERT_TRUE(st.run.split_0_60_ms > 0);

    /* Continue to 161 km/h (100 mph) */
    for (unsigned kph = 100; kph < 161; kph += 5) {
        t += 100;
        perf_feed(&st, kph, 6000, t);
    }
    t += 100;
    perf_feed(&st, 161, 6500, t);
    ASSERT_TRUE(st.run.split_0_100_ms > 0);
    ASSERT_TRUE(st.run.split_0_100_ms > st.run.split_0_60_ms);

    return 0;
}

/* ── Test 3: Distance integration from speed samples ── */
static int test_distance_integration(void) {
    struct perf_state st;
    perf_init(&st);
    perf_arm(&st);

    /* Constant 100 km/h = 27.78 m/s for 10 seconds = 277.8 m */
    uint64_t t = 10000;
    perf_feed(&st, 0, 0, t); t += 100;
    perf_feed(&st, 3, 1000, t); t += 100;  /* start */

    /* Feed constant 100 km/h for 100 samples at 100ms = 10 seconds */
    for (int i = 0; i < 100; i++) {
        t += 100;
        perf_feed(&st, 100, 5000, t);
    }

    /* Distance should be ~277.8 m (100 km/h × 10s) */
    ASSERT_NEAR(st.run.distance_m, 277.8, 5.0);
    return 0;
}

/* ── Test 4: Quarter mile detection at 402m ── */
static int test_quarter_mile_detection(void) {
    struct perf_state st;
    perf_init(&st);
    perf_arm(&st);

    uint64_t t = 10000;
    perf_feed(&st, 0, 0, t); t += 100;
    perf_feed(&st, 3, 1000, t); t += 100;  /* start */

    /* Accelerate hard — 200 km/h constant (55.6 m/s) for 8 seconds = 444m */
    for (int i = 0; i < 80; i++) {
        t += 100;
        perf_feed(&st, 200, 7000, t);
    }

    ASSERT_TRUE(st.run.quarter_ms > 0);
    ASSERT_TRUE(st.run.quarter_trap_kph > 0);
    ASSERT_TRUE(st.run.distance_m >= 402.0);
    return 0;
}

/* ── Test 5: Longitudinal G from speed derivative ── */
static int test_g_from_speed(void) {
    /* 0 to 100 km/h in 1 second = 27.78 m/s² = 2.83g */
    double g = perf_longitudinal_g(0, 100, 1000);
    ASSERT_NEAR(g, 2.83, 0.1);

    /* Constant speed = 0g */
    g = perf_longitudinal_g(100, 100, 100);
    ASSERT_NEAR(g, 0.0, 0.01);

    /* Braking: 100 to 0 in 3 seconds = -9.26 m/s² = -0.94g */
    g = perf_longitudinal_g(100, 0, 3000);
    ASSERT_NEAR(g, -0.94, 0.05);

    return 0;
}

/* ── Test 6: Brake trigger detection ── */
static int test_brake_trigger(void) {
    struct perf_state st;
    perf_init(&st);

    uint64_t t = 10000;
    /* Cruising at 120 km/h */
    for (int i = 0; i < 10; i++) {
        t += 100;
        perf_brake_feed(&st, 120, t);
    }
    ASSERT_EQ(st.brake.state, BRAKE_IDLE);

    /* Hard braking: 120 → 110 in 100ms = decel */
    t += 100;
    perf_brake_feed(&st, 110, t);
    /* Might not trigger yet — needs sustained decel */
    t += 100;
    perf_brake_feed(&st, 98, t);
    t += 100;
    perf_brake_feed(&st, 85, t);

    ASSERT_EQ(st.brake.state, BRAKE_ACTIVE);

    /* Decel to 0 */
    for (unsigned kph = 80; kph > 0; kph -= 5) {
        t += 100;
        perf_brake_feed(&st, kph, t);
    }
    t += 100;
    perf_brake_feed(&st, 0, t);
    t += 100;
    perf_brake_feed(&st, 0, t);

    ASSERT_EQ(st.brake.state, BRAKE_DONE);
    ASSERT_TRUE(st.brake.distance_m > 0);
    ASSERT_TRUE(st.brake.peak_decel_g > 0);

    return 0;
}

/* ── Test 7: Run reset clears everything ── */
static int test_run_reset(void) {
    struct perf_state st;
    perf_init(&st);
    perf_arm(&st);

    uint64_t t = 10000;
    perf_feed(&st, 0, 0, t); t += 100;
    perf_feed(&st, 3, 1200, t); t += 100;  /* motion_count=1 */
    perf_feed(&st, 5, 1500, t); t += 100;  /* motion_count=2, now RUNNING */
    perf_feed(&st, 50, 4000, t); t += 100;

    ASSERT_EQ(st.state, PERF_RUNNING);
    ASSERT_TRUE(st.run.distance_m > 0);

    perf_reset(&st);
    ASSERT_EQ(st.state, PERF_IDLE);
    ASSERT_NEAR(st.run.distance_m, 0.0, 0.001);
    ASSERT_EQ(st.run.split_0_60_ms, 0);
    ASSERT_EQ(st.run.split_0_100_ms, 0);
    ASSERT_EQ(st.run.quarter_ms, 0);
    ASSERT_EQ(st.run.start_ms, 0);
    return 0;
}

/* ── Test 8: Edge case — speed jumps ── */
static int test_edge_speed_jump(void) {
    struct perf_state st;
    perf_init(&st);
    perf_arm(&st);

    uint64_t t = 10000;
    perf_feed(&st, 0, 0, t); t += 100;
    perf_feed(&st, 3, 1000, t); t += 100;   /* motion_count=1 */
    perf_feed(&st, 5, 1200, t); t += 100;   /* motion_count=2, RUNNING */

    /* Sudden jump from 5 to 120 km/h (missed samples) */
    t += 100;
    perf_feed(&st, 120, 6000, t);

    /* Should still be RUNNING, 0-60 should be captured (120 > 97) */
    ASSERT_EQ(st.state, PERF_RUNNING);
    ASSERT_TRUE(st.run.split_0_60_ms > 0);
    return 0;
}

/* ── Test 9: Not armed — feeding does nothing ── */
static int test_not_armed(void) {
    struct perf_state st;
    perf_init(&st);

    /* Feed without arming */
    perf_feed(&st, 100, 6000, 10000);
    ASSERT_EQ(st.state, PERF_IDLE);
    ASSERT_EQ(st.run.start_ms, 0);
    return 0;
}

int main(void) {
    int fails = 0, total = 0;
    printf("M Performance timer core tests:\n");
    RUN(test_timer_state_machine);
    RUN(test_split_capture);
    RUN(test_distance_integration);
    RUN(test_quarter_mile_detection);
    RUN(test_g_from_speed);
    RUN(test_brake_trigger);
    RUN(test_run_reset);
    RUN(test_edge_speed_jump);
    RUN(test_not_armed);
    printf("\n%d/%d passed%s\n", total - fails, total, fails ? " *** FAILURES ***" : "");
    return fails ? 1 : 0;
}
