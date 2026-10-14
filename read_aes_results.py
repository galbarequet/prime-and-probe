import argparse
import platform
import subprocess

import pandas as pd
import polars as pl
import numpy as np
import matplotlib.pyplot as plt


CIPHER_TEXT_SIZE = 16
PROBE_SET_COLUMN_NAME = 'probe_set_{}'


def _detect_cache_line_size(default=64):
    """Cache line size in bytes, used to map a T-table entry to a cache set.

    This MUST equal the BLOCK_SIZE the probe binary was built with -- the probe
    buffer is laid out in BLOCK_SIZE-byte lines, and the C side's
    verify_cache_geometry() asserts (hardware line size == BLOCK_SIZE), so the
    hardware value is authoritative.

    On Apple Silicon the line size is 128 B and is INVARIANT across the P and E
    clusters: the two differ only in L1D size and associativity (P: 128 KB/16-way,
    E: 64 KB/8-way), neither of which changes the line size or the set count
    (64), and neither of which enters this correlation model. So it does not
    matter which core pp/aes_pp was pinned to. We default to 64 for non-macOS
    (typical x86 BLOCK_SIZE) when the sysctl is unavailable.
    """
    if platform.system() == 'Darwin':
        try:
            out = subprocess.check_output(['sysctl', '-n', 'hw.cachelinesize'])
            return int(out.strip())
        except (subprocess.SubprocessError, ValueError, OSError):
            pass
    return default


CACHE_LINE_SIZE = _detect_cache_line_size()

# Standard AES Inverse S-Box array
INV_SBOX = np.array([
    0x52, 0x09, 0x6a, 0xd5, 0x30, 0x36, 0xa5, 0x38, 0xbf, 0x40, 0xa3, 0x9e, 0x81, 0xf3, 0xd7, 0xfb,
    0x7c, 0xe3, 0x39, 0x82, 0x9b, 0x2f, 0xff, 0x87, 0x34, 0x8e, 0x43, 0x44, 0xc4, 0xde, 0xe9, 0xcb,
    0x54, 0x7b, 0x94, 0x32, 0xa6, 0xc2, 0x23, 0x3d, 0xee, 0x4c, 0x95, 0x0b, 0x42, 0xfa, 0xc3, 0x4e,
    0x08, 0x2e, 0xa1, 0x66, 0x28, 0xd9, 0x24, 0xb2, 0x76, 0x5b, 0xa2, 0x49, 0x6d, 0x8b, 0xd1, 0x25,
    0x72, 0xf8, 0xf6, 0x64, 0x86, 0x68, 0x98, 0x16, 0xd4, 0xa4, 0x5c, 0xcc, 0x5d, 0x65, 0xb6, 0x92,
    0x6c, 0x70, 0x48, 0x50, 0xfd, 0xed, 0xb9, 0xda, 0x5e, 0x15, 0x46, 0x57, 0xa7, 0x8d, 0x9d, 0x84,
    0x90, 0xd8, 0xab, 0x00, 0x8c, 0xbc, 0xd3, 0x0a, 0xf7, 0xe4, 0x58, 0x05, 0xb8, 0xb3, 0x45, 0x06,
    0xd0, 0x2c, 0x1e, 0x8f, 0xca, 0x3f, 0x0f, 0x02, 0xc1, 0xaf, 0xbd, 0x03, 0x01, 0x13, 0x8a, 0x6b,
    0x3a, 0x91, 0x11, 0x41, 0x4f, 0x67, 0xdc, 0xea, 0x97, 0xf2, 0xcf, 0xce, 0xf0, 0xb4, 0xe6, 0x73,
    0x96, 0xac, 0x74, 0x22, 0xe7, 0xad, 0x35, 0x85, 0xe2, 0xf9, 0x37, 0xe8, 0x1c, 0x75, 0xdf, 0x6e,
    0x47, 0xf1, 0x1a, 0x71, 0x1d, 0x29, 0xc5, 0x89, 0x6f, 0xb7, 0x62, 0x0e, 0xaa, 0x18, 0xbe, 0x1b,
    0xfc, 0x56, 0x3e, 0x4b, 0xc6, 0xd2, 0x79, 0x20, 0x9a, 0xdb, 0xc0, 0xfe, 0x78, 0xcd, 0x5a, 0xf4,
    0x1f, 0xdd, 0xa8, 0x33, 0x88, 0x07, 0xc7, 0x31, 0xb1, 0x12, 0x10, 0x59, 0x27, 0x80, 0xec, 0x5f,
    0x60, 0x51, 0x7f, 0xa9, 0x19, 0xb5, 0x4a, 0x0d, 0x2d, 0xe5, 0x7a, 0x9f, 0x93, 0xc9, 0x9c, 0xef,
    0xa0, 0xe0, 0x3b, 0x4d, 0xae, 0x2a, 0xf5, 0xb0, 0xc8, 0xeb, 0xbb, 0x3c, 0x83, 0x53, 0x99, 0x61,
    0x17, 0x2b, 0x04, 0x7e, 0xba, 0x77, 0xd6, 0x26, 0xe1, 0x69, 0x14, 0x63, 0x55, 0x21, 0x0c, 0x7d
], dtype=np.uint8)

