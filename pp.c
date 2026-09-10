#include <stdlib.h>
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <inttypes.h>
#include <limits.h>
#include <string.h>
#include <assert.h>
#include <errno.h>
#include <sys/stat.h>

#include "arch_primitives.h"
#include "consts.h"
#include "victim.h"
#include "pointer_chasing.h"
#include "pp.h"

// static volatile uint8_t buffer[NUM_SETS * NUM_LINES * BLOCK_SIZE] __attribute__((aligned(4096))) = {0};
static volatile doubly_linked_list_elem_t buffer[NUM_SETS * NUM_LINES * BLOCK_SIZE / sizeof(doubly_linked_list_elem_t)] __attribute__((aligned(4096))) = {0};
static uint16_t set_order[NUM_SETS] = {0};
static uint16_t line_order[NUM_LINES] = {0};

#define BUFFER_NUM_ELEMS (NUM_SETS * NUM_LINES * BLOCK_SIZE / sizeof(doubly_linked_list_elem_t))
// verifying underlying type assumptions to ensure type is valid to index the buffer.     
_Static_assert(__builtin_types_compatible_p(__typeof__(buffer[0].next), uint16_t), "expecting uint16_t indexes");
_Static_assert(BUFFER_NUM_ELEMS <= UINT16_MAX, "uint16_t is too small to index the buffer");

void ppinit(void)
{    
    init_doubly_linked_list_structure(set_order, line_order, buffer);
    init_victim();

    /* provided code for ramping up CPU */
    uint64_t start = read_clock();
    while (read_clock() - start < clock_ticks_per_second()) ;
}

void prime(void)
{
    uint16_t head = GET_BUFFER_IDX(set_order[0], line_order[0]);
    uint16_t idx = head;

    do {
        idx = buffer[idx].prev;
        memory_fence();
    } while (idx != head);
}

void probe(uint64_t result[NUM_SETS])
{
    uint16_t idx = GET_BUFFER_IDX(set_order[0], line_order[0]);  // probing all sets in the order of the permutation

    for (size_t s = 0; s < NUM_SETS; s++)
    {
        uint16_t set = set_order[s];

        uint64_t start = read_clock();
        for (size_t l = 0; l < NUM_LINES; l++)
        {
            // size_t debug_set = 0, debug_line = 0;
            // get_set_and_line_from_buffer_idx(idx, &debug_set, &debug_line);
            // assert(debug_set == set);

            idx = buffer[idx].next;  // using get_set_and_line_from_buffer_idx() I verified that the idx corresponds to the expected set
        }
        uint64_t end = read_clock();
        result[set] = (end - start);
    }
}

void probe_set_per_line(size_t set, uint64_t result[NUM_LINES])
{
    uint64_t start = 0, end = 0, duration = 0;
    uint16_t idx = GET_BUFFER_IDX(set, line_order[0]);

    for (size_t l = 0; l < NUM_LINES; l++)
    {
        start = read_clock();
        idx = buffer[idx].next;
        end = read_clock();
        duration = (end - start);
        if (duration < 200)
        {
            result[line_order[l]] = duration;
        }
    }
}

uint64_t probe_set(size_t set)
{
    uint64_t start = 0, end = 0;
    uint16_t idx = GET_BUFFER_IDX(set, line_order[0]);

    start = read_clock();
    for (size_t l = 0; l < NUM_LINES; l++)
    {
        // size_t debug_set = 0, debug_line = 0;
        // get_set_and_line_from_buffer_idx(idx, &debug_set, &debug_line);
        // assert(debug_set == set);

        idx = buffer[idx].next;
    }
    end = read_clock();
    return (end - start);
}
