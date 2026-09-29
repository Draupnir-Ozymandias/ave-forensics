import json

import numpy as np

from analysis.video_regions import analyze_region_frames
from verification.demo_observation import (
    DemoObservationError,
    _observe_video,
    _validate_request,
)


def test_detects_four_independent_pixel_timing_regions():
    frame_count = 120
    frames = np.zeros((frame_count, 32, 32, 3), dtype=np.uint8)
    schedules = {
        "top_left": (slice(0, 16), slice(0, 16), 6),
        "top_right": (slice(0, 16), slice(16, 32), 8),
        "bottom_left": (slice(16, 32), slice(0, 16), 10),
        "bottom_right": (slice(16, 32), slice(16, 32), 12),
    }
    colors = {
        "top_left": (255, 0, 0),
        "top_right": (0, 255, 0),
        "bottom_left": (0, 0, 255),
        "bottom_right": (255, 255, 255),
    }
    for name, (rows, columns, period) in schedules.items():
        active = (np.arange(frame_count) // period) % 2 == 1
        frames[active, rows, columns] = colors[name]

    result = analyze_region_frames(frames, refresh_rate_hz=60.0)

    assert result["classification"] == "independent_region_schedules"
    assert result["region_count"] == 4
    assert result["independent_region_schedules"] is True
    assert result["frame_count"] == 120
    assert result["duration_seconds"] == 2.0
    assert {item["region_id"] for item in result["regions"]} == set(schedules)
    assert all(item["explicit_off_intervals"] for item in result["regions"])


def test_blind_request_rejects_target_schedules():
    request = {
        "request_version": "1.1.0",
        "demo_id": "ave-demo-999-test",
        "demo_version": "1.0.0",
        "declaration_id": "ave-demo-999-test@1.0.0",
        "detector_input": {
            "expected_values_present": False,
            "expected_tolerances_present": False,
            "target_schedules_present": True,
        },
        "generator_declared_values_in_detector_input": False,
        "comparison_after_observation": {
            "do_not_load_before_evidence_is_persisted": True
        },
        "requested_observation_metrics": [],
    }

    try:
        _validate_request(request)
    except DemoObservationError as error:
        assert "target schedules" in str(error)
    else:
        raise AssertionError("expected target-bearing detector input to be rejected")


def test_video_observation_emits_contract_normalized_metrics(tmp_path, monkeypatch):
    input_path = tmp_path / "preview.mp4"
    input_path.write_bytes(b"synthetic-video")
    request_path = tmp_path / "verification-request.json"
    request = {
        "demo_id": "ave-demo-004-four-region-light",
        "demo_version": "1.0.0",
        "declaration_id": "ave-demo-004-four-region-light@1.0.0",
        "comparison_after_observation": {"declaration_sha256": "a" * 64},
    }
    request_path.write_text(json.dumps(request))
    regions = []
    for region_id in ("top_left", "top_right", "bottom_left", "bottom_right"):
        regions.append(
            {
                "region_id": region_id,
                "explicit_off_intervals": [{"start": 0.0, "end": 0.5}],
            }
        )
    result = {
        "classification": "independent_region_schedules",
        "region_count": 4,
        "independent_region_schedules": True,
        "regions": regions,
        "frame_count": 240,
        "refresh_rate_hz": 60.0,
        "duration_seconds": 4.0,
        "analysis_resolution": {"width": 64, "height": 64},
        "on_threshold": 0.02,
        "minimum_region_pixels": 82,
        "spatial_coverage_fraction": 1.0,
        "confidence": 1.0,
        "limitations": ["synthetic test"],
        "stream": {"width": 480, "height": 480},
    }
    monkeypatch.setattr(
        "verification.demo_observation.analyze_video_regions",
        lambda path, analysis_size: result,
    )

    observation, evidence = _observe_video(
        request=request,
        request_path=request_path,
        input_path=input_path,
        actual_hash="b" * 64,
        requested_metrics={
            "duration_seconds",
            "frame_count",
            "refresh_rate_hz",
            "region_count",
            "independent_region_schedules",
            "explicit_off_intervals",
            "source_recipe_sha256",
        },
        provenance={"run_id": "ave_run_0123456789abcdef"},
        evidence_provenance={"run_id": "ave_run_0123456789abcdef"},
        detector_configuration={"video_regions": {"analysis_size": 64}},
    )

    normalized = {
        (item["evidence_type"], item["metric"], item["unit"]): item
        for item in observation["metrics"]
    }
    assert ("resolved_light_plan", "region_count", "count") in normalized
    assert ("resolved_light_plan", "explicit_off_intervals", "boolean") in normalized
    assert ("media_identity", "frame_count", "frames") in normalized
    assert normalized[("resolved_light_plan", "region_count", "count")]["scope"][
        "modality"
    ] == "light"
    assert observation["not_evaluated"] == [
        {
            "metric": "source_recipe_sha256",
            "reason": "Generator recipe identity is not observable from rendered video pixels.",
        }
    ]
    assert len(evidence) == 2
