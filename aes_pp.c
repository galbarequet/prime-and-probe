#include <errno.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>

#include "aes_utils.h"
#include "AES/aes.h"
#include "pp.h"
#include "consts.h"
#include "cpu_affinity.h"

#define PRIME_AND_PROBE_AES_RESULTS_FILENAME ("./results/raw/aes_results.csv")

typedef struct
{
    aes_t plaintext;
    aes_t ciphertext;
    uint64_t probe_measurements[NUM_SETS];
} probe_results_t;

void run_prime_and_probe_on_aes(AES_KEY *aeskey, unsigned long long n, probe_results_t *probe_results)
{
    ppinit();

    unsigned long long i = 0;
    while (i < n)
    {
        aes_t plaintext = {0};
        aes_t ciphertext = {0};
        rand_aes_plaintext(plaintext);

        unsigned current_core = current_cpu();
        prime();
        AES_encrypt(plaintext, ciphertext, aeskey);
        probe(probe_results[i].probe_measurements);
        if (current_cpu() != current_core)  // crossed cores -> retry
        {
            continue;
        }

        memcpy(probe_results[i].plaintext, plaintext, AESSIZE);
        memcpy(probe_results[i].ciphertext, ciphertext, AESSIZE);

        ++i;
    }
}

void write_results(const char *filename, unsigned long long n, probe_results_t *probe_results)
{
    FILE *fp = fopen(filename, "w");
    assert(fp != NULL);
    
    // write header
    fprintf(fp, "plaintext,ciphertext");
    for (int j = 0; j < NUM_SETS; j++)
    {
        fprintf(fp, ",probe_set_%d", j);
    }

    for (unsigned long long i = 0; i < n; ++i)
    {
        char plaintext_string[AESSIZE * 2 + 1] = {0};
        char ciphertext_string[AESSIZE * 2 + 1] = {0};

        tostring(probe_results[i].plaintext, plaintext_string);
        tostring(probe_results[i].ciphertext, ciphertext_string);

        fprintf(fp, "\n%s,%s", plaintext_string, ciphertext_string);
        for (int j = 0; j < NUM_SETS; j++)
        {
            fprintf(fp, ",%lu", (unsigned long)probe_results[i].probe_measurements[j]);
        }
    }

    fclose(fp);
}

int main(int argc, char **argv)
{
    aes_t key;
    AES_KEY aeskey;
    unsigned long long n;
    probe_results_t *probe_results = NULL;

    if (argc != 3) {
        fprintf(stderr, "Usage: %s <32-hex-digit-key> <number-of-encryptions>\n", argv[0]);
        return EXIT_FAILURE;
    }

    if (tobinary(argv[1], key) != 0) {
        fprintf(stderr, "Error: the key must be exactly 32 hexadecimal digits.\n");
        return EXIT_FAILURE;
    }

    if (parse_count(argv[2], &n) != 0) {
        fprintf(stderr, "Error: the number of encryptions must be a nonnegative integer.\n");
        return EXIT_FAILURE;
    }

    if (private_AES_set_encrypt_key(key, 128, &aeskey) != 0) {
        fprintf(stderr, "Error: failed to initialize the AES key.\n");
        return EXIT_FAILURE;
    }

    probe_results = calloc(n, sizeof(probe_results_t));
    assert(probe_results != NULL);

    run_prime_and_probe_on_aes(&aeskey, n, probe_results);
    write_results(PRIME_AND_PROBE_AES_RESULTS_FILENAME, n, probe_results);

    return EXIT_SUCCESS;
}