from copy import deepcopy
import json
from pathlib import Path

import pytest

from device_protocol.lumenate import LumenateContractError, import_lumenate_export, validate_lumenate_export


FIXTURES = Path(__file__).resolve().parents[1] / "device_protocol" / "fixtures"
VITALITY = FIXTURES / "vitality-5min-empirical-0.2.0.json"


def _vitality_document():
    return json.loads(VITALITY.read_text(encoding="utf-8"))


def test_imports_complete_vitality_golden_fixture():
    imported = import_lumenate_export(VITALITY)
    assert imported.schema_version == "0.2.0"
    assert imported.session_id == "vitality-5min-high-intensity"
    assert imported.duration_seconds == pytest.approx(300.0)
    assert imported.audio_identity_status == "verified"
    assert imported.timeline[0].start_seconds == 0.0
    assert imported.timeline[-1].end_seconds == pytest.approx(300.0)
    assert all(event.evidence_ids for event in imported.timeline)


@pytest.mark.parametrize("fixture_name", [
    "deep-exploration-optical-empirical-0.2.0.json",
    "spirit-optical-empirical-0.2.0.json",
    "offline-explore-optical-empirical-0.2.0.json",
])
def test_imports_partial_physical_measurement_fixtures(fixture_name):
    imported = import_lumenate_export(FIXTURES / fixture_name)
    assert imported.audio_identity_status == "unavailable"
    assert len(imported.timeline) == 1
    assert imported.timeline[0].execution_layer == "physical_measurement"


@pytest.mark.parametrize(("field", "value", "message"), [
    ("schema_version", "1.0.0", "unsupported Lumenate protocol"),
    ("ave_evidence_schema_version", "2.0.0", "unsupported AVE evidence"),
])
def test_rejects_unsupported_contract_versions(field, value, message):
    document = _vitality_document()
    document[field] = value
    with pytest.raises(LumenateContractError, match=message):
        validate_lumenate_export(document)


def test_rejects_schema_drift():
    document = _vitality_document()
    document["unexpected_consumer_guess"] = True
    with pytest.raises(LumenateContractError, match="schema validation failed"):
        validate_lumenate_export(document)


def test_rejects_unknown_evidence_reference():
    document = _vitality_document()
    document["segments"][0]["evidence_ids"] = ["ave_0000000000000000"]
    with pytest.raises(LumenateContractError, match="unknown evidence"):
        validate_lumenate_export(document)


def test_rejects_duplicate_ids():
    document = _vitality_document()
    document["segments"].insert(1, deepcopy(document["segments"][0]))
    with pytest.raises(LumenateContractError, match="duplicate segment IDs"):
        validate_lumenate_export(document)


def test_rejects_segment_outside_session():
    document = _vitality_document()
    document["segments"][-1]["end_ms"] = document["session"]["duration_ms"] + 1
    with pytest.raises(LumenateContractError, match="exceeds session duration"):
        validate_lumenate_export(document)


def test_rejects_undeclared_overlap():
    document = _vitality_document()
    document["segments"][1]["start_ms"] = document["segments"][0]["end_ms"] - 1
    with pytest.raises(LumenateContractError, match="must be declared by both"):
        validate_lumenate_export(document)


def test_rejects_verified_audio_hash_without_matching_source():
    document = _vitality_document()
    document["audio_asset"]["sha256"] = "0" * 64
    with pytest.raises(LumenateContractError, match="verified audio identity"):
        validate_lumenate_export(document)
