#include "perf_core.h"
#include <string.h>
#include <math.h>

void perf_init(struct perf_state *st) {
    memset(st, 0, sizeof *st);
    st->state = PERF_IDLE;
    st->brake.state = BRAKE_IDLE;
}

void perf_arm(struct perf_state *st) {
    if (st->state == PERF_IDLE || st->state == PERF_DONE)
        st->state = PERF_ARMED;
}

void perf_reset(struct perf_state *st) {
    perf_init(st);
}

static void integrate_distance(struct perf_state *st, unsigned kph, uint64_t now_ms) {
    if (st->prev_valid && now_ms > st->prev_ms) {
        double dt_s = (now_ms - st->prev_ms) / 1000.0;
        double avg_ms = ((double)st->prev_kph + (double)kph) / 2.0 * PERF_KPH_TO_MS;
        st->run.distance_m += avg_ms * dt_s;
    }
}

void perf_feed(struct perf_state *st, unsigned kph, unsigned rpm, uint64_t now_ms) {
    (void)rpm;

    if (st->state == PERF_IDLE) {
        st->prev_kph = kph;
        st->prev_ms = now_ms;
        st->prev_valid = 1;
        return;
    }

    if (st->state == PERF_ARMED) {
        if (kph >= PERF_MOTION_KPH) {
            st->motion_count++;
            if (st->motion_count >= PERF_MOTION_COUNT) {
                st->state = PERF_RUNNING;
                st->run.start_ms = now_ms - (PERF_MOTION_COUNT - 1) * (now_ms > st->prev_ms ? now_ms - st->prev_ms : 100);
                st->run.distance_m = 0;
                st->prev_valid = 1;
                st->prev_kph = 0;
                st->prev_ms = st->run.start_ms;
            }
        } else {
            st->motion_count = 0;
        }
        st->prev_kph = kph;
        st->prev_ms = now_ms;
        st->prev_valid = 1;
        return;
    }

    if (st->state == PERF_RUNNING) {
        integrate_distance(st, kph, now_ms);

        if (kph > st->run.peak_kph)
            st->run.peak_kph = kph;

        uint64_t elapsed = now_ms - st->run.start_ms;

        if (!st->run.split_0_60_ms && kph >= PERF_SPLIT_60_KPH)
            st->run.split_0_60_ms = elapsed;

        if (!st->run.split_0_100_ms && kph >= PERF_SPLIT_100_KPH)
            st->run.split_0_100_ms = elapsed;

        if (!st->run.quarter_ms && st->run.distance_m >= PERF_QUARTER_M) {
            st->run.quarter_ms = elapsed;
            st->run.quarter_trap_kph = kph;
        }

        /* End condition: speed dropped significantly from peak */
        if (st->run.peak_kph > 50 && kph < st->run.peak_kph - 10 &&
            st->run.split_0_60_ms > 0) {
            st->state = PERF_DONE;
            st->run.valid = 1;
        }

        /* Also end if quarter mile captured and we have 0-60 */
        if (st->run.quarter_ms > 0 && st->run.split_0_60_ms > 0) {
            st->state = PERF_DONE;
            st->run.valid = 1;
        }
    }

    st->prev_kph = kph;
    st->prev_ms = now_ms;
    st->prev_valid = 1;
}

double perf_longitudinal_g(unsigned kph_before, unsigned kph_after, uint64_t dt_ms) {
    if (dt_ms == 0) return 0.0;
    double dv = ((double)kph_after - (double)kph_before) * PERF_KPH_TO_MS;
    double dt = dt_ms / 1000.0;
    return dv / dt / 9.80665;
}

static void brake_integrate(struct perf_state *st, unsigned kph, uint64_t now_ms) {
    if (st->prev_valid && now_ms > st->prev_ms) {
        double dt_s = (now_ms - st->prev_ms) / 1000.0;
        double avg_ms = ((double)st->prev_kph + (double)kph) / 2.0 * PERF_KPH_TO_MS;
        st->brake.distance_m += avg_ms * dt_s;
    }
}

void perf_brake_feed(struct perf_state *st, unsigned kph, uint64_t now_ms) {
    if (st->brake.state == BRAKE_DONE) {
        st->prev_kph = kph;
        st->prev_ms = now_ms;
        st->prev_valid = 1;
        return;
    }

    if (st->brake.state == BRAKE_IDLE) {
        /* Detect hard braking from high speed */
        if (st->prev_valid && kph < st->prev_kph &&
            st->prev_kph >= PERF_BRAKE_MIN_KPH) {
            double decel_g = perf_longitudinal_g(st->prev_kph, kph, now_ms - st->prev_ms);
            if (decel_g < -0.3) {
                st->brake.state = BRAKE_ACTIVE;
                st->brake.start_ms = st->prev_ms;
                st->brake.start_kph = st->prev_kph;
                st->brake.distance_m = 0;
                st->brake.peak_decel_g = 0;
                brake_integrate(st, kph, now_ms);
            }
        }
        st->prev_kph = kph;
        st->prev_ms = now_ms;
        st->prev_valid = 1;
        return;
    }

    if (st->brake.state == BRAKE_ACTIVE) {
        brake_integrate(st, kph, now_ms);

        if (st->prev_valid) {
            double decel_g = perf_longitudinal_g(st->prev_kph, kph, now_ms - st->prev_ms);
            double abs_g = fabs(decel_g);
            if (abs_g > st->brake.peak_decel_g)
                st->brake.peak_decel_g = abs_g;
        }

        uint64_t elapsed = now_ms - st->brake.start_ms;

        if (!st->brake.split_100_0_ms && st->brake.start_kph >= 100 && kph == 0)
            st->brake.split_100_0_ms = elapsed;

        if (!st->brake.split_60_0_ms && st->brake.start_kph >= PERF_SPLIT_60_KPH && kph == 0)
            st->brake.split_60_0_ms = elapsed;

        if (kph == 0) {
            st->stop_count++;
            if (st->stop_count >= PERF_STOP_COUNT) {
                st->brake.state = BRAKE_DONE;
                st->brake.end_ms = now_ms;
            }
        } else {
            st->stop_count = 0;
        }
    }

    st->prev_kph = kph;
    st->prev_ms = now_ms;
    st->prev_valid = 1;
}
