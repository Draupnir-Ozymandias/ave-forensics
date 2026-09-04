import csv
import json

from alignment.intent_alignment import (
    build_intent_alignment,
    validate_intent_alignment,
    write_intent_alignment,
)
from clustering.protocol_families import build_protocol_families
from tests.test_protocol_clustering import synthetic_index


def aligned_index() -> dict:
    index = synthetic_index()
    for record in index["recordings"]:
        if record.get("index_status") != "indexed":
            continue
        record["stated_intent"] = (
            "activation" if record["relative_path"].startswith("high-") else "rest"
        )
    return index


def test_scores_association_without_claiming_efficacy():
    index = aligned_index()
    clustering = build_protocol_families(index)
    document = build_intent_alignment(index, clustering)

    assert document["eligible_recording_count"] == 12
    assert document["scored_recording_count"] == 12
    assert document["global_association"]["cramers_v"] == 1.0
    assert document["global_association"]["normalized_mutual_information"] == 1.0
    assert "therapeutic efficacy" in document["interpretation"]["does_not_measure"]
    assert all(
        profile["family_consistency"] == 1.0
        for profile in document["intent_profiles"]
    )
    assert all(
        assessment["normalized_alignment_score"] == 1.0
        for assessment in document["recording_assessments"]
    )


def test_small_cohort_is_not_scored():
    index = aligned_index()
    indexed = [
        record for record in index["recordings"] if record.get("index_status") == "indexed"
    ]
    unique_record = next(
        record for record in indexed if record["relative_path"] == "low-1.wav"
    )
    unique_record["stated_intent"] = "singleton"
    clustering = build_protocol_families(index)
    document = build_intent_alignment(index, clustering, minimum_cohort_size=3)

    singleton = next(
        profile for profile in document["intent_profiles"]
        if profile["stated_intent"] == "singleton"
    )
    assessment = next(
        item for item in document["recording_assessments"]
        if item["stated_intent"] == "singleton"
    )
    assert singleton["assessment_status"] == "insufficient_cohort"
    assert singleton["family_consistency"] is None
    assert assessment["normalized_alignment_score"] is None


def test_rejects_stale_clustering_and_writes_outputs(tmp_path):
    index = aligned_index()
    clustering = build_protocol_families(index)
    document = build_intent_alignment(index, clustering)
    json_path, csv_path = write_intent_alignment(document, tmp_path)

    validate_intent_alignment(json.loads(json_path.read_text()))
    with csv_path.open(newline="") as input_file:
        assert len(list(csv.DictReader(input_file))) == 12

    index["recordings"][0]["stated_intent"] = "changed"
    try:
        build_intent_alignment(index, clustering)
    except ValueError as error:
        assert "does not match" in str(error)
    else:
        raise AssertionError("stale clustering was accepted")


def test_conflicting_intents_on_duplicate_audio_are_excluded():
    index = aligned_index()
    duplicate = next(
        record for record in index["recordings"]
        if record["relative_path"] == "renamed-low.wav"
    )
    duplicate["stated_intent"] = "conflicting-claim"
    clustering = build_protocol_families(index)
    document = build_intent_alignment(index, clustering)

    assert document["eligible_recording_count"] == 11
    conflict = next(
        item for item in document["excluded_recordings"]
        if item["reason"] == "conflicting_duplicate_intents"
    )
    assert conflict["stated_intents"] == ["conflicting-claim", "rest"]
    assert conflict["aliases"] == ["low-0.wav", "renamed-low.wav"]
