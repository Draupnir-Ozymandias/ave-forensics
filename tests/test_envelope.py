import numpy as np

from analysis.envelope import (
    analyze_carrier_envelope,
    select_envelope_carrier_pair,
)


def generate_am_signal(
    sample_rate: int,
    duration_seconds: float,
    carrier_hz: float,
    modulation_hz: float,
    modulation_depth: float,
) -> np.ndarray:
    time = np.arange(int(sample_rate * duration_seconds)) / sample_rate

    envelope = 1.0 + modulation_depth * np.sin(2.0 * np.pi * modulation_hz * time)

    carrier = np.sin(2.0 * np.pi * carrier_hz * time)

    return envelope * carrier


def test_detects_three_hz_amplitude_modulation():
    sample_rate = 4000

    audio = generate_am_signal(
        sample_rate=sample_rate,
        duration_seconds=20.0,
        carrier_hz=100.0,
        modulation_hz=3.0,
        modulation_depth=0.60,
    )

    result = analyze_carrier_envelope(
        audio=audio,
        sample_rate=sample_rate,
        center_frequency_hz=100.0,
        bandwidth_hz=20.0,
        envelope_sample_rate=200,
        min_modulation_hz=0.5,
        max_modulation_hz=10.0,
    )

    dominant = result["dominant_modulation"]

    assert dominant is not None
    assert abs(dominant["modulation_hz"] - 3.0) < 0.2
    assert dominant["relative_power"] > 0.9

    assert abs(result["modulation_depth"] - 0.60) < 0.12


def test_rejects_invalid_carrier_band():
    sample_rate = 1000
    audio = np.zeros(sample_rate)

    try:
        analyze_carrier_envelope(
            audio=audio,
            sample_rate=sample_rate,
            center_frequency_hz=499.0,
            bandwidth_hz=10.0,
        )
    except ValueError:
        return

    raise AssertionError("Expected invalid Nyquist band to raise ValueError")


def test_selects_acoustic_carrier_instead_of_low_frequency_track():
    pairs = [
        {"left_carrier_hz": 2.72, "right_carrier_hz": 2.74, "duration_seconds": 100, "confidence": .9, "amplitude_balance": 1, "pair_type": "shared_carrier"},
        {"left_carrier_hz": 130.97, "right_carrier_hz": 130.96, "duration_seconds": 50, "confidence": .8, "amplitude_balance": 1, "pair_type": "shared_carrier"},
    ]

    selected = select_envelope_carrier_pair(pairs)

    assert selected == pairs[1]


def test_selects_longest_supported_non_harmonic_carrier_pair():
    short = {"left_carrier_hz": 24.0, "right_carrier_hz": 24.1, "duration_seconds": 45, "confidence": .9, "amplitude_balance": 1, "pair_type": "shared_carrier"}
    long = {"left_carrier_hz": 87.0, "right_carrier_hz": 88.0, "duration_seconds": 255, "confidence": .6, "amplitude_balance": .9, "pair_type": "beat_candidate"}
    harmonic = {"left_carrier_hz": 29.0, "right_carrier_hz": 58.0, "duration_seconds": 300, "confidence": 1, "amplitude_balance": 1, "pair_type": "harmonic_relationship"}

    assert select_envelope_carrier_pair([short, long, harmonic]) == long
