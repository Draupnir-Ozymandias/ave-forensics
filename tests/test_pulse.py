import numpy as np

from analysis.pulse import analyze_pulse_patterns
from evidence.adapters import pulse_analysis_to_evidence
from evidence.schema import validate_evidence_object


SAMPLE_RATE = 4000
DURATION = 12.0


def carrier(gain):
    time = np.arange(int(SAMPLE_RATE * DURATION)) / SAMPLE_RATE
    return np.sin(2 * np.pi * 220.0 * time) * gain(time)


def square_gain(rate, duty=0.25, offset=0.0):
    return lambda time: (((time * rate + offset) % 1.0) < duty).astype(float)


def analyze(left, right=None, **overrides):
    audio = left if right is None else np.vstack([left, right])
    options = {
        "window_seconds": 4.0,
        "hop_seconds": 2.0,
        "minimum_pulse_count": 4,
    }
    options.update(overrides)
    return analyze_pulse_patterns(audio, SAMPLE_RATE, **options)


def test_detects_synchronized_hard_gated_isochronic_candidate():
    signal = carrier(square_gain(8.0, duty=0.25))
    result = analyze(signal, signal)

    assert result["classification"] == "synchronized_isochronic_pulse_candidate"
    assert result["stereo_relationship"]["classification"] == "synchronized"
    assert abs(result["channels"]["left"]["pulse_rate_hz"] - 8.0) < 0.1
    assert abs(result["channels"]["left"]["duty_cycle"] - 0.25) < 0.05
    assert result["channels"]["left"]["onset_regularity"] > 0.95
    assert result["channels"]["left"]["state_separation"] > 0.85


def test_distinguishes_smooth_amplitude_modulation_from_hard_gating():
    signal = carrier(
        lambda time: 0.55 + 0.45 * np.sin(2 * np.pi * 8.0 * time)
    )
    result = analyze(signal, signal)

    assert result["classification"] == "smooth_amplitude_modulation"
    assert abs(result["channels"]["left"]["pulse_rate_hz"] - 8.0) < 0.1
    assert result["channels"]["left"]["classification"] == "smooth_amplitude_modulation"


def test_detects_alternating_stereo_pulses():
    left = carrier(square_gain(5.0, duty=0.25))
    right = carrier(square_gain(5.0, duty=0.25, offset=0.5))
    result = analyze(left, right)

    assert result["classification"] == "alternating_isochronic_pulse_candidate"
    assert result["stereo_relationship"]["classification"] == "alternating"
    assert 0.4 <= result["stereo_relationship"]["median_offset_fraction"] <= 0.5


def test_preserves_non_alternating_stereo_offset():
    left = carrier(square_gain(5.0, duty=0.2))
    right = carrier(square_gain(5.0, duty=0.2, offset=0.25))
    result = analyze(left, right)

    assert result["classification"] == "stereo_offset_isochronic_pulse_candidate"
    assert result["stereo_relationship"]["classification"] == "phase_offset"


def test_constant_amplitude_is_not_reported_as_a_pulse_train():
    signal = carrier(lambda time: np.ones_like(time))
    result = analyze(signal, signal)

    assert result["classification"] == "no_periodic_pulse"
    assert result["channels"]["left"]["pulse_rate_hz"] is None


def test_irregular_transients_are_not_reported_as_isochronic():
    rng = np.random.default_rng(4)
    starts = np.cumsum(rng.uniform(0.08, 0.55, 45))

    def gain(time):
        output = np.zeros_like(time)
        for start in starts[starts < DURATION]:
            output[(time >= start) & (time < start + 0.025)] = 1.0
        return output

    signal = carrier(gain)
    result = analyze(signal, signal)

    assert result["classification"] == "irregular_transients"
    assert result["channels"]["left"]["interval_cv"] > 0.2


def test_timeline_preserves_rate_changes_and_reports_transitions():
    time = np.arange(int(SAMPLE_RATE * DURATION)) / SAMPLE_RATE
    gain = np.where(
        time < DURATION / 2,
        ((time * 6.0) % 1.0) < 0.25,
        ((time * 12.0) % 1.0) < 0.25,
    ).astype(float)
    signal = np.sin(2 * np.pi * 220.0 * time) * gain
    result = analyze(signal, signal, window_seconds=3.0, hop_seconds=3.0)
    rates = [item["channels"]["left"]["pulse_rate_hz"] for item in result["timeline"]]

    assert abs(rates[0] - 6.0) < 0.1
    assert abs(rates[-1] - 12.0) < 0.1


def test_pulse_result_adapts_to_canonical_evidence():
    signal = carrier(square_gain(8.0))
    result = analyze(signal, signal)
    evidence = pulse_analysis_to_evidence(result, {"run_id": "test"})

    validate_evidence_object(evidence)
    assert evidence["evidence_type"] == "broadband_pulse_pattern"
    assert evidence["evidence_level"] == "detection"
    assert any(
        measurement["name"] == "primary_pulse_rate"
        and abs(measurement["value"] - 8.0) < 0.1
        for measurement in evidence["measurements"]
    )
