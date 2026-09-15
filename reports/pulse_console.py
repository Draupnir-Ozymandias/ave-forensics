"""Console reporting for pulse-pattern analysis."""


def print_pulse_summary(result: dict) -> None:
    print("\nPulse and isochronic pattern analysis:")
    print(f"Overall: {result['classification'].replace('_', ' ')}")
    for name, channel in result["channels"].items():
        rate = channel["pulse_rate_hz"]
        rate_text = f"{rate:.3f} Hz" if rate is not None else "not resolved"
        print(
            f"{name.title()}: {channel['classification'].replace('_', ' ')} | "
            f"rate {rate_text} | regularity {channel['onset_regularity']:.3f} | "
            f"duty {channel['duty_cycle'] if channel['duty_cycle'] is not None else '—'}"
        )
    print(
        "Stereo timing: "
        f"{result['stereo_relationship']['classification'].replace('_', ' ')}"
    )
    print(
        f"Timeline: {result['timeline_summary']['window_count']} windows, "
        f"{result['timeline_summary']['transition_count']} classification transitions"
    )
