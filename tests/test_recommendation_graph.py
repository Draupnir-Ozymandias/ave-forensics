import json

from recommendations.graph import (
    aggregate_recommendation_captures,
    extract_recommendation_capture,
    validate_recommendation_capture,
    validate_recommendation_graph,
    write_recommendation_capture,
    write_recommendation_graph,
)


def track(track_id: str, title: str, similar: list[dict] | None = None) -> dict:
    value = {
        "id": track_id,
        "name": title,
        "mentalState": {"displayValue": "Focus"},
        "mobileActivity": {"displayValue": "Deep Work"},
        "beatsPerMinute": 120,
        "brightnessLevel": 0.75,
        "complexityLevel": 0.5,
        "releaseStatus": "published",
        "tags": [{"type": "mood", "value": "Calm"}],
        "variations": [
            {
                "style": "unguided",
                "neuralEffectLevel": 0.8,
                "lengthInSeconds": 900,
                "url": "https://forbidden.example/variation?token=secret",
            }
        ],
        "url": "https://forbidden.example/audio?token=secret",
    }
    if similar is not None:
        value["similarTracks"] = similar
    return value


def test_extracts_ranked_edges_variants_and_omits_sensitive_fields(tmp_path):
    beta = track("beta", "Beta")
    gamma = track("gamma", "Gamma")
    first = {"result": track("alpha", "Alpha", [beta, gamma])}
    second = {"result": track("alpha", "Alpha", [gamma, beta])}
    capture_path = tmp_path / "capture.json"
    capture_path.write_text(json.dumps(first) + "\n" + json.dumps(second))

    document = extract_recommendation_capture(
        capture_path,
        visible_category="focus",
        visible_intent="deep_work",
        context_method="user_recorded",
    )

    validate_recommendation_capture(document)
    assert document["summary"]["unique_edge_count"] == 2
    assert document["summary"]["seed_with_multiple_list_variants_count"] == 1
    assert len(document["list_observations"]) == 2
    assert all(edge["observed_ranks"] == [1, 2] for edge in document["edges"])
    alpha = next(node for node in document["nodes"] if node["track_id"] == "alpha")
    assert alpha["beats_per_minute_values"] == [120]
    assert alpha["brightness_levels"] == [0.75]
    assert alpha["neural_effect_levels"] == [0.8]
    assert alpha["styles"] == ["unguided"]
    serialized = json.dumps(document)
    assert "forbidden.example" not in serialized
    assert "secret" not in serialized


def test_preserves_empty_recommendation_observation(tmp_path):
    capture_path = tmp_path / "empty.json"
    capture_path.write_text(json.dumps({"result": track("alpha", "Alpha", [])}))
    document = extract_recommendation_capture(capture_path)

    assert document["summary"]["observed_seed_count"] == 1
    assert document["summary"]["seed_with_only_empty_lists_count"] == 1
    assert document["edges"] == []
    assert document["list_observations"][0]["recommendation_count"] == 0


def test_aggregates_capture_observations_and_writes_valid_json(tmp_path):
    first_path = tmp_path / "first.json"
    second_path = tmp_path / "second.json"
    first_path.write_text(
        json.dumps({"result": track("alpha", "Alpha", [track("beta", "Beta")])})
    )
    second_path.write_text(
        json.dumps({"result": track("alpha", "Alpha", [track("gamma", "Gamma")])})
    )
    first = extract_recommendation_capture(first_path, visible_category="focus")
    second = extract_recommendation_capture(second_path, visible_category="sleep")
    graph = aggregate_recommendation_captures([first, second])

    validate_recommendation_graph(graph)
    assert graph["summary"] == {
        "observation_count": 2,
        "node_count": 3,
        "seed_count": 1,
        "edge_count": 2,
        "seed_with_multiple_list_variants_count": 1,
    }
    assert graph["seed_list_variants"][0]["variant_count"] == 2
    capture_output = write_recommendation_capture(first, tmp_path / "sidecars")
    graph_output = write_recommendation_graph(graph, tmp_path / "graph.json")
    assert json.loads(capture_output.read_text())["observation_id"] == first["observation_id"]
    assert json.loads(graph_output.read_text())["summary"]["edge_count"] == 2