# AES S-Box for key schedule
SBOX = [
    0x63, 0x7c, 0x77, 0x7b, 0xf2, 0x6b, 0x6f, 0xc5, 0x30, 0x01, 0x67, 0x2b, 0xfe, 0xd7, 0xab, 0x76,
    0xca, 0x82, 0xc9, 0x7d, 0xfa, 0x59, 0x47, 0xf0, 0xad, 0xd4, 0xa2, 0xaf, 0x9c, 0xa4, 0x72, 0xc0,
    0xb7, 0xfd, 0x93, 0x26, 0x36, 0x3f, 0xf7, 0xcc, 0x34, 0xa5, 0xe5, 0xf1, 0x71, 0xd8, 0x31, 0x15,
    0x04, 0xc7, 0x23, 0xc3, 0x18, 0x96, 0x05, 0x9a, 0x07, 0x12, 0x80, 0xe2, 0xeb, 0x27, 0xb2, 0x75,
    0x09, 0x83, 0x2c, 0x1a, 0x1b, 0x6e, 0x5a, 0xa0, 0x52, 0x3b, 0xd6, 0xb3, 0x29, 0xe3, 0x2f, 0x84,
    0x53, 0xd1, 0x00, 0xed, 0x20, 0xfc, 0xb1, 0x5b, 0x6a, 0xcb, 0xbe, 0x39, 0x4a, 0x4c, 0x58, 0xcf,
    0xd0, 0xef, 0xaa, 0xfb, 0x43, 0x4d, 0x33, 0x85, 0x45, 0xf9, 0x02, 0x7f, 0x50, 0x3c, 0x9f, 0xa8,
    0x51, 0xa3, 0x40, 0x8f, 0x92, 0x9d, 0x38, 0xf5, 0xbc, 0xb6, 0xda, 0x21, 0x10, 0xff, 0xf3, 0xd2,
    0xcd, 0x0c, 0x13, 0xec, 0x5f, 0x97, 0x44, 0x17, 0xc4, 0xa7, 0x7e, 0x3d, 0x64, 0x5d, 0x19, 0x73,
    0x60, 0x81, 0x4f, 0xdc, 0x22, 0x2a, 0x90, 0x88, 0x46, 0xee, 0xb8, 0x14, 0xde, 0x5e, 0x0b, 0xdb,
    0xe0, 0x32, 0x3a, 0x0a, 0x49, 0x06, 0x24, 0x5c, 0xc2, 0xd3, 0xac, 0x62, 0x91, 0x95, 0xe4, 0x79,
    0xe7, 0xc8, 0x37, 0x6d, 0x8d, 0xd5, 0x4e, 0xa9, 0x6c, 0x56, 0xf4, 0xea, 0x65, 0x7a, 0xae, 0x08,
    0xba, 0x78, 0x25, 0x2e, 0x1c, 0xa6, 0xb4, 0xc6, 0xe8, 0xdd, 0x74, 0x1f, 0x4b, 0xbd, 0x8b, 0x8a,
    0x70, 0x3e, 0xb5, 0x66, 0x48, 0x03, 0xf6, 0x0e, 0x61, 0x35, 0x57, 0xb9, 0x86, 0xc1, 0x1d, 0x9e,
    0xe1, 0xf8, 0x98, 0x11, 0x69, 0xd9, 0x8e, 0x94, 0x9b, 0x1e, 0x87, 0xe9, 0xce, 0x55, 0x28, 0xdf,
    0x8c, 0xa1, 0x89, 0x0d, 0xbf, 0xe6, 0x42, 0x68, 0x41, 0x99, 0x2d, 0x0f, 0xb0, 0x54, 0xbb, 0x16
]

