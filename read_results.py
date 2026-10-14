import pandas as pd
import matplotlib.pyplot as plt


def read_results(file_path):
    df = pd.read_csv(file_path)

    # only need results for when the probed set == the victim set
    results = df[df["probe_set"] == df["victim_set"]]
    results = results[["victim_set", "victim_line_count", "probe_time"]].reset_index(drop=True)

    # derive geometry from the capture so the plot ticks match NUM_SETS/NUM_LINES
    # the binary was built with (E-core=8 ways, P-core=16), instead of hardcoding.
    num_sets = int(results["victim_set"].max()) + 1
    num_lines = int(results["victim_line_count"].max())
    print(f"detected geometry: {num_sets} sets, up to {num_lines} victim lines")

    # Clip gross outliers (scheduler hiccups, the odd page-boundary set) before
    # aggregating so a few huge samples don't dominate a set's mean.
    bottom = results["probe_time"].quantile(0.05)
    top = results["probe_time"].quantile(0.95)
    results_filtered = results[
        (results["probe_time"] >= bottom) & (results["probe_time"] <= top)
    ]

    avg = results_filtered.groupby(
        ["victim_line_count", "victim_set"], as_index=False
    )["probe_time"].mean()

    heatmap_abs = avg.pivot(
        index="victim_line_count", columns="victim_set", values="probe_time"
    )

    # Per-set normalization: the victim signal is a small bump on top of a large,
    # per-set-varying baseline (probe-order position, TLB, etc.). Subtracting each
    # set's own line_count==0 baseline removes those vertical stripes AND the
    # constant measurement overhead, leaving just the eviction signal -- the extra
    # probe time caused by the victim touching that set.
    baseline = heatmap_abs.loc[0]
    heatmap_norm = heatmap_abs.sub(baseline, axis="columns")

    fig, (ax_abs, ax_norm) = plt.subplots(2, 1, figsize=(12, 8))

    im0 = ax_abs.imshow(heatmap_abs, aspect="auto", origin="lower")
    fig.colorbar(im0, ax=ax_abs, label="Average probe time")
    ax_abs.set_title("Absolute average probe time (per-set baseline dominates)")
    ax_abs.set_xlabel("Cache set")
    ax_abs.set_ylabel("Number of accessed lines")
    ax_abs.set_xticks(range(0, num_sets, 4))
    ax_abs.set_yticks(range(0, num_lines + 1))

    # Normalized panel: force 0 to the bottom of the scale so "no signal" is dark
    # and any eviction reads as positive.
    im1 = ax_norm.imshow(
        heatmap_norm, aspect="auto", origin="lower", vmin=0, vmax=heatmap_norm.values.max()
    )
    fig.colorbar(im1, ax=ax_norm, label="Probe time above set's own baseline")
    ax_norm.set_title("Per-set normalized probe time (eviction signal)")
    ax_norm.set_xlabel("Cache set")
    ax_norm.set_ylabel("Number of accessed lines")
    ax_norm.set_xticks(range(0, num_sets, 4))
    ax_norm.set_yticks(range(0, num_lines + 1))

    fig.tight_layout()
    fig.savefig("./results/prime_probe_heatmap.png", dpi=200, bbox_inches="tight")
    plt.show()


def main():
    file_path = "./results/raw/results.csv"
    read_results(file_path)


if __name__ == "__main__":
    main()
