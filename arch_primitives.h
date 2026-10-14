#ifndef ARCH_PRIMITIVES_H
#define ARCH_PRIMITIVES_H

#include <stdatomic.h>
#include <stdint.h>

#if defined(__x86_64__) || defined(_M_X64)

#include <x86intrin.h>

static inline uint64_t read_clock(void)
{
    uint32_t dummy;
    return __rdtscp(&dummy);
}

/* rdtscp already partially serializes, so the open/close window variants (see
   the arm64 branch for the rationale) coincide with read_clock() here. */
static inline uint64_t read_clock_open(void)  { return read_clock(); }
static inline uint64_t read_clock_close(void) { return read_clock(); }

static inline void memory_fence(void)
{
    atomic_thread_fence(memory_order_seq_cst);
}

static inline uint64_t clock_ticks_per_second(void)
{
    return 1000000000ULL;
}

#elif defined(__aarch64__) || defined(__arm64__)

static inline void memory_fence(void)
{
    atomic_thread_fence(memory_order_seq_cst);
}

/*
 * cntvct_el0 backend: the architectural virtual counter. On M5 this ticks at
 * 1 GHz (cntfrq_el0), ~3 CPU cycles/tick -- fine enough for most intervals, but
 * blind to work under ~50 cycles. The two `isb`s serialize the read so the
 * timed region isn't reordered around it.
 */
static inline uint64_t read_clock(void)
{
    uint64_t t;

    __asm__ volatile(
        "isb\n"
        "mrs %0, cntvct_el0\n"
        "isb\n"
        : "=r"(t)
        :
        : "memory"
    );

    return t;
}

/*
 * Window-boundary reads: the minimal-correct way to bracket a timed region.
 *
 * `mrs cntvct_el0` carries no data dependency on the work being timed, so the
 * out-of-order core will happily read the counter before (or after) the work
 * unless an `isb` pins it. The full read_clock() above spends an `isb` on *both*
 * sides of every read -- four per timed region -- but only two of those orderings
 * actually matter:
 *   - open  (region start): read the counter, THEN let the work issue -> trailing isb.
 *   - close (region end):   wait for the work to retire, THEN read the counter -> leading isb.
 * This halves the (very expensive) isb count while preserving the exact ordering
 * that exposes the signal.
 */
static inline uint64_t read_clock_open(void)
{
    uint64_t t;
    __asm__ volatile("mrs %0, cntvct_el0\n\tisb\n" : "=r"(t) : : "memory");
    return t;
}

static inline uint64_t read_clock_close(void)
{
    uint64_t t;
    __asm__ volatile("isb\n\tmrs %0, cntvct_el0\n" : "=r"(t) : : "memory");
    return t;
}

static inline uint64_t clock_ticks_per_second(void)
{
    uint64_t frequency;

    __asm__ volatile(
        "isb\n"
        "mrs %0, cntfrq_el0\n"
        "isb\n"
        : "=r"(frequency)
        :
        : "memory"
    );

    return frequency;
}

#else

#error "Unsupported architecture"

#endif

/*
 * One-time initialization of the clock backend for the current thread. For the
 * cntvct_el0 backend and on other platforms this is a no-op; it exists as a stable
 * seam so an alternative backend can hook in. Call once, after pin_current_thread()
 * and before the first read_clock().
 */
void clock_init(void);

/*
 * Reduce scheduler-induced measurement noise for the current (measuring) thread.
 * On macOS this biases the thread onto the performance cluster, or onto the
 * efficiency cluster when built with -DUSE_EFFICIENCY_CORE; on Linux it delegates
 * to pin_to_core(0); elsewhere it is a no-op.
 */
void pin_current_thread(void);

/*
 * Verify the compile-time cache geometry (consts.h) against the real hardware
 * and abort on a hard mismatch (e.g. wrong cache-line size). No-op on platforms
 * whose geometry cannot be queried.
 */
void verify_cache_geometry(void);

#endif /* ARCH_PRIMITIVES_H */