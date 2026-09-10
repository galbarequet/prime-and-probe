#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>
#include <sys/stat.h>
#include <errno.h>

#include "arch_primitives.h"
#include "pp.h"
#include "consts.h"
#include "victim.h"

#define REPETITIONS (1000000)

#define PRIME_AND_PROBE_RESULTS_FILENAME ("./results/raw/results.csv")
#define PRIME_AND_PROBE_SET_RESULTS_FILENAME ("./results/raw/results_set_%zu_lines.csv")
#define PRIME_AND_PROBE_SET_PER_LINE_RESULTS_FILENAME ("./results/raw/results_set_per_line_%zu_lines.csv")

typedef struct
{
    uint64_t before[NUM_LINES];
    uint64_t after[NUM_LINES];
} probe_per_line_results_t;

typedef struct
{
    uint64_t before;
    uint64_t after;
} probe_set_results_t;

typedef struct
{
    size_t victim_set;
    size_t victim_line_count;
    uint64_t probe[NUM_SETS];
} probe_results_t;

void prime_and_probe(size_t repetitions)
{
    probe_results_t result = {0};
    probe_results_t *probe_times = calloc(repetitions, sizeof(probe_results_t));
    assert(probe_times != NULL);

    for (size_t i = 0; i < repetitions; i++)
    {
        size_t victim_set = rand() % NUM_SETS;
        size_t victim_line_count = rand() % VICTIM_NUM_LINES_OPTIONS;

        prime();
        victim(victim_set, victim_line_count);
        probe(result.probe);

        result.victim_set = victim_set;
        result.victim_line_count = victim_line_count;
        probe_times[i] = result;
    }

    FILE *fp = fopen(PRIME_AND_PROBE_RESULTS_FILENAME, "w");
    assert(fp != NULL);
    fprintf(fp, "victim_set,victim_line_count,probe_set,probe_time\n");
    for (size_t i = 0; i < repetitions; i++)
    {
        for (size_t set = 0; set < NUM_SETS; set++)
        {
            fprintf(fp, "%zu,%zu,%zu,%zu\n", probe_times[i].victim_set, probe_times[i].victim_line_count, set, probe_times[i].probe[set]);
        }
    }
    fclose(fp);
    free(probe_times);
}

void prime_and_probe_set_per_line(size_t repetitions, size_t set, size_t lines)
{
    probe_per_line_results_t results = {0};
    probe_per_line_results_t *probe_times = calloc(repetitions, sizeof(probe_per_line_results_t));

    for (size_t i = 0; i < repetitions; i++)
    {
        memset(&results, 0, sizeof(results));
        prime();
        probe_set_per_line(set, results.before);
        victim(set, lines);
        probe_set_per_line(set, results.after);
        // if (results.before[0] > 500 || results.after[0] > 500)
        // {
        //     continue; // will remain 0. to filter later.
        // }
        probe_times[i] = results;
    }

    char filename[sizeof(PRIME_AND_PROBE_SET_PER_LINE_RESULTS_FILENAME) + 20];
    snprintf(filename, sizeof(filename), PRIME_AND_PROBE_SET_PER_LINE_RESULTS_FILENAME, lines);
    printf("%s\n", filename);
    FILE *fp = fopen(filename, "w");
    assert(fp != NULL);
    fprintf(fp, "line,before,after\n");
    for (size_t i = 0; i < repetitions; i++)
    {
        for (size_t l = 0; l < NUM_LINES; l++)
        {
            fprintf(fp, "%lu,%lu,%lu\n", l, (unsigned long)probe_times[i].before[l], (unsigned long)probe_times[i].after[l]);
        }
    }
    free(probe_times);
    fclose(fp);
}

void prime_and_probe_set(size_t repetitions, size_t set, size_t lines)
{
    probe_set_results_t results = {0};
    probe_set_results_t *probe_times = calloc(repetitions, sizeof(results));
    size_t before = 0, after = 0;

    for (size_t i = 0; i < repetitions; i++)
    {
        memset(&results, 0, sizeof(results));
        prime();
        before = probe_set(set);
        victim(set, lines);
        after = probe_set(set);

        memory_fence();
        results.before = before;
        results.after = after;

        // if (results.before > 300 || results.after > 300)
        // {
        //     continue; // will remain 0. to filter later.
        // }
        probe_times[i] = results;
    }

    char filename[sizeof(PRIME_AND_PROBE_SET_RESULTS_FILENAME) + 20];
    snprintf(filename, sizeof(filename), PRIME_AND_PROBE_SET_RESULTS_FILENAME, lines);
    printf("%s\n", filename);
    FILE *fp = fopen(filename, "w");
    assert(fp != NULL);
    fprintf(fp, "before,after\n");
    for (size_t i = 0; i < repetitions; i++)
    {
        for (size_t l = 0; l < NUM_LINES; l++)
        {
            fprintf(fp, "%lu,%lu\n", (unsigned long)probe_times[i].before, (unsigned long)probe_times[i].after);
        }
    }
    free(probe_times);
    fclose(fp);
}

int main(void)
{
    assert(mkdir("./results", 0755) == 0 || errno == EEXIST);
    assert(mkdir("./results/raw", 0755) == 0 || errno == EEXIST);

    ppinit();

    prime_and_probe(REPETITIONS);
    // for (size_t lines = 0; lines <= NUM_LINES; lines++)
    // {
    //     // prime_and_probe_set_per_line(REPETITIONS, 17, lines);
    //     prime_and_probe_set(REPETITIONS, 17, lines);
    // }

    return 0;
}
