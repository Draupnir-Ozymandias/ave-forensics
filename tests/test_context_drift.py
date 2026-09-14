import csv
import json

from alignment.context_drift import (
    build_context_drift,
    validate_context_drift,
    write_context_drift,
)
from clustering.protocol_families import build_protocol_families
from dashboard.comparison import build_dashboard_data
from recommendations.graph import aggregate_recommendation_captures, extract_recommendation_capture
from tests.test_protocol_clustering import synthetic_index
from tests.test_recommendation_graph import track


def _inputs(tmp_path):
    index = synthetic_index()
    for record in index["recordings"]:
        if record.get("index_status") != "indexed":
            continue
        record["stated_intent"] = (
            "deep_work" if record["relative_path"].startswith("high-") else "rest"
        )
    local = next(item for item in index["recordings"] if item["relative_path"] == "high-0.wav")
    local["relative_path"] = "brainfm/focus/deep_work/Alpha_Focus_DeepWork.mp3"
    local["provider_metadata_status"] = "validated"
    local["provider_metadata"] = {
        "provider_track": {"track_id": "alpha", "title": "Alpha"},
        "taxonomy": {
            "activity": "Light Work",
            "mobile_activity": "Light Work",
            "web_activity": "Deep Work",
            "all_provider_tags": {"activity": ["Deep Work", "Light Work"]},
        },
    }
    capture_path = tmp_path / "recommendations.json"
    capture_path.write_text(
        json.dumps({"result": track("alpha", "Alpha", [track("beta", "Beta")])})
    )
    capture = extract_recommendation_capture(
        capture_path,
        visible_category="focus",
        visible_intent="deep_work",
        seed_track_id="alpha",
        context_method="user_recorded",
    )
    return index, build_protocol_families(index), aggregate_recommendation_captures([capture])


def test_preserves_layers_and_reports_mixed_context(tmp_path):
    index, clustering, graph = _inputs(tmp_path)
    document = build_context_drift(index, clustering, graph)
    assessment = next(
        item for item in document["recording_assessments"]
        if item["provider_track_id"] == "alpha"
    )

    assert assessment["context_layers"]["directory_claimed_intent"] == ["deep_work"]
    assert assessment["context_layers"]["filename_activity"] == ["deep_work"]
    assert assessment["context_layers"]["provider_mobile_activity"] == ["light_work"]
    assert assessment["context_layers"]["provider_web_activity"] == ["deep_work"]
    assert assessment["context_layers"]["provider_activity_tags"] == [
        "deep_work",
        "light_work",
    ]
    assert assessment["context_layers"]["visible_session_intent"] == ["deep_work"]
    assert assessment["context_status"] == "mixed"
    assert assessment["protocol_family_id"]
    assert assessment["recommendation_context"]["unique_target_count"] == 1
    assert "therapeutic efficacy" in document["interpretation"]["does_not_measure"]


def test_excludes_duplicate_inputs_with_conflicting_directory_claims(tmp_path):
    index, clustering, graph = _inputs(tmp_path)
    duplicate = next(item for item in index["recordings"] if item["relative_path"] == "renamed-low.wav")
    duplicate["stated_intent"] = "another_claim"
    clustering = build_protocol_families(index)
    document = build_context_drift(index, clustering, graph)

    assert document["summary"]["excluded_duplicate_input_count"] == 1
    assert document["excluded_recordings"][0]["reason"] == "conflicting_duplicate_intents"


def test_rejects_stale_clustering_and_writes_json_and_csv(tmp_path):
    index, clustering, graph = _inputs(tmp_path)
    document = build_context_drift(index, clustering, graph)
    json_path, csv_path = write_context_drift(document, tmp_path / "output")

    validate_context_drift(json.loads(json_path.read_text()))
    with csv_path.open(newline="") as input_file:
        assert len(list(csv.DictReader(input_file))) == document["summary"]["assessed_recording_count"]

    index["recordings"][0]["stated_intent"] = "changed"
    try:
        build_context_drift(index, clustering, graph)
    except ValueError as error:
        assert "does not match" in str(error)
    else:
        raise AssertionError("stale clustering was accepted")


def test_dashboard_accepts_context_artifact_bound_to_current_inputs(tmp_path):
    index, clustering, graph = _inputs(tmp_path)
    document = build_context_drift(index, clustering, graph)
    data = build_dashboard_data(
        index,
        clustering=clustering,
        recommendation_graph=graph,
        context_drift=document,
    )

    assert data["context_drift_status"] == "validated"
    assert data["overview"]["context_compared_count"] == document["summary"][
        "assessed_recording_count"
    ]
    local = next(
        item for item in data["comparison_recordings"]
        if item["provider_track_id"] == "alpha"
    )
    assert local["context_drift_status"] == "mixed"
