"""
Step 1 of adapting Prime+Prune+Probe to L1D: decide whether per-line hit/miss
classification is resolvable on this machine's clock. That is the prerequisite
for a "prune" step -- without a clean single-line threshold, pruning cannot tell
a resident line from an evicted one.

Input:  ./results/raw/line_latency_hist.csv  (phase,set,line,latency)
        produced by `make CFLAGS+=-DMEASURE_HIST pp && ./pp`
Output: ./results/line_latency_hist.png  plus a printed verdict.
"""

import numpy as np
import polars as pl
import matplotlib.pyplot as plt

CSV = "./results/raw/line_latency_hist.csv"
PNG = "./results/line_latency_hist.png"

SCHEMA = {
    "phase": pl.Categorical,
    "set": pl.UInt16,
    "line": pl.UInt8,
    "latency": pl.UInt32,
}


def best_threshold(hit, miss):
    """Sweep candidate thresholds and pick the one maximizing balanced accuracy
    (mean of hit-specificity and miss-sensitivity). Returns (threshold, spec,
    sens, balanced_accuracy)."""
    lo = int(min(hit.min(), miss.min()))
    hi = int(max(hit.max(), miss.max()))
    # cap the sweep range so a few huge outliers don't blow it up
    hi = min(hi, int(np.percentile(miss, 99.9)) + 5)
    best = (lo, 0.0, 0.0, 0.0)
    for t in range(lo, hi + 1):
        spec = np.mean(hit < t)          # hits correctly called resident
        sens = np.mean(miss >= t)        # misses correctly called evicted
        bal = 0.5 * (spec + sens)
        if bal > best[3]:
            best = (t, spec, sens, bal)
    return best


def main():
    df = pl.read_csv(CSV, schema_overrides=SCHEMA)
    hit = df.filter(pl.col("phase") == "hit")["latency"].to_numpy()
    miss = df.filter(pl.col("phase") == "miss")["latency"].to_numpy()

    def stats(name, a):
        qs = np.percentile(a, [1, 5, 50, 95, 99])
        print(f"{name:5s} n={a.size:>9d}  "
              f"p1={qs[0]:.0f} p5={qs[1]:.0f} p50={qs[2]:.0f} "
              f"p95={qs[3]:.0f} p99={qs[4]:.0f}  mean={a.mean():.1f}")

    print("single-line latency (clock ticks):")
    stats("hit", hit)
    stats("miss", miss)

    thr, spec, sens, bal = best_threshold(hit, miss)
    print(f"\nbest threshold = {thr} ticks")
    print(f"  hit  classified resident (specificity): {spec*100:.1f}%")
    print(f"  miss classified evicted  (sensitivity): {sens*100:.1f}%")
    print(f"  balanced accuracy: {bal*100:.1f}%")

    # empirical stable way count: per (rep-equivalent) miss vector, how many
    # lines actually flipped to evicted. We approximate per-probe grouping by
    # counting evicted fraction * NUM_LINES from the miss phase overall.
    num_lines = int(df["line"].max()) + 1
    evicted_per_probe = np.mean(miss >= thr) * num_lines
    print(f"\nempirical evicted ways after full-set victim: "
          f"{evicted_per_probe:.1f} / {num_lines}")

    if bal >= 0.9:
        verdict = "SEPARABLE -> per-line prune is viable (proceed to full PPP)."
    elif bal >= 0.75:
        verdict = "MARGINAL -> prune may work with multi-sample voting per line."
    else:
        verdict = "NOT SEPARABLE -> fall back to the lightweight prune path."
    print(f"\nverdict: {verdict}")

    # plot overlaid histograms (log y so the miss tail is visible)
    hi = int(min(max(hit.max(), miss.max()), np.percentile(miss, 99.9) + 5))
    bins = np.arange(0, hi + 2)
    plt.figure(figsize=(10, 5))
    plt.hist(hit, bins=bins, alpha=0.6, label="hit (resident)", color="#2b8cbe")
    plt.hist(miss, bins=bins, alpha=0.6, label="miss (evicted)", color="#e34a33")
    plt.axvline(thr, color="black", linestyle="--", label=f"threshold={thr}")
    plt.yscale("log")
    plt.xlabel("single-line probe latency (clock ticks)")
    plt.ylabel("count (log)")
    plt.title(f"Per-line hit vs miss latency  (balanced acc {bal*100:.1f}%)")
    plt.legend()
    plt.tight_layout()
    plt.savefig(PNG, dpi=200, bbox_inches="tight")
    print(f"wrote {PNG}")


if __name__ == "__main__":
    main()
