import numpy as np

from analysis.multimodal_clock import compare_clock_series
from verification.demo_observation import DemoObservationError, _validate_request


def test_clock_series_reports_zero_lag_alignment():
    random = np.random.default_rng(42)
    signal = random.normal(size=900)
    audio = np.column_stack([signal, signal * 0.8])
    video = np.vstack([signal, signal * 0.8])

    result = compare_clock_series(video, audio, frame_rate_hz=60.0)

    assert result["clock_alignment"] is True
    assert result["maximum_absolute_lag_frames"] == 0
    assert result["minimum_component_correlation"] == 1.0


def test_clock_series_rejects_multi_frame_offset():
    random = np.random.default_rng(7)
    signal = random.normal(size=900)
    shifted = np.concatenate([np.zeros(4), signal[:-4]])
    audio = signal[:, np.newaxis]
    video = shifted[np.newaxis, :]

    result = compare_clock_series(video, audio, frame_rate_hz=60.0)

    assert result["clock_alignment"] is False
    assert result["maximum_absolute_lag_frames"] == 4
    assert result["minimum_component_correlation"] > 0.99


def test_request_rejects_declared_stage_boundaries():
    request = {
        "request_version": "1.2.0",
        "demo_id": "ave-demo-005-staged-av-comparison",
        "demo_version": "1.0.0",
        "declaration_id": "ave-demo-005-staged-av-comparison@1.0.0",
        "detector_input": {
            "expected_values_present": False,
            "expected_tolerances_present": False,
            "target_schedules_present": False,
            "stage_boundaries_present": True,
            "construction_labels_present": False,
        },
        "generator_declared_values_in_detector_input": False,
        "comparison_after_observation": {
            "do_not_load_before_evidence_is_persisted": True
        },
        "requested_observation_metrics": ["clock_alignment"],
    }

    try:
        _validate_request(request)
    except DemoObservationError as error:
        assert "stage boundaries" in str(error)
    else:
        raise AssertionError("expected boundary-bearing detector input to be rejected")
