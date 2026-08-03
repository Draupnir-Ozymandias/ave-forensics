import numpy as np

from analysis.phase import (
    analyze_phase_over_time,
    analyze_phase_relationship,
)


def generate_tone(
    sample_rate: int,
    duration_seconds: float,
    frequency_hz: float,
    phase_radians: float = 0.0,
) -> np.ndarray:
    time = np.arange(int(sample_rate * duration_seconds)) / sample_rate
    return np.sin(
        2.0 * np.pi * frequency_hz * time + phase_radians
    )


def circular_error(value: float, expected: float) -> float:
    return abs((value - expected + np.pi) % (2.0 * np.pi) - np.pi)


def test_detects_zero_phase_offset():
    sample_rate = 2000
    left = generate_tone(sample_rate, 5.0, 100.0)
    right = generate_tone(sample_rate, 5.0, 100.0)

    result = analyze_phase_relationship(
        left_audio=left,
        right_audio=right,
        sample_rate=sample_rate,
        left_center_frequency_hz=100.0,
        right_center_frequency_hz=100.0,
        bandwidth_hz=20.0,
    )

    assert abs(result["estimated_difference_hz"]) < 0.02
    assert circular_error(result["mean_phase_offset_radians"], 0.0) < 0.05
    assert result["raw_phase_locking_value"] > 0.99
    assert result["phase_behavior"] == "phase_locked"


def test_detects_ninety_degree_phase_offset():
    sample_rate = 2000
    left = generate_tone(sample_rate, 5.0, 100.0)
    right = generate_tone(sample_rate, 5.0, 100.0, np.pi / 2.0)

    result = analyze_phase_relationship(
        left_audio=left,
        right_audio=right,
        sample_rate=sample_rate,
        left_center_frequency_hz=100.0,
        right_center_frequency_hz=100.0,
        bandwidth_hz=20.0,
    )

    assert circular_error(
        result["mean_phase_offset_radians"],
        np.pi / 2.0,
    ) < 0.05
    assert result["raw_phase_locking_value"] > 0.99
    assert result["phase_behavior"] == "phase_locked"


def test_detects_stable_two_hz_phase_rotation():
    sample_rate = 2000
    left = generate_tone(sample_rate, 5.0, 100.0)
    right = generate_tone(sample_rate, 5.0, 102.0)

    result = analyze_phase_relationship(
        left_audio=left,
        right_audio=right,
        sample_rate=sample_rate,
        left_center_frequency_hz=100.0,
        right_center_frequency_hz=102.0,
        bandwidth_hz=20.0,
    )

    assert abs(result["estimated_difference_hz"] - 2.0) < 0.05
    assert result["raw_phase_locking_value"] < 0.1
    assert result["detrended_phase_locking_value"] > 0.99
    assert result["phase_behavior"] == "stable_phase_rotation"


def test_independent_noise_is_not_phase_locked():
    sample_rate = 2000
    rng = np.random.default_rng(20260801)
    left = rng.normal(size=sample_rate * 20)
    right = rng.normal(size=sample_rate * 20)

    result = analyze_phase_relationship(
        left_audio=left,
        right_audio=right,
        sample_rate=sample_rate,
        left_center_frequency_hz=100.0,
        right_center_frequency_hz=100.0,
        bandwidth_hz=20.0,
    )

    assert result["detrended_phase_locking_value"] < 0.3
    assert result["phase_behavior"] == "unstable_or_unrelated"


def test_phase_timeline_preserves_known_detuning():
    sample_rate = 2000
    left = generate_tone(sample_rate, 12.0, 100.0)
    right = generate_tone(sample_rate, 12.0, 102.0)

    timeline = analyze_phase_over_time(
        left_audio=left,
        right_audio=right,
        sample_rate=sample_rate,
        left_center_frequency_hz=100.0,
        right_center_frequency_hz=102.0,
        bandwidth_hz=20.0,
        window_seconds=4.0,
        hop_seconds=2.0,
    )

    assert len(timeline) == 5
    assert all(
        abs(item["estimated_difference_hz"] - 2.0) < 0.05
        for item in timeline
    )
    assert all(
        item["phase_behavior"] == "stable_phase_rotation"
        for item in timeline
    )
