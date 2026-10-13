import pandas as pd
import matplotlib.pyplot as plt

def read_results(file_path):
    df = pd.read_csv(file_path)

    # only need results for when the probed set == the victim set
    results = df[df['probe_set'] == df['victim_set']]
    results = results[['victim_set', 'victim_line_count', 'probe_time']].reset_index(drop=True)

    # derive geometry from the capture so the plot ticks match NUM_SETS/NUM_LINES
    # the binary was built with (E-core=8 ways, P-core=16), instead of hardcoding.
    num_sets = int(results["victim_set"].max()) + 1
    num_lines = int(results["victim_line_count"].max())
    print(f"detected geometry: {num_sets} sets, up to {num_lines} victim lines")

    bottom = results["probe_time"].quantile(0.05)
    top = results["probe_time"].quantile(0.95)

    results_filtered = results[
        (results["probe_time"] >= bottom) &
        (results["probe_time"] <= top)
    ]

    avg_results = (results_filtered.groupby(["victim_line_count", "victim_set"], as_index=False)["probe_time"] .mean())

    heatmap_data = avg_results.pivot(
        index="victim_line_count",
        columns="victim_set",
        values="probe_time",
    )
    # vmin = results["probe_time"].quantile(0.05)
    # vmax = results["probe_time"].quantile(0.95)
    plt.figure(figsize=(12, 4))
    plt.imshow(
        heatmap_data,
        aspect="auto",
        origin="lower",
        # vmin=vmin,
        # vmax=vmax
    )

    plt.colorbar(label="Average probe time")
    plt.xlabel("Cache set")
    plt.ylabel("Number of accessed lines")
    plt.title("Average probe time by cache set and victim accesses")

    plt.xticks(range(0, num_sets, 4))
    plt.yticks(range(0, num_lines + 1))

    plt.tight_layout()
    plt.savefig("./results/prime_probe_heatmap.png", dpi=200, bbox_inches="tight")
    plt.show()

def main():
    file_path = "./results/raw/results.csv"
    read_results(file_path)

if __name__ == "__main__":
    main()
