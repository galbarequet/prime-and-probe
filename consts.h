#ifndef CONSTS_H
#define CONSTS_H

/*
 * L1D cache geometry.
 *
 * These are compile-time constants because the prime/probe buffers are sized
 * statically from them. Each can be overridden from the build
 * (e.g. `make pp CFLAGS=-DBLOCK_SIZE=128 ...`); otherwise a per-platform default
 * is chosen below. At startup verify_cache_geometry() (arch_primitives.c) queries
 * the real hardware and aborts on a mismatch, so a wrong guess fails loudly
 * instead of silently producing a dead (noise-floor) attack.
 *
 *   BLOCK_SIZE - cache line size in bytes
 *   NUM_SETS   - number of L1D sets
 *   NUM_LINES  - L1D associativity (ways); size of the per-set eviction set
 */

#if defined(__APPLE__) && (defined(__aarch64__) || defined(__arm64__))
/* Apple Silicon L1D: 128-byte lines, 64 sets (confirmed on M5 via sysctl
   hw.cachelinesize / hw.perflevelN.l1dcachesize).
     - P-core (perflevel0): 128 KB => 128 KB / 64 / 128 B = 16 ways;
     - E-core (perflevel1):  64 KB =>  64 KB / 64 / 128 B =  8 ways.
   Build with -DUSE_EFFICIENCY_CORE (the default, see Makefile) to target the
   E-cluster, which empirically yields a cleaner prime+probe heatmap. */
#  ifndef BLOCK_SIZE
#    define BLOCK_SIZE (128)
#  endif
#  ifndef NUM_SETS
#    define NUM_SETS (64)
#  endif
#  ifndef NUM_LINES
#    ifdef USE_EFFICIENCY_CORE
#      define NUM_LINES (8)
#    else
#      define NUM_LINES (16)
#    endif
#  endif
#else
/* Typical x86 L1D: 32-48 KB, 64-byte lines, 64 sets. */
#  ifndef BLOCK_SIZE
#    define BLOCK_SIZE (64)
#  endif
#  ifndef NUM_SETS
#    define NUM_SETS (64)
#  endif
#  ifndef NUM_LINES
#    define NUM_LINES (12)  // Assuming assignment to logical cores 0-(NUM_LINES-1)
#  endif
#endif

#define LINE_SEPARATION_IN_BYTES (NUM_SETS * BLOCK_SIZE)
#define CACHE_SIZE (NUM_SETS * NUM_LINES * BLOCK_SIZE)

/* Prime/probe buffers must be aligned so their base maps to set 0 and every set
   index is stable; aligning to one full set-sweep (== L1D way size) achieves
   this. NB: with 128 B lines and 64 sets this is 8192, so a plain page (4096)
   alignment is NOT enough -- use this macro. */
#define BUFFER_ALIGNMENT (LINE_SEPARATION_IN_BYTES)

// assignment allows values from 0-NUM_LINES (NUM_LINES numbers of options)
#define VICTIM_NUM_LINES_OPTIONS (NUM_LINES + 1)

#endif /* CONSTS_H */
