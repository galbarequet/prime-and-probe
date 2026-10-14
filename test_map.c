/* Diagnostic: learn the address->cache-set map by touching one known contiguous
   line and seeing which probe set lights up. Linear indexing => identity/rotation;
   scrambled => hashed L1D indexing (breaks the AES attack's contiguity model). */
#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include "arch_primitives.h"
#include "consts.h"
#include "pp.h"

static volatile uint8_t vbuf[NUM_SETS * NUM_LINES * BLOCK_SIZE]
    __attribute__((aligned(BUFFER_ALIGNMENT))) = {0};

#define REPS 4000

int main(void)
{
    ppinit();
    uint64_t probe_times[NUM_SETS];

    static double acc[NUM_SETS][NUM_SETS]; /* acc[t][s] */
    double baseline[NUM_SETS];
    for (size_t s = 0; s < NUM_SETS; s++) baseline[s] = 0.0;

    for (size_t t = 0; t < NUM_SETS; t++)
    {
        for (size_t s = 0; s < NUM_SETS; s++) acc[t][s] = 0.0;
        for (int r = 0; r < REPS; r++)
        {
            prime();
            memory_fence();
            /* touch a full way-set for target set t: lines at the way stride all
               map to the same L1D set under linear indexing => strong eviction */
            volatile uint8_t x = 0;
            for (size_t w = 0; w < NUM_LINES; w++)
                x ^= vbuf[t * BLOCK_SIZE + w * LINE_SEPARATION_IN_BYTES];
            (void)x;
            memory_fence();
            probe(probe_times);
            for (size_t s = 0; s < NUM_SETS; s++) acc[t][s] += (double)probe_times[s];
        }
        for (size_t s = 0; s < NUM_SETS; s++) baseline[s] += acc[t][s] / (double)NUM_SETS;
    }

    /* residual argmax: subtract per-set baseline to remove systematic bias */
    printf("target_line -> hottest_probe_set (baseline-subtracted, top 3)\n");
    int scrambled = 0;
    for (size_t t = 0; t < NUM_SETS; t++)
    {
        size_t best = 0; double bestv = -1e18;
        for (size_t s = 0; s < NUM_SETS; s++) {
            double v = acc[t][s] - baseline[s];
            if (v > bestv) { bestv = v; best = s; }
        }
        size_t b2=0,b3=0; double v2=-1e18,v3=-1e18;
        for (size_t s = 0; s < NUM_SETS; s++) { if (s==best) continue; double v=acc[t][s]-baseline[s];
            if (v>v2){v3=v2;b3=b2;v2=v;b2=s;} else if (v>v3){v3=v;b3=s;} }
        printf("%3zu -> %3zu   (2nd %3zu, 3rd %3zu)\n", t, best, b2, b3);
        if (best != t) scrambled++;
    }
    printf("\nlines whose hottest residual set != line index: %d / %d\n", scrambled, NUM_SETS);
    return 0;
}
