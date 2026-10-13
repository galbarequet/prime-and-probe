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

static inline void memory_fence(void)
{
    atomic_thread_fence(memory_order_seq_cst);
}

static inline uint64_t clock_ticks_per_second(void)
{
    return 1000000000ULL;
}

#elif defined(__aarch64__) || defined(__arm64__)

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

static inline void memory_fence(void)
{
    atomic_thread_fence(memory_order_seq_cst);
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