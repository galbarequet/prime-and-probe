#define _GNU_SOURCE
#include "cpu_affinity.h"

#include <stdint.h>

#if defined(__linux__)

#include <sched.h>

int pin_to_core(int core)
{
    cpu_set_t set;
    CPU_ZERO(&set);
    CPU_SET(core, &set);
    return sched_setaffinity(0, sizeof(set), &set);
}

unsigned current_cpu(void)
{
    int c = sched_getcpu();
    return c < 0 ? 0u : (unsigned)c;
}

#elif defined(__APPLE__)

#include <pthread.h>
#include <pthread/qos.h>

int pin_to_core(int core)
{
    (void)core;   /* arm64 macOS has no hard CPU pinning from user space */
    return pthread_set_qos_class_self_np(QOS_CLASS_USER_INTERACTIVE, 0);
}

#if defined(__aarch64__) || defined(__arm64__)

unsigned current_cpu(void)
{
    /* Darwin stashes the logical CPU id in the low bits of TPIDRRO_EL0 --
     * this is exactly what libplatform's _os_cpu_number() reads. We only
     * need to detect *change*, not the absolute id. The 3-bit field can
     * alias on machines with >8 cores, but QoS keeps us inside the
     * P-cluster, so migrations within it are still caught. */
    uint64_t p;
    __asm__ __volatile__("mrs %0, TPIDRRO_EL0" : "=r"(p));
    return (unsigned)(p & 0x7);
}

#else

unsigned current_cpu(void)
{
    return 0u;
}

#endif

#else

#error "Unsupported architecture"

#endif
