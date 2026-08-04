from typing import Any


def print_modulation_spectrum_summary(
    result: dict[str, Any],
    track_limit: int = 8,
) -> None:
    print("\nModulation spectrum reconstruction:")
    print(f"Classification: {result['classification']}")

    primary = result["primary_stereo_modulation"]

    if primary is not None:
        print(
            f"Primary shared modulation: "
            f"{primary['average_modulation_hz']:.3f} Hz"
        )
        print(
            f"Shared coverage: {primary['shared_coverage']:.1%} | "
            f"stereo difference "
            f"{primary['frequency_difference_hz']:.4f} Hz | "
            f"confidence {primary['confidence']:.4f}"
        )

    for channel in ("left", "right"):
        tracks = result[f"{channel}_tracks"]
        print(f"\n{channel.title()} modulation tracks:")

        if not tracks:
            print("  No significant modulation tracks.")
            continue

        for track in tracks[:track_limit]:
            print(
                f"  {track['start_seconds']:>7.2f}s - "
                f"{track['end_seconds']:>7.2f}s | "
                f"median {track['median_modulation_hz']:.3f} Hz "
                f"(mean {track['average_modulation_hz']:.3f}) | "
                f"coverage {track['coverage']:.1%} | "
                f"depth {track['median_modulation_depth']:.3f} | "
                f"power {track['median_relative_power']:.3f} | "
                f"drift {track['drift_hz_per_second']:+.4f} Hz/s | "
                f"{track['classification']}"
            )
