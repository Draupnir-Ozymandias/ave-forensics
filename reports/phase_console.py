from collections import Counter
from statistics import median
from typing import Any


def print_phase_timeline(
    timeline: list[dict[str, Any]],
    limit: int = 20,
) -> None:
    print("\nTime-resolved phase relationship analysis:")

    if not timeline:
        print("No phase windows were available.")
        return

    behaviors = Counter(item["phase_behavior"] for item in timeline)
    dominant_behavior, dominant_count = behaviors.most_common(1)[0]
    estimated_differences = [
        item["estimated_difference_hz"] for item in timeline
    ]
    detrended_locking = [
        item["detrended_phase_locking_value"] for item in timeline
    ]

    print(
        f"Dominant behavior: {dominant_behavior} "
        f"({dominant_count}/{len(timeline)} windows)"
    )
    print(
        f"Median phase-derived difference: "
        f"{median(estimated_differences):.4f} Hz"
    )
    print(
        f"Median detrended phase locking: "
        f"{median(detrended_locking):.4f}"
    )

    for item in timeline[:limit]:
        print(
            f"{item['start_seconds']:>7.2f}s - "
            f"{item['end_seconds']:>7.2f}s | "
            f"Δphase {item['estimated_difference_hz']:>7.3f} Hz | "
            f"offset {item['mean_phase_offset_degrees']:>7.2f}° | "
            f"PLV {item['raw_phase_locking_value']:.3f} | "
            f"detrended {item['detrended_phase_locking_value']:.3f} | "
            f"{item['phase_behavior']}"
        )
