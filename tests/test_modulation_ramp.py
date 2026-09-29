import numpy as np

from analysis.modulation_ramp import analyze_modulation_ramp
from evidence.adapters import modulation_ramp_to_evidence
from evidence.schema import validate_evidence_object


SAMPLE_RATE = 4000
CARRIER_HZ = 220.0
DURATION = 12.0


def am_ramp(start_hz, end_hz, depth=0.7):
    time = np.arange(int(SAMPLE_RATE * DURATION)) / SAMPLE_RATE
    slope = (end_hz - start_hz) / DURATION
    phase = 2.0 * np.pi * (start_hz * time + 0.5 * slope * time ** 2)
    envelope = 1.0 + depth * np.sin(phase)
    return envelope * np.sin(2.0 * np.pi * CARRIER_HZ * time)


def analyze(signal, **overrides):
    options = {
        "carrier_center_hz": CARRIER_HZ,
        "carrier_bandwidth_hz": 70.0,
        "envelope_sample_rate": 200,
        "min_rate_hz": 2.0,
        "max_rate_hz": 25.0,
        "window_seconds": 2.0,
        "hop_seconds": 0.5,
    }
    options.update(overrides)
    return analyze_modulation_ramp(signal, SAMPLE_RATE, **options)


def test_recovers_blind_increasing_smooth_am_ramp():
    result = analyze(am_ramp(4.0, 20.0))

    assert result["classification"] == "continuous_modulation_ramp"
    assert result["fit"]["direction"] == "increasing"
    assert result["coverage"] >= 0.9
    assert abs(result["fit"]["slope_hz_per_second"] - 16.0 / 12.0) < 0.12
    assert abs(result["fit"]["fitted_start_rate_hz"] - (4.0 + 16.0 / 12.0)) < 0.5
    assert abs(result["fit"]["fitted_end_rate_hz"] - (20.0 - 16.0 / 12.0)) < 0.5
    assert result["fit"]["residual_rmse_hz"] < 0.35
    assert abs(result["fit"]["fitted_scope_start_rate_hz"] - 4.0) < 0.5
    assert abs(result["fit"]["fitted_scope_end_rate_hz"] - 20.0) < 0.5


def test_classifies_constant_smooth_am_as_stable_not_ramp():
    result = analyze(am_ramp(8.0, 8.0))

    assert result["classification"] == "stable_modulation"
    assert result["fit"]["direction"] == "stable"
    assert abs(result["fit"]["fitted_start_rate_hz"] - 8.0) < 0.15
    assert abs(result["fit"]["fitted_end_rate_hz"] - 8.0) < 0.15


def test_constant_carrier_remains_unsupported():
    time = np.arange(int(SAMPLE_RATE * DURATION)) / SAMPLE_RATE
    signal = np.sin(2.0 * np.pi * CARRIER_HZ * time)
    result = analyze(signal)

    assert result["classification"] == "insufficient_support"
    assert result["fit"] is None
    assert result["coverage"] < 0.5
    assert result["unsupported_intervals"]


def test_broadband_noise_does_not_become_a_supported_ramp():
    for seed in range(20):
        signal = np.random.default_rng(seed).normal(
            0.0, 1.0, int(SAMPLE_RATE * DURATION)
        )
        result = analyze(signal)

        assert result["classification"] == "insufficient_support"
        assert result["fit"] is None


def test_result_adapts_to_canonical_evidence_with_visible_limits():
    result = analyze(am_ramp(4.0, 20.0))
    evidence = modulation_ramp_to_evidence(
        result, {"run_id": "test"}, channel="left"
    )

    validate_evidence_object(evidence)
    assert evidence["evidence_type"] == "continuous_modulation_ramp"
    assert evidence["evidence_level"] == "reconstruction"
    assert evidence["scope"]["channels"] == ["left"]
    assert any(item["name"] == "ramp_slope" for item in evidence["measurements"])
    assert any("efficacy" in item for item in evidence["limitations"])


def test_preserves_original_source_time_for_bounded_analysis():
    result = analyze(am_ramp(4.0, 20.0), time_offset_seconds=22.0)
    evidence = modulation_ramp_to_evidence(result, channel="left")

    assert result["source_time_range_seconds"] == {"start": 22.0, "end": 34.0}
    assert result["windows"][0]["start_seconds"] == 22.0
    assert result["fit"]["first_supported_center_seconds"] == 23.0
    assert evidence["scope"]["time_range_seconds"] == {"start": 22.0, "end": 34.0}


def test_rejects_envelope_rate_at_or_below_nyquist_requirement():
    signal = am_ramp(4.0, 20.0)
    try:
        analyze(signal, envelope_sample_rate=50, max_rate_hz=25.0)
    except ValueError as error:
        assert "twice max_rate_hz" in str(error)
    else:
        raise AssertionError("expected invalid envelope sample rate to fail")
