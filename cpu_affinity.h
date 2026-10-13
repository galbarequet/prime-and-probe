#ifndef CPU_AFFINITY_H
#define CPU_AFFINITY_H

/*
 * Bias / pin the calling thread to a single stable core.
 *   Linux : hard affinity to logical CPU `core` (sched_setaffinity)
 *   macOS : QOS_CLASS_USER_INTERACTIVE (P-core bias; no hard pin on arm64)
 * Returns 0 on success, nonzero otherwise. `core` is ignored on macOS.
 */
int pin_to_core(int core);

/*
 * Best-effort: the logical CPU the calling thread is currently running on.
 * Used only to detect *migration* between two points in time, not as an
 * absolute identity. On platforms with no cheap query it returns 0.
 */
unsigned current_cpu(void);

#endif /* CPU_AFFINITY_H */
