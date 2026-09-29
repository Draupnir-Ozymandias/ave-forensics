import hashlib
import json

from verification.demo_agreement import compare_demo
from verification.demo_observation import DemoObservationError, _validate_request


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def claim(claim_id, metric, target, tolerance, *, required=True):
    return {
        "claim_id": claim_id,
        "required": required,
        "evidence_type": "test_evidence",
        "metric": metric,
        "unit": "Hz" if target["kind"] != "category" else "category",
        "scope": {
            "modality": "audio",
            "channels": ["left"],
            "regions": [],
            "time_range_seconds": {"start": 0.0, "end": 2.0},
        },
        "target": target,
        "tolerance": tolerance,
    }


def observation_metric(metric, observed):
    return {
        "evidence_type": "test_evidence",
        "metric": metric,
        "unit": "Hz" if observed["kind"] != "category" else "category",
        "scope": {
            "modality": "audio",
            "channels": ["left"],
            "regions": [],
            "time_range_seconds": {"start": 0.0, "end": 2.0},
        },
        "observed": observed,
        "coverage_fraction": 1.0,
        "confidence": 1.0,
        "evidence_ids": ["ave_0123456789abcdef"],
        "limitations": [],
    }


def test_preserves_all_five_field_states(tmp_path):
    declaration_path = tmp_path / "declaration.json"
    observation_path = tmp_path / "observation.json"
    schema_path = tmp_path / "schema.json"
    declaration = {
        "schema_version": "0.1.0",
        "demo_id": "ave-demo-999-test",
        "demo_version": "1.0.0",
        "declaration_id": "ave-demo-999-test@1.0.0",
        "claims": [
            claim("agree", "measured", {"kind": "scalar", "value": 10.0}, {"comparison": "absolute", "max_absolute_error": 0.1}),
            claim("disagree", "measured", {"kind": "scalar", "value": 20.0}, {"comparison": "absolute", "max_absolute_error": 0.1}),
            claim("unsupported", "missing", {"kind": "scalar", "value": 1.0}, {"comparison": "absolute", "max_absolute_error": 0.1}),
            claim("not-evaluated", "deferred", {"kind": "scalar", "value": 1.0}, {"comparison": "absolute", "max_absolute_error": 0.1}),
            claim("invalid", "measured", {"kind": "category", "value": "x"}, {"comparison": "absolute", "max_absolute_error": 0.1}),
        ],
    }
    write_json(declaration_path, declaration)
    declaration_hash = hashlib.sha256(declaration_path.read_bytes()).hexdigest()
    observation = {
        "demo_id": declaration["demo_id"],
        "demo_version": declaration["demo_version"],
        "declaration_id": declaration["declaration_id"],
        "expected_declaration_sha256": declaration_hash,
        "artifact": {"sha256": "a" * 64},
        "ordering_attestation": {
            "declaration_loaded_during_detection": False,
            "targets_loaded_during_detection": False,
            "tolerances_loaded_during_detection": False,
        },
        "metrics": [
            observation_metric("measured", {"kind": "scalar", "value": 10.0})
        ],
        "not_evaluated": [{"metric": "deferred", "reason": "deliberately deferred"}],
        "run_provenance": {
            "toolkit": {"version": "test", "source_tree_sha256": "b" * 64},
            "git": {"commit": None, "branch": None, "dirty": True},
            "run_id": "ave_run_0123456789abcdef",
            "analysis_configuration": {},
        },
    }
    write_json(observation_path, observation)
    write_json(schema_path, {"type": "object"})

    report = compare_demo(declaration_path, observation_path, schema_path)
    states = {item["claim_id"]: item["state"] for item in report["claim_results"]}

    assert states == {
        "agree": "agree",
        "disagree": "disagree",
        "unsupported": "unsupported",
        "not-evaluated": "not_evaluated",
        "invalid": "invalid_declaration",
    }
    assert report["evidence_label"] == "exploratory"


def test_curve_comparison_uses_observed_points_and_support_thresholds(tmp_path):
    declaration_path = tmp_path / "declaration.json"
    observation_path = tmp_path / "observation.json"
    schema_path = tmp_path / "schema.json"
    curve_claim = claim(
        "curve",
        "curve",
        {
            "kind": "linear_curve",
            "start": {"time_seconds": 0.0, "value": 4.0},
            "end": {"time_seconds": 2.0, "value": 8.0},
        },
        {
            "comparison": "curve_fit",
            "max_point_error": 0.2,
            "max_rmse": 0.2,
            "max_time_error_seconds": 0.01,
            "minimum_coverage_fraction": 0.9,
            "minimum_confidence": 0.8,
        },
    )
    declaration = {
        "schema_version": "0.1.0",
        "demo_id": "ave-demo-999-test",
        "demo_version": "1.0.0",
        "declaration_id": "ave-demo-999-test@1.0.0",
        "claims": [curve_claim],
    }
    write_json(declaration_path, declaration)
    metric = observation_metric(
        "curve",
        {
            "kind": "linear_curve",
            "start": {"time_seconds": 0.0, "value": 4.02},
            "end": {"time_seconds": 2.0, "value": 7.98},
            "point_observations": [
                {"time_seconds": 0.5, "value": 5.01},
                {"time_seconds": 1.5, "value": 7.02},
            ],
        },
    )
    observation = {
        "demo_id": declaration["demo_id"],
        "demo_version": declaration["demo_version"],
        "declaration_id": declaration["declaration_id"],
        "expected_declaration_sha256": hashlib.sha256(declaration_path.read_bytes()).hexdigest(),
        "artifact": {"sha256": "a" * 64},
        "ordering_attestation": {},
        "metrics": [metric],
        "not_evaluated": [],
        "run_provenance": {
            "toolkit": {"version": "test", "source_tree_sha256": "b" * 64},
            "git": {},
            "run_id": "ave_run_0123456789abcdef",
            "analysis_configuration": {},
        },
    }
    write_json(observation_path, observation)
    write_json(schema_path, {"type": "object"})

    report = compare_demo(declaration_path, observation_path, schema_path)

    assert report["claim_results"][0]["state"] == "agree"
    assert report["evidence_label"] == "verified"


def test_blind_request_rejects_expected_values():
    request = {
        "request_version": "1.1.0",
        "demo_id": "ave-demo-999-test",
        "demo_version": "1.0.0",
        "declaration_id": "ave-demo-999-test@1.0.0",
        "detector_input": {
            "expected_values_present": True,
            "expected_tolerances_present": False,
        },
        "comparison_after_observation": {
            "do_not_load_before_evidence_is_persisted": True
        },
        "requested_observation_metrics": [],
    }

    try:
        _validate_request(request)
    except DemoObservationError as error:
        assert "expected values" in str(error)
    else:
        raise AssertionError("expected target-bearing detector input to be rejected")
