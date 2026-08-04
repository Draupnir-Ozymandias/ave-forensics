import json
from pathlib import Path

import pytest

from evidence.adapters import (
    carrier_pair_to_evidence,
    modulation_spectrum_to_evidence,
)
from evidence.schema import (
    EvidenceValidationError,
    create_evidence_object,
    measurement,
    validate_evidence_object,
)
from reports.evidence_export import export_evidence_json


def test_creates_valid_deterministic_json_evidence():
    arguments = {
        "evidence_level": "measurement",
        "evidence_type": "synthetic_measurement",
        "source_module": "tests.synthetic",
        "summary": "Known synthetic frequency",
        "measurements": [measurement("frequency", 3.0, "Hz")],
        "channels": ["mono"],
        "provenance": {"generator": "synthetic"},
    }
    first = create_evidence_object(**arguments)
    second = create_evidence_object(**arguments)

    assert first["evidence_id"] == second["evidence_id"]
    validate_evidence_object(first)
    json.dumps(first)


def test_rejects_invalid_confidence():
    with pytest.raises(EvidenceValidationError):
        create_evidence_object(
            evidence_level="detection",
            evidence_type="invalid",
            source_module="tests.synthetic",
            summary="Invalid confidence",
            measurements=[measurement("frequency", 3.0, "Hz")],
            confidence={"score": 1.1, "method": "test"},
        )


def test_carrier_adapter_produces_valid_association():
    pair = {
        "pair_type": "beat_candidate",
        "left_carrier_hz": 100.0,
        "right_carrier_hz": 102.0,
        "difference_hz": 2.0,
        "start_seconds": 0.0,
        "end_seconds": 60.0,
        "duration_seconds": 60.0,
        "overlap_ratio": 1.0,
        "amplitude_balance": 0.95,
        "confidence": 0.9,
    }
    evidence = carrier_pair_to_evidence(pair)

    validate_evidence_object(evidence)
    assert evidence["evidence_level"] == "association"
    assert evidence["scope"]["channels"] == ["left", "right"]


def test_modulation_adapter_produces_reconstruction():
    result = {
        "classification": "persistent_shared_amplitude_modulation",
        "left_tracks": [{}],
        "right_tracks": [{}],
        "primary_stereo_modulation": {
            "average_modulation_hz": 0.625,
            "shared_coverage": 0.966,
            "frequency_difference_hz": 0.0,
            "confidence": 0.96,
        },
    }
    evidence = modulation_spectrum_to_evidence(result)

    validate_evidence_object(evidence)
    assert evidence["evidence_level"] == "reconstruction"


def test_exports_evidence_document(tmp_path):
    evidence = create_evidence_object(
        evidence_level="measurement",
        evidence_type="synthetic_measurement",
        source_module="tests.synthetic",
        summary="Export test",
        measurements=[measurement("frequency", 3.0, "Hz")],
    )
    output_path = tmp_path / "evidence.json"
    export_evidence_json([evidence], str(output_path))
    document = json.loads(output_path.read_text())

    assert document["evidence_count"] == 1
    assert document["evidence"][0]["evidence_id"] == evidence["evidence_id"]


def test_formal_json_schema_matches_runtime_contract():
    schema_path = (
        Path(__file__).parents[1]
        / "evidence"
        / "evidence-object.schema.json"
    )
    schema = json.loads(schema_path.read_text())

    assert schema["properties"]["schema_version"]["const"] == "1.0.0"
    assert "evidence_id" in schema["required"]
    assert set(schema["properties"]["evidence_level"]["enum"]) == {
        "measurement",
        "detection",
        "association",
        "reconstruction",
        "hypothesis",
    }
