import json

import numpy as np

from analysis.stage_robustness import (
    analyze_stage_robustness,
    compare_confidence_threshold,
)


def smooth_stage(sample_rate=4000, seconds=3.0):
    time = np.arange(int(sample_rate * seconds)) / sample_rate
    envelope = 0.5 * (1.0 + np.sin(2 * np.pi * 10.0 * time))
    signal = 0.8 * envelope * np.sin(2 * np.pi * 440.0 * time)
    return np.vstack([signal, signal])


def test_robustness_analysis_is_deterministic_and_target_free():
    first = analyze_stage_robustness(smooth_stage(), 4000)
    second = analyze_stage_robustness(smooth_stage(), 4000)

    assert first == second
    assert first["baseline"]["construction_class"] == (
        "smooth_amplitude_modulation"
    )
    assert first["summary"]["variant_count"] == 19
    assert first["configuration"]["confidence_threshold_loaded"] is False
    assert "threshold" not in json.dumps(first["variants"])


def test_threshold_inside_observed_range_is_borderline_without_promotion():
    robustness = {
        "baseline": {"confidence": 0.749983},
        "variants": [
            {"confidence": 0.749320},
            {"confidence": 0.758564},
        ],
    }

    comparison = compare_confidence_threshold(robustness, 0.75)

    assert comparison["interpretation"] == "borderline_within_observed_variation"
    assert comparison["baseline_distance_from_threshold"] == 0.000017
    assert comparison["observed_robustness_radius"] == 0.008581
    assert comparison["observations_below_threshold"] == 2
    assert comparison["observations_at_or_above_threshold"] == 1
    assert comparison["changes_primary_support_state"] is False


def test_threshold_outside_observed_range_is_robustly_below():
    robustness = {
        "baseline": {"confidence": 0.70},
        "variants": [{"confidence": 0.69}, {"confidence": 0.71}],
    }

    comparison = compare_confidence_threshold(robustness, 0.75)

    assert comparison["interpretation"] == "robustly_below_observed_range"
