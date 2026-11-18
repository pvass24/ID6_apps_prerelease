#ifndef PERF_CORE_H
#define PERF_CORE_H

#include <stdint.h>

enum perf_timer_state { PERF_IDLE, PERF_ARMED, PERF_RUNNING, PERF_DONE };
enum brake_state { BRAKE_IDLE, BRAKE_ARMED, BRAKE_ACTIVE, BRAKE_DONE };

#define PERF_KPH_TO_MS 0.27778  /* 1 km/h in m/s */
#define PERF_SPLIT_60_KPH 97    /* 60 mph */
#define PERF_SPLIT_100_KPH 161  /* 100 mph */
#define PERF_QUARTER_M 402.336  /* 1/4 mile in meters */
#define PERF_MOTION_KPH 3       /* minimum speed to detect motion */
#define PERF_MOTION_COUNT 2     /* consecutive readings above threshold */
#define PERF_BRAKE_DECEL_KPH 8  /* km/h drop per 100ms to trigger brake */
#define PERF_BRAKE_MIN_KPH 80   /* minimum speed to arm brake test */
#define PERF_STOP_COUNT 2       /* consecutive 0 readings = stopped */

struct run_result {
    uint64_t start_ms;
    uint64_t split_0_60_ms;
    uint64_t split_0_100_ms;
    uint64_t quarter_ms;
    unsigned quarter_trap_kph;
    unsigned peak_kph;
    double distance_m;
    int valid;
};

struct brake_result {
    enum brake_state state;
    uint64_t start_ms;
    uint64_t end_ms;
    double distance_m;
    double peak_decel_g;
    unsigned start_kph;
    unsigned split_100_0_ms;
    unsigned split_60_0_ms;
};

struct perf_state {
    enum perf_timer_state state;
    struct run_result run;
    struct brake_result brake;

    /* internal */
    unsigned prev_kph;
    uint64_t prev_ms;
    unsigned motion_count;
    unsigned stop_count;
    int prev_valid;
};

void perf_init(struct perf_state *st);
void perf_arm(struct perf_state *st);
void perf_reset(struct perf_state *st);
void perf_feed(struct perf_state *st, unsigned kph, unsigned rpm, uint64_t now_ms);
void perf_brake_feed(struct perf_state *st, unsigned kph, uint64_t now_ms);
double perf_longitudinal_g(unsigned kph_before, unsigned kph_after, uint64_t dt_ms);

#endif