RCON = [0x00, 0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x80, 0x1B, 0x36]


def _read_aes_pp_results(file_path):
    with open(file_path, 'r') as f:
        header = f.readline().strip().split(',')
        cache_sets_count = max(int(col.strip('probe_set_')) for col in header if col.startswith('probe_set_')) + 1

    probe_columns = [f"probe_set_{i}" for i in range(cache_sets_count)]
    return pl.read_csv(
        file_path,
        columns=["ciphertext", *probe_columns],
        schema_overrides={column: pl.UInt32 for column in probe_columns},
    )


def read_results(file_path):
    df = _read_aes_pp_results(file_path)
    prepared_data = _prepare_correlation_data(df)
    num_sets = prepared_data[4]

    # Correlation scores per ciphertext byte, pivoted to a [key_byte, table_start_set]
    # matrix so we can pick the key and the table offset jointly.
    score_matrices = []
    for i in range(CIPHER_TEXT_SIZE):
        print(f'Running correlation for ciphertext byte index {i}...')
        results = run_correlation(df, i, prepared_data=prepared_data)
        matrix = (
            results.pivot(index='key_byte_value', columns='table_start_set', values='score')
            .sort_index()
            .reindex(columns=range(num_sets))
            .to_numpy()
        )
        score_matrices.append(matrix)

    # table_start_set is a *shared* nuisance parameter: the four ciphertext bytes in
    # a T-table group (index % 4) all index the SAME table, so they share one start
    # set. Resolving it per group -- instead of independently per byte -- both avoids
    # spurious +/-1 argmax jitter between bytes and regularizes weak-signal bytes.
    key_bytes = [None] * CIPHER_TEXT_SIZE
    group_start_sets = {}
    for group in range(4):
        bytes_in_group = [group + 4 * j for j in range(CIPHER_TEXT_SIZE // 4)]
        # Best achievable score for each candidate start set, summed over the group.
        group_score = sum(score_matrices[i].max(axis=0) for i in bytes_in_group)
        start_set = int(np.argmax(group_score))
        group_start_sets[group] = start_set
        for i in bytes_in_group:
            key_bytes[i] = int(np.argmax(score_matrices[i][:, start_set]))

    print('\nRecovered per-group table start sets (set index of each T-table):')
    for group in range(4):
        print(f'  group {group} (bytes {group}, {group + 4}, {group + 8}, {group + 12}):'
              f' set {group_start_sets[group]}')

    print('\nFinal round key:')
    key = [f'{b:02X}' for b in key_bytes]
    print(' '.join(key))
    k10_bytes = bytes(key_bytes)
    k0_bytes = reverse_key_schedule_128(k10_bytes)
    print('Original AES-128 master key (Round Key 0):')
    print(' '.join(f'{b:02X}' for b in k0_bytes))


def _prepare_correlation_data(df):
    probe_columns = [column for column in df.columns if column.startswith('probe_set_')]
    num_sets = len(probe_columns)
    lower = df.select([
        pl.col(column).quantile(0.05, interpolation='nearest').alias(column)
        for column in probe_columns
    ]).row(0)
    upper = df.select([
        pl.col(column).quantile(0.95, interpolation='nearest').alias(column)
        for column in probe_columns
    ]).row(0)
    clipped = df.with_columns([
        pl.col(column).clip(lower[index], upper[index]).alias(column)
        for index, column in enumerate(probe_columns)
    ])

    statistics = clipped.select(
        [pl.col(column).mean().alias(f'mean_{column}') for column in probe_columns]
        + [pl.col(column).std(ddof=0).alias(f'std_{column}') for column in probe_columns]
    ).row(0)
    mean_Y = np.asarray(statistics[:num_sets], dtype=np.float64)[None, :]
    std_Y = np.asarray(statistics[num_sets:], dtype=np.float64)[None, :]

    byte_counts = np.empty((CIPHER_TEXT_SIZE, 256), dtype=np.int64)
    byte_sums = np.empty((CIPHER_TEXT_SIZE, 256, num_sets), dtype=np.float64)
    for byte_index in range(CIPHER_TEXT_SIZE):
        grouped = clipped.with_columns(
            pl.col('ciphertext').str.slice(byte_index * 2, 2)
            .str.to_integer(base=16).alias('cipher_byte')
        ).group_by('cipher_byte').agg(
            [pl.len().alias('count')]
            + [pl.col(column).sum().alias(column) for column in probe_columns]
        ).sort('cipher_byte')
        byte_counts[byte_index] = grouped['count'].to_numpy()
        byte_sums[byte_index] = grouped.select(probe_columns).to_numpy().astype(
            np.float64, copy=False
        )

    return mean_Y, std_Y, byte_counts, byte_sums, num_sets


def run_correlation(df, ciphertext_byte_index, prepared_data=None):
    if prepared_data is None:
        prepared_data = _prepare_correlation_data(df)

    mean_Y, std_Y, byte_counts, byte_sums, num_sets = prepared_data
    counts_by_value = byte_counts[ciphertext_byte_index]
    sums_by_value = byte_sums[ciphertext_byte_index]
    N = counts_by_value.sum()

    cache_line_size = CACHE_LINE_SIZE  # bytes; must match the build's BLOCK_SIZE
    table_entry_size = 4  # bytes
    table_cache_lines_count = INV_SBOX.size * table_entry_size // cache_line_size
    entries_per_cache_line = cache_line_size // table_entry_size

    cipher_values = np.arange(256, dtype=np.uint8)
    line_by_key_and_value = INV_SBOX[np.bitwise_xor(
        np.arange(256, dtype=np.uint8)[:, None], cipher_values[None, :]
    )] // entries_per_cache_line

    results = []
    for byte_value in range(256):
        line_by_value = line_by_key_and_value[byte_value]
        counts = np.bincount(
            line_by_value, weights=counts_by_value, minlength=table_cache_lines_count
        )
        sums = np.empty((table_cache_lines_count, num_sets), dtype=np.float64)
        for relative_line in range(table_cache_lines_count):
            sums[relative_line] = sums_by_value[line_by_value == relative_line].sum(axis=0)

        probability = counts / N
        cov = sums / N - probability[:, None] * mean_Y
        std_X = np.sqrt(probability * (1 - probability))[:, None]
        denom = std_X * std_Y
        M = np.abs(cov / denom)

        # for each possible set the table starts in 
        relative_line_indices = np.arange(table_cache_lines_count)
        for table_start_set in range(num_sets):
            set_indices = (table_start_set + relative_line_indices) % num_sets  # which sets the relative cache lines map to
            total_score = np.sum(M[relative_line_indices, set_indices])
            results.append({
                'key_byte_value': byte_value,
                'table_start_set': table_start_set,
                'score': total_score
            })

    results_df = pd.DataFrame(results)
    results_df['key_hex'] = results_df['key_byte_value'].apply(lambda x: f"0x{x:02X}")
    return results_df[['key_hex', 'key_byte_value', 'table_start_set', 'score']]

def reverse_key_schedule_128(k10_bytes: bytes) -> bytes:
    """AI gen code that reverses AES-128 key schedule from Round Key 10 to Round Key 0."""
    # Convert 16-byte key to four 32-bit words
    w = [int.from_bytes(k10_bytes[i:i+4], 'big') for i in range(0, 16, 4)]

    def g(word, rcon_idx):
        # RotWord + SubWord + Rcon
        b0 = (word >> 24) & 0xFF
        b1 = (word >> 16) & 0xFF
        b2 = (word >> 8) & 0xFF
        b3 = word & 0xFF
        
        # RotWord: [b1, b2, b3, b0] -> SubWord + Rcon
        res0 = SBOX[b1] ^ RCON[rcon_idx]
        res1 = SBOX[b2]
        res2 = SBOX[b3]
        res3 = SBOX[b0]
        
        return (res0 << 24) | (res1 << 16) | (res2 << 8) | res3

    # Reverse 10 rounds
    for r in range(10, 0, -1):
        w3 = w[3] ^ w[2]
        w2 = w[2] ^ w[1]
        w1 = w[1] ^ w[0]
        w0 = w[0] ^ g(w3, r)
        w = [w0, w1, w2, w3]

    # Reconstruct 16-byte master key
    return b''.join(word.to_bytes(4, 'big') for word in w)


def main():
    parser = argparse.ArgumentParser(
        description="Recover the AES-128 key from prime+probe measurements."
    )
    parser.add_argument(
        "input_file",
        nargs="?",
        default="./results/raw/aes_results.csv",
        help="CSV produced by aes_pp (default: ./results/raw/aes_results.csv)",
    )
    args = parser.parse_args()
    read_results(args.input_file)


if __name__ == "__main__":
    main()
