#include "arch_primitives.h"
#include "consts.h"

#include <stdio.h>
#include <stdlib.h>

/* ------------------------------------------------------------------------- */
/* Clock backend                                                             */
/* ------------------------------------------------------------------------- */

/* The cntvct_el0 clock backend is defined inline in arch_primitives.h; its
   one-time initialization is a no-op, kept as a stable seam for the ppinit()
   call site. */
void clock_init(void)
{
}

/* ------------------------------------------------------------------------- */
/* Cache-geometry verification                                               */
/* ------------------------------------------------------------------------- */

/*
 * Query the real L1D geometry at runtime and abort if it disagrees with the
 * compile-time constants the buffers were sized from. A line-size mismatch does
 * not crash prime/probe -- it silently misaligns the set model and produces a
 * dead, noise-floor attack -- so we fail loudly here instead.
 */
static void check_geometry(long detected_line, long detected_l1d)
{
    int bad = 0;

    if (detected_line > 0 && detected_line != BLOCK_SIZE) {
        fprintf(stderr,
                "cache geometry mismatch: hardware line size is %ld bytes but "
                "BLOCK_SIZE is %d. Rebuild with -DBLOCK_SIZE=%ld (and matching "
                "-DNUM_SETS/-DNUM_LINES).\n",
                detected_line, BLOCK_SIZE, detected_line);
        bad = 1;
    }
    /* The L1D size depends on which core the thread lands on (P vs E) and on the
       associativity we model, so treat a size mismatch as a note, not fatal.
       Line size is invariant across cores, so that stays a hard error. */
    if (detected_l1d > 0 && detected_l1d != (long)CACHE_SIZE) {
        fprintf(stderr,
                "cache geometry note: hardware L1D is %ld bytes but the eviction "
                "buffer models %d bytes (NUM_SETS=%d * NUM_LINES=%d * "
                "BLOCK_SIZE=%d).\n",
                detected_l1d, (int)CACHE_SIZE, NUM_SETS, NUM_LINES, BLOCK_SIZE);
    }
    if (bad) {
        abort();
    }
}

#if defined(__APPLE__)

#include <sys/sysctl.h>

static long sysctl_long(const char *name)
{
    int64_t value = 0;
    size_t len = sizeof(value);
    if (sysctlbyname(name, &value, &len, NULL, 0) != 0) {
        return -1;
    }
    return (long)value;
}

void verify_cache_geometry(void)
{
    long line = sysctl_long("hw.cachelinesize");
    /* Match the L1D we compare against to the cluster we intend to run on. */
#if defined(USE_EFFICIENCY_CORE)
    long l1d = sysctl_long("hw.perflevel1.l1dcachesize");
#else
    long l1d = sysctl_long("hw.perflevel0.l1dcachesize");
#endif
    if (l1d <= 0) {
        l1d = sysctl_long("hw.l1dcachesize");
    }
    check_geometry(line, l1d);
}

#elif defined(__linux__)

#include <unistd.h>

void verify_cache_geometry(void)
{
    long line = sysconf(_SC_LEVEL1_DCACHE_LINESIZE);
    long l1d = sysconf(_SC_LEVEL1_DCACHE_SIZE);
    check_geometry(line, l1d);
}

#else

void verify_cache_geometry(void)
{
    /* Unknown platform: cannot query geometry, so nothing to verify. */
}

#endif

/* ------------------------------------------------------------------------- */
/* Core pinning / measurement-noise reduction                                */
/* ------------------------------------------------------------------------- */

#if defined(__APPLE__)

#include <pthread.h>
#include <sys/qos.h>
#include <mach/mach.h>
#include <mach/mach_time.h>
#include <mach/thread_policy.h>

/*
 * macOS (Apple Silicon and Intel) does not expose a taskset-style API to bind a
 * thread to a specific physical core. On Apple Silicon the affinity API
 * (THREAD_AFFINITY_POLICY) is a no-op entirely. Instead we reduce measurement
 * noise via QoS: the highest QoS keeps the thread on the performance cores,
 * BACKGROUND QoS biases it onto the efficiency cluster.
 */
void pin_current_thread(void)
{
#if defined(USE_EFFICIENCY_CORE)
    /* Bias the measuring thread onto the efficiency cluster. On Apple Silicon the
       scheduler runs BACKGROUND-QoS work on the E-cores, so lowering QoS is the
       only lever available (there is no core-pinning API). We deliberately do NOT
       apply the real-time time-constraint policy below: it forces performance
       behavior and pulls the thread back onto a P-core, defeating the purpose.
       The E-core has a smaller/simpler L1D and less aggressive prefetching, and
       its lower clock stretches each cache event across more timer ticks -- both
       of which can improve prime+probe cleanliness. Confirm placement by the
       higher absolute probe latencies vs a P-core run. */
    pthread_set_qos_class_self_np(QOS_CLASS_BACKGROUND, 0);
    return;
#else
    /* Keep the thread on the performance cores. */
    pthread_set_qos_class_self_np(QOS_CLASS_USER_INTERACTIVE, 0);

    /* Real-time scheduling to minimize preemption during measurement.
       Policy values are in absolute-time units; convert from nanoseconds. */
    mach_timebase_info_data_t tb;
    mach_timebase_info(&tb);
    double ns_to_abs = (double)tb.denom / (double)tb.numer;

    thread_time_constraint_policy_data_t pol;
    pol.period      = (uint32_t)(500000.0 * ns_to_abs); /* 0.5 ms */
    pol.computation = (uint32_t)(400000.0 * ns_to_abs); /* 0.4 ms of CPU */
    pol.constraint  = (uint32_t)(500000.0 * ns_to_abs); /* 0.5 ms deadline */
    pol.preemptible = 0;

    kern_return_t kr = thread_policy_set(mach_thread_self(),
                                         THREAD_TIME_CONSTRAINT_POLICY,
                                         (thread_policy_t)&pol,
                                         THREAD_TIME_CONSTRAINT_POLICY_COUNT);
    if (kr != KERN_SUCCESS) {
        fprintf(stderr,
                "pin_current_thread: real-time policy denied (kr=%d); the thread "
                "may run on an efficiency core. Run with sudo to be granted "
                "real-time scheduling and land on a P-core.\n",
                (int)kr);
    }
#endif /* USE_EFFICIENCY_CORE */
}

#elif defined(__linux__)

#include "cpu_affinity.h"

/* On Linux, bind hard to a single logical CPU (taskset-equivalent). */
void pin_current_thread(void)
{
    pin_to_core(0);
}

#else

/* Unknown platform: nothing to do. */
void pin_current_thread(void)
{
}

#endif
