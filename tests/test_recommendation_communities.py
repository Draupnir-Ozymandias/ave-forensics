import copy
import json

from recommendations.communities import (
    analyze_recommendation_drift,
    build_recommendation_communities,
    validate_recommendation_communities,
    validate_recommendation_drift,
    write_recommendation_communities,
    write_recommendation_drift,
)
from recommendations.graph import (
    aggregate_recommendation_captures,
    extract_recommendation_capture,
)
from tests.test_recommendation_graph import track


def capture(tmp_path, name: str, payload: dict):
    path = tmp_path / name
    path.write_text(json.dumps(payload))
    return extract_recommendation_capture(path)


def test_discovers_topology_only_communities_and_isolates(tmp_path):
    document = capture(
        tmp_path,
        "graph.json",
        {
            "result": [
                track("a", "A", [track("b", "B"), track("c", "C")]),
                track("b", "B", [track("a", "A"), track("c", "C")]),
                track("x", "X", [track("y", "Y")]),
                track("isolated", "Isolated", []),
            ]
        },
    )
    graph = aggregate_recommendation_captures([document])
    communities = build_recommendation_communities(graph)

    validate_recommendation_communities(communities)
    assignments = {
        item["track_id"]: item["community_id"] for item in communities["assignments"]
    }
    assert assignments["a"] == assignments["b"] == assignments["c"]
    assert assignments["x"] == assignments["y"]
    assert assignments["a"] != assignments["x"]
    assert [item["track_id"] for item in communities["isolated_nodes"]] == [
        "isolated"
    ]
    assert communities["method"]["context_fields_used"] == []
    assert communities["posthoc_context_association"]["provider_mental_state"][
        "sample_count"
    ] == 5
    assert build_recommendation_communities(graph) == communities

    relabeled_graph = copy.deepcopy(graph)
    for node in relabeled_graph["nodes"]:
        node["mental_states"] = ["Reassigned Context"]
        node["activities"] = ["Unrelated Label"]
    relabeled = build_recommendation_communities(relabeled_graph)
    assert {
        item["track_id"]: item["community_id"] for item in relabeled["assignments"]
    } == assignments


def test_measures_repeated_nonempty_seed_drift(tmp_path):
    first = capture(
        tmp_path,
        "first.json",
        {"result": track("a", "A", [track("b", "B"), track("c", "C")])},
    )
    second = capture(
        tmp_path,
        "second.json",
        {"result": track("a", "A", [track("c", "C"), track("d", "D")])},
    )
    empty = capture(
        tmp_path,
        "empty.json",
        {"result": track("z", "Z", [])},
    )
    drift = analyze_recommendation_drift([first, second, empty])

    validate_recommendation_drift(drift)
    assessment = next(
        item for item in drift["seed_assessments"] if item["seed_track_id"] == "a"
    )
    assert assessment["assessment_status"] == "assessed"
    assert assessment["mean_jaccard_similarity"] == 0.333333
    assert assessment["pairwise_comparisons"][0]["retained_count"] == 1
    assert drift["summary"]["assessed_seed_count"] == 1


def test_empty_and_nonempty_forms_are_not_mislabeled_as_temporal_drift(tmp_path):
    payload = {
        "result": [
            track("a", "A", []),
            track("a", "A", [track("b", "B")]),
        ]
    }
    observation = capture(tmp_path, "variants.json", payload)
    drift = analyze_recommendation_drift([observation])

    assessment = next(
        item for item in drift["seed_assessments"] if item["seed_track_id"] == "a"
    )
    assert assessment["assessment_status"] == "not_repeated"
    assert assessment["mean_jaccard_similarity"] is None
    assert drift["summary"]["within_capture_variant_seed_count"] == 1


def test_writes_community_and_drift_outputs(tmp_path):
    observation = capture(
        tmp_path,
        "capture.json",
        {"result": track("a", "A", [track("b", "B")])},
    )
    graph = aggregate_recommendation_captures([observation])
    communities = build_recommendation_communities(graph)
    drift = analyze_recommendation_drift([observation])

    community_path, csv_path = write_recommendation_communities(
        communities, tmp_path / "output"
    )
    drift_path = write_recommendation_drift(drift, tmp_path / "output")
    assert json.loads(community_path.read_text())["summary"]["community_count"] == 1
    assert csv_path.read_text().startswith("track_id,title,community_id")
    assert json.loads(drift_path.read_text())["summary"]["observation_count"] == 1
