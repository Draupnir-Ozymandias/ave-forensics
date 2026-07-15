import csv
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
import numpy as np

BANDS = [
    ("Delta", 0.5, 4),
    ("Theta", 4, 8),
    ("Alpha", 8, 13),
    ("Beta", 13, 30),
    ("Gamma", 30, 40),
]


def plot_timeline(csv_path="ave_timeline.csv", output_path="ave_timeline.png"):
    times = []
    diffs = []
    confidence = []
    correlation = []

    with open(csv_path, "r") as f:
        reader = csv.DictReader(f)

        for row in reader:
            if not row["difference_hz"]:
                continue

            times.append(float(row["start_seconds"]) / 60)
            diffs.append(float(row["difference_hz"]))
            confidence.append(float(row["confidence"]))
            correlation.append(float(row["left_right_correlation"]))

    x = np.array(times)
    y = np.array(diffs)
    c = np.array(confidence)
    r = np.array(correlation)

    fig, ax = plt.subplots(figsize=(16, 7))

    band_colors = {
        "Delta": "#c9b6ff",  # lavender
        "Theta": "#9fe7ff",  # cyan
        "Alpha": "#b9f5b1",  # green
        "Beta": "#ffd38a",  # orange
        "Gamma": "#ff9ecb",  # pink
    }

    for name, low, high in BANDS:
        ax.axhspan(
            low,
            high,
            color=band_colors[name],
            alpha=0.45,
            label=name,
        )

    points = np.array([x, y]).T.reshape(-1, 1, 2)
    segments = np.concatenate([points[:-1], points[1:]], axis=1)

    lc = LineCollection(
        segments,
        cmap="viridis",
        norm=plt.Normalize(0, 1),
        linewidth=2,
    )
    lc.set_array(c[:-1])
    ax.add_collection(lc)

    sizes = 40 + (r * 160)

    scatter = ax.scatter(
        x,
        y,
        c=c,
        cmap="viridis",
        s=sizes,
        edgecolors="black",
        linewidths=0.4,
        zorder=3,
    )

    cb = fig.colorbar(scatter, ax=ax)
    cb.set_label("Confidence")

    ax.set_title("AVE Time-Resolved Entrainment Candidate Map")
    ax.set_xlabel("Time (minutes)")
    ax.set_ylabel("Candidate Difference Frequency (Hz)")

    ax.set_ylim(0, 40)
    ax.set_xlim(min(x), max(x))

    ax.grid(True, alpha=0.25)
    ax.legend(loc="upper right")

    plt.tight_layout()
    plt.savefig(output_path, dpi=200)
    plt.close()
