"""Diagnostic plots for the AES last-round prime+probe correlation attack.

Renders a 3-panel figure from an aes_pp CSV:

  A - KEY RECOVERY: correlation score for every key-byte guess, per ciphertext
      byte (brightest column = winning guess). With --key, the true key byte is
      circled so you can see at a glance which bytes recovered.
  B - TABLE LOCATION: each T-table group's score vs. cache set; a sharp peak
      means that table was localized. The four peaks sit ~8 sets apart.
  C - RAW SIGNAL: mean probe time per cache set (where the T-tables evict us).

Reuses the attack code in read_aes_results.py so the plotted scores are exactly
what the recovery uses.

Usage:
    python plot_aes_diag.py results/raw/aes_results_20M.csv \
        --key 00112233445566778899aabbccddeeff \
        --title "20M capture" -o results/aes_diag_20M.png
    python plot_aes_diag.py results/raw/aes_results_20M.csv --limit 3000000   # subsample
"""
import argparse

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

import read_aes_results as rr

GROUP_COLORS = ['#4C72B0', '#DD8452', '#55A868', '#C44E52']  # groups 0..3


def round10_key(master_key_hex):
    """Expand an AES-128 master key and return round-key 10 as 16 ints."""
    master = bytes.fromhex(master_key_hex)
    words = [list(master[i:i + 4]) for i in range(0, 16, 4)]
    for i in range(4, 44):
        tmp = list(words[i - 1])
        if i % 4 == 0:
            tmp = [rr.SBOX[tmp[1]], rr.SBOX[tmp[2]], rr.SBOX[tmp[3]], rr.SBOX[tmp[0]]]
            tmp[0] ^= rr.RCON[i // 4]
        words.append([words[i - 4][j] ^ tmp[j] for j in range(4)])
    return np.array(sum(words[40:44], []), dtype=int)


def score_matrices(df, prepared_data, num_sets):
    """Per ciphertext byte: a [key_byte (256) x table_start_set (num_sets)] score matrix."""
    matrices = []
    for byte_index in range(rr.CIPHER_TEXT_SIZE):
        results = rr.run_correlation(df, byte_index, prepared_data=prepared_data)
        matrix = (
            results.pivot(index='key_byte_value', columns='table_start_set', values='score')
            .sort_index()
            .reindex(columns=range(num_sets))
            .to_numpy()
        )
        matrices.append(matrix)
    return matrices


def recover(matrices):
    """Group-shared table_start_set selection + per-byte key pick (matches read_results)."""
    group_start_set = {}
    predicted = [0] * rr.CIPHER_TEXT_SIZE
    for group in range(4):
        bytes_in_group = [group + 4 * j for j in range(rr.CIPHER_TEXT_SIZE // 4)]
        start_set = int(np.argmax(sum(matrices[i].max(axis=0) for i in bytes_in_group)))
        group_start_set[group] = start_set
        for i in bytes_in_group:
            predicted[i] = int(np.argmax(matrices[i][:, start_set]))
    return group_start_set, predicted


def make_figure(df, title, output_path, true_k10=None):
    prepared_data = rr._prepare_correlation_data(df)
    num_sets = prepared_data[4]
    mean_latency = prepared_data[0].ravel()

    matrices = score_matrices(df, prepared_data, num_sets)
    group_start_set, predicted = recover(matrices)
    n_rows = df.height
    n_correct = (sum(predicted[i] == true_k10[i] for i in range(16))
                 if true_k10 is not None else None)

    plt.rcParams.update({'font.size': 8, 'axes.edgecolor': '#888', 'axes.linewidth': .6,
                         'figure.facecolor': 'white', 'axes.titlesize': 9})
    fig = plt.figure(figsize=(13.5, 8))
    grid = fig.add_gridspec(2, 2, height_ratios=[1.25, 1], hspace=.42, wspace=.2)

    # A - key recovery heatmap (score vs key, at each byte's group start set)
    ax_a = fig.add_subplot(grid[0, :])
    profile = np.vstack([matrices[i][:, group_start_set[i % 4]] for i in range(16)])
    norm = ((profile - profile.min(1, keepdims=True))
            / (profile.max(1, keepdims=True) - profile.min(1, keepdims=True) + 1e-12))
    image = ax_a.imshow(norm, aspect='auto', cmap='viridis')
    ax_a.scatter(predicted, range(16), marker='_', s=120, color='w', lw=1.4)
    handles = [Line2D([], [], marker='_', color='w', mew=1.6, ls='', ms=12, label="script's pick")]
    if true_k10 is not None:
        ax_a.scatter(true_k10, range(16), marker='o', s=90,
                     facecolors='none', edgecolors='#E8000B', lw=1.8)
        handles.insert(0, Line2D([], [], marker='o', mfc='none', mec='#E8000B', mew=1.8,
                                 ls='', ms=9, label='true key'))
    ax_a.legend(handles=handles, loc='upper right', framealpha=.85, fontsize=7.5)
    ax_a.set_yticks(range(16))
    ax_a.set_yticklabels([f'byte {i}' for i in range(16)])
    for i in range(16):
        ax_a.get_yticklabels()[i].set_color(GROUP_COLORS[i % 4])
    ax_a.set_xlabel('key-byte hypothesis (0-255)')
    ax_a.set_title('A - KEY RECOVERY: correlation score for every key guess, per ciphertext byte. '
                   'Bright column = winning guess; recovery works when the true-key circle is on it.')
    fig.colorbar(image, ax=ax_a, fraction=.025, pad=.01).set_label('normalised score (per row)')

    # B - table localisation
    ax_b = fig.add_subplot(grid[1, 0])
    for group in range(4):
        bytes_in_group = [group + 4 * j for j in range(4)]
        group_score = sum(matrices[i].max(axis=0) for i in bytes_in_group)
        ax_b.plot(range(num_sets), group_score, color=GROUP_COLORS[group], lw=1.3,
                  label=f'group {group}  -> set {group_start_set[group]}')
        ax_b.axvline(group_start_set[group], color=GROUP_COLORS[group], lw=.7, ls=':', alpha=.6)
    ax_b.set_title('B - TABLE LOCATION: each group\'s score vs. cache set.\n'
                   'Sharp peak = table located. Peaks sit ~8 sets apart (4 tables, 8 sets each).')
    ax_b.set_xlabel('cache set (table start position)')
    ax_b.set_ylabel('group score (higher = better fit)')
    ax_b.legend(fontsize=7, title='T-table group')

    # C - raw per-set signal
    ax_c = fig.add_subplot(grid[1, 1])
    ax_c.plot(range(num_sets), mean_latency, color='#333', lw=1.2)
    low, high = min(group_start_set.values()), max(group_start_set.values()) + 8
    ax_c.axvspan(low, high, color='#ffd54f', alpha=.25)
    ax_c.text((low + high) / 2, ax_c.get_ylim()[1], 'T-tables live here',
              ha='center', va='top', fontsize=7, color='#8a6d00')
    ax_c.set_title('C - RAW SIGNAL: average probe time per cache set.\n'
                   'Higher = victim evicted our data there (the T-tables).')
    ax_c.set_xlabel('cache set')
    ax_c.set_ylabel('mean probe time (cycles)')

    suptitle = f'{title}   -   {n_rows:,} traces'
    if n_correct is not None:
        suptitle += f'   -   recovered {n_correct}/16 key bytes'
    fig.suptitle(suptitle, fontsize=12, fontweight='bold', y=.995)
    fig.savefig(output_path, dpi=140, bbox_inches='tight')
    print(f'{output_path}: traces={n_rows} start_sets={dict(group_start_set)}'
          + (f' recovered={n_correct}/16' if n_correct is not None else ''))


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('input_file', help='CSV produced by aes_pp')
    parser.add_argument('-o', '--output', default='results/aes_diag.png',
                        help='output PNG path (default: results/aes_diag.png)')
    parser.add_argument('--limit', type=int, default=None,
                        help='use only the first N rows (subsample for comparison)')
    parser.add_argument('--key', default=None,
                        help='known 32-hex master key; adds ground-truth markers + score')
    parser.add_argument('--title', default='AES prime+probe', help='figure title')
    args = parser.parse_args()

    df = rr._read_aes_pp_results(args.input_file)
    if args.limit:
        df = df.head(args.limit)
    true_k10 = round10_key(args.key) if args.key else None
    make_figure(df, args.title, args.output, true_k10=true_k10)


if __name__ == '__main__':
    main()
