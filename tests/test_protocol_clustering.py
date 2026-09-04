import csv
import json

from clustering.protocol_families import (
    build_protocol_families,
    validate_protocol_families,
    write_protocol_families,
)


def indexed_record(path: str, digest: str, *, high_rate: bool, intent: str) -> dict:
    rate = 8.0 if high_rate else 0.75
    carrier = 220.0 if high_rate else 80.0
    difference = 7.5 if high_rate else 0.15
    return {
        "relative_path": path,
        "input_sha256": digest,
        "source": "synthetic",
        "category": "meditate" if high_rate else "focus",
        "stated_intent": intent,
        "index_status": "indexed",
        "evidence_summary": {
            "evidence_count": 20,
            "strongest_carrier_pair": {
                "left_hz": carrier,
                "right_hz": carrier + difference,
                "difference_hz": difference,
                "pair_type": "beat_candidate" if high_rate else "shared_carrier",
                "confidence": 0.9,
            },
            "dominant_envelope": {
                "modulation_hz": rate,
                "relative_power": 0.8,
                "modulation_depth": 0.7,
            },
            "modulation_reconstruction": {
                "primary_shared_modulation_hz": rate,
                "shared_window_coverage": 0.8,
                "classification": "persistent_shared_amplitude_modulation",
            },
            "phase_relationship": {
                "behavior": "phase_locked" if high_rate else "unstable_or_unrelated",
                "window_coverage": 0.9,
                "median_difference_hz": difference,
            },
            "top_hypothesis": {
                "difference_hz": rate,
                "ranking_score": 0.6,
            },
        },
    }


def synthetic_index() -> dict:
    recordings = []
    for index in range(6):
        recordings.append(
            indexed_record(
                f"low-{index}.wav",
                f"{index + 1:064x}",
                high_rate=False,
                intent="sleep" if index % 2 else "focus",
            )
        )
    for index in range(6):
        recordings.append(
            indexed_record(
                f"high-{index}.wav",
                f"{index + 101:064x}",
                high_rate=True,
                intent="focus" if index % 2 else "sleep",
            )
        )
    duplicate = dict(recordings[0])
    duplicate["relative_path"] = "renamed-low.wav"
    recordings.append(duplicate)
    recordings.append(
        {
            "relative_path": "deferred.wav",
            "input_sha256": f"{999:064x}",
            "index_status": "deferred",
            "source": "synthetic",
            "category": "focus",
            "stated_intent": "focus",
            "evidence_summary": None,
        }
    )
    return {
        "index_schema_version": "1.0.0",
        "duplicate_input_groups": [],
        "recordings": recordings,
    }


def test_discovers_deterministic_families_without_context_labels():
    index = synthetic_index()
    document = build_protocol_families(index)

    assert document["clustered_unique_input_count"] == 12
    assert len(document["families"]) == 2
    assert sorted(family["member_count"] for family in document["families"]) == [6, 6]
    assert document["method"]["overall_silhouette_score"] == 1.0
    assert document["clustering_schema_version"] == "1.1.0"
    assert document["feature_specification"]["explicitly_excluded_context"]
    assert "hypothesis_ranking_score" not in document["feature_specification"][
        "numeric_features"
    ]
    assert {item["reason"] for item in document["excluded_recordings"]} == {
        "deferred",
        "duplicate_alias",
    }

    by_path = {item["relative_path"]: item["family_id"] for item in document["assignments"]}
    low_family = {by_path[f"low-{index}.wav"] for index in range(6)}
    high_family = {by_path[f"high-{index}.wav"] for index in range(6)}
    assert len(low_family) == 1
    assert len(high_family) == 1
    assert low_family != high_family
    assert all(family["semantic_label"] for family in document["families"])
    assert all(
        family["interpretation_status"] == "exploratory_evidence_derived"
        for family in document["families"]
    )
    assert all(family["defining_signatures"] for family in document["families"])
    assert all(
        1 <= len(family["representative_recordings"]) <= 3
        for family in document["families"]
    )
    for family in document["families"]:
        representative_distances = [
            item["distance_to_centroid"]
            for item in family["representative_recordings"]
        ]
        member_distances = sorted(item["distance_to_centroid"] for item in family["members"])
        assert representative_distances == member_distances[:3]

    for record in index["recordings"]:
        if record.get("index_status") == "indexed":
            record["category"] = "reversed-label"
            record["stated_intent"] = "unrelated-claim"
    relabeled = build_protocol_families(index)
    assert {
        item["relative_path"]: item["family_id"] for item in relabeled["assignments"]
    } == by_path


def test_writes_validated_json_and_flat_assignment_csv(tmp_path):
    document = build_protocol_families(synthetic_index())
    json_path, csv_path = write_protocol_families(document, tmp_path)

    loaded = json.loads(json_path.read_text())
    validate_protocol_families(loaded)
    with csv_path.open(newline="") as input_file:
        rows = list(csv.DictReader(input_file))
    assert len(rows) == 12
    assert rows[0]["family_id"].startswith("ave_family_")
    assert rows[0]["family_label"]
    assert rows[0]["family_descriptor"]


def test_validator_rejects_unknown_family_assignment():
    document = build_protocol_families(synthetic_index())
    document["assignments"][0]["family_id"] = "ave_family_99"

    try:
        validate_protocol_families(document)
    except ValueError as error:
        assert "unknown family" in str(error)
    else:
        raise AssertionError("tampered family assignment was accepted")
