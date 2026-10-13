Undergraduate's project in micro-architectural attacks and weird gates.

# Prime+Probe

## Compiling and Running
Compiling:

```bash
make pp
```

Running:

```bash
./pp
```

(Assuming core 0 has a L1 cache with specifications fitting to those in consts.h)

> No `taskset` needed. The program pins itself in `ppinit()` (`pin_current_thread`): on Linux it calls `sched_setaffinity` to core 0, and on macOS / Apple Silicon (where `taskset` does not exist and no hard pinning is available) it uses the QoS class to bias the thread onto one cluster. **The default build targets the efficiency (E) cluster** (`QOS_CLASS_BACKGROUND`), which gives a cleaner heatmap on Apple Silicon; build with `make pp EFFICIENCY_CORE=0` to target a performance (P) core instead (`QOS_CLASS_USER_INTERACTIVE` + a real-time policy). Either way it discards any sample where the scheduler migrated the thread mid-measurement (`current_cpu()` retry in `run_pp.c`).
>
> `ppinit()` also calls `verify_cache_geometry()`, which checks the compile-time cache geometry in `consts.h` against the real hardware (via `sysctl` on macOS, `sysconf` on Linux) and **aborts on a line-size mismatch** so a wrong guess fails loudly instead of silently producing a dead attack. The E-/P-core geometry (`BLOCK_SIZE`/`NUM_SETS`/`NUM_LINES`) is selected automatically in `consts.h`; override any of them with `-D...` if needed.

Analyzing results:

```bash
python ./read_results.py
```

All in one:

```bash
make pp && ./pp && python ./read_results.py
```

Expects the raw results to be in `./results/raw/results.csv` (very large file). Creates the prime+probe heatmap (saved to `./results/prime_probe_heatmap.png`).

## Probe Single Set

Work on a single set. For i=0,...,NUM_LINES: Prime it, run victim with lines=i, probe.

To switch to this instead of full P+P: in `run_pp.c` in `main`, comment out call to `prime_and_probe` and comment in the for loop. Compiling and running like above will save raw results to `./results/raw/results_set_$i_lines.csv`, and print the file name for each $i as it does. 

Analyzing results using: `python ./read_set_results <results_file_name>`. Results will include histogram of probe times before and after victim, in `./results/probe_set/$i_lines.png`, and histogram of diff between after minus before times, in `./results/probe_set_diff`.

Compile, run and analyze all results:

```bash
make pp && for f in `./pp`; do python ./read_set_results.py $f; done
```

(Still assuming core 0 has a L1 cache with specifications fitting to those in consts.h)

# AES attack

## Run AES to get measurements

The program generates `n` random plaintexts, and encrypts them while performing Prime+Probe, measuring the access time to each set after encryption. 

## Compiling and Running

Compile:

```bash
make aes_pp
```

Args: a 32-digit hexadecimal number that represents an AES `key`, and a number of encryptions `n`. 

Example:

```bash
./aes_pp 00112233445566778899aabbccddeeff 100000
```

The measurements are saved to `./results/raw/aes_results.csv`. The file will contain `n` entries, with the plaintext, ciphertext and measurements collected for each set.

## Running analysis - correlation attacks

Correlation attack to try to obtain the final round key (and original master key) for the AES encryption. If there isn't enough data, this will likely fail.

Expects results file in `./results/raw/aes_results.csv`.

```bash
python ./read_aes_results.py
```

Example output:
```bash
Running correlation for ciphertext byte index 0...
Running correlation for ciphertext byte index 1...
Running correlation for ciphertext byte index 2...
Running correlation for ciphertext byte index 3...
Running correlation for ciphertext byte index 4...
Running correlation for ciphertext byte index 5...
Running correlation for ciphertext byte index 6...
Running correlation for ciphertext byte index 7...
Running correlation for ciphertext byte index 8...
Running correlation for ciphertext byte index 9...
Running correlation for ciphertext byte index 10...
Running correlation for ciphertext byte index 11...
Running correlation for ciphertext byte index 12...
Running correlation for ciphertext byte index 13...
Running correlation for ciphertext byte index 14...
Running correlation for ciphertext byte index 15...

Correlation analysis completed successfully.
Final round key:
36 D0 24 46 1D 84 B8 37 5F C0 F9 C0 4C BA B6 BB
Original AES-128 master key (Round Key 0):
00 11 22 33 44 55 66 77 88 99 AA BB CC DD EE FF
```
