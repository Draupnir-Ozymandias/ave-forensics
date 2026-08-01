from typing import Any


def print_global_envelope_results(
    carrier_center_hz: float,
    left_result: dict[str, Any],
    right_result: dict[str, Any],
) -> None:
    print("\nCarrier-envelope analysis:")
    print(f"Carrier region: {carrier_center_hz:.3f} Hz")
    print(f"Left modulation depth: " f"{left_result['modulation_depth']:.4f}")
    print(f"Right modulation depth: " f"{right_result['modulation_depth']:.4f}")

    print("\nLeft envelope modulation peaks:")
    for peak in left_result["modulation_peaks"][:10]:
        print(
            f"  {peak['modulation_hz']:.3f} Hz | "
            f"relative power {peak['relative_power']:.4f}"
        )

    print("\nRight envelope modulation peaks:")
    for peak in right_result["modulation_peaks"][:10]:
        print(
            f"  {peak['modulation_hz']:.3f} Hz | "
            f"relative power {peak['relative_power']:.4f}"
        )


def print_envelope_timeline(
    left_timeline: list[dict[str, Any]],
    right_timeline: list[dict[str, Any]],
    limit: int = 20,
) -> None:
    print("\nTime-resolved carrier-envelope analysis:")

    for left_item, right_item in zip(
        left_timeline[:limit],
        right_timeline[:limit],
    ):
        left_dominant = left_item["dominant_modulation"]
        right_dominant = right_item["dominant_modulation"]

        left_hz = left_dominant["modulation_hz"] if left_dominant is not None else None
        right_hz = (
            right_dominant["modulation_hz"] if right_dominant is not None else None
        )

        left_power = (
            left_dominant["relative_power"] if left_dominant is not None else 0.0
        )
        right_power = (
            right_dominant["relative_power"] if right_dominant is not None else 0.0
        )

        print(
            f"{left_item['start_seconds']:>7.2f}s - "
            f"{left_item['end_seconds']:>7.2f}s | "
            f"L {str(left_hz):>5} Hz "
            f"(depth {left_item['modulation_depth']:.3f}, "
            f"power {left_power:.3f}) | "
            f"R {str(right_hz):>5} Hz "
            f"(depth {right_item['modulation_depth']:.3f}, "
            f"power {right_power:.3f})"
        )
