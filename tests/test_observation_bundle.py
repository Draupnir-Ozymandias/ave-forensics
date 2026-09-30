import json
import hashlib
from pathlib import Path

from verification.observation_bundle import bundle_observations


def persisted_observation(artifact, metric, *, not_evaluated=None, run_id):
    return {
        "observation_schema_version": "0.1.0",
        "demo_id": "ave-demo-005-staged-av-comparison",
        "demo_version": "1.0.0",
        "declaration_id": "ave-demo-005-staged-av-comparison@1.0.0",
        "verification_request_sha256": "a" * 64,
        "expected_declaration_sha256": "b" * 64,
        "artifact": {
            "path": str(artifact),
            "sha256": hashlib.sha256(artifact.read_bytes()).hexdigest(),
        },
        "ordering_attestation": {
            "declaration_loaded_during_detection": False,
            "targets_loaded_during_detection": False,
            "tolerances_loaded_during_detection": False,
        },
        "run_provenance": {
            "run_id": run_id,
            "analysis_configuration": {"test": True},
        },
        "metrics": [metric],
        "not_evaluated": not_evaluated or [],
        "evidence_ids": ["ave_0123456789abcdef"],
        "limitations": ["test limitation"],
    }


def test_bundle_preserves_artifacts_and_resolves_not_evaluated(tmp_path):
    project_root = Path(__file__).resolve().parents[1]
    audio = tmp_path / "audio.wav"
    video = tmp_path / "clock.mp4"
    audio.write_bytes(b"audio")
    video.write_bytes(b"video")
    scope = {
        "modality": "audio",
        "channels": ["left", "right"],
        "regions": [],
        "time_range_seconds": {"start": 0.0, "end": 15.0},
    }
    stage_metric = {
        "evidence_type": "stage_timeline",
        "metric": "stage_count",
        "unit": "count",
        "scope": scope,
        "observed": {"kind": "scalar", "value": 3},
        "coverage_fraction": 1.0,
        "confidence": 1.0,
        "evidence_ids": ["ave_0123456789abcdef"],
        "limitations": [],
    }
    clock_metric = {
        **stage_metric,
        "evidence_type": "multimodal_timeline",
        "metric": "clock_alignment",
        "unit": "boolean",
        "scope": {**scope, "modality": "multimodal"},
        "observed": {"kind": "boolean", "value": True},
        "evidence_ids": ["ave_fedcba9876543210"],
    }
    first_path = tmp_path / "first.json"
    second_path = tmp_path / "second.json"
    first_path.write_text(
        json.dumps(
            persisted_observation(
                audio,
                stage_metric,
                not_evaluated=[{"metric": "clock_alignment", "reason": "audio only"}],
                run_id="ave_run_0123456789abcdef",
            )
        )
    )
    second = persisted_observation(
        video,
        clock_metric,
        run_id="ave_run_fedcba9876543210",
    )
    second["evidence_ids"] = ["ave_fedcba9876543210"]
    second_path.write_text(json.dumps(second))

    bundle = bundle_observations(
        [first_path, second_path], project_root=project_root
    )

    assert len(bundle["metrics"]) == 2
    assert bundle["not_evaluated"] == []
    assert bundle["artifact"]["path"] == str(audio)
    assert bundle["supporting_artifacts"] == [second["artifact"]]
    assert len(bundle["component_observations"]) == 2
    assert bundle["component_observations"][0]["verification_request_sha256"] == "a" * 64
    assert bundle["ordering_attestation"] == {
        "declaration_loaded_during_detection": False,
        "targets_loaded_during_detection": False,
        "tolerances_loaded_during_detection": False,
    }
