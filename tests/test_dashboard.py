import json

from dashboard.comparison import build_dashboard_data, write_dashboard


def record(path, digest, *, status="indexed", provenance="validated", score=0.5):
    evidence = None
    if status == "indexed":
        evidence = {
            "evidence_count": 10,
            "strongest_carrier_pair": {
                "left_hz": 100.0,
                "right_hz": 104.0,
                "difference_hz": 4.0,
                "pair_type": "split_carrier",
                "confidence": 0.9,
            },
            "dominant_envelope": {"modulation_hz": 8.0},
            "modulation_reconstruction": {
                "classification": "shared_amplitude_modulation",
                "primary_shared_modulation_hz": 8.0,
            },
            "phase_relationship": {
                "behavior": "stable_offset",
                "window_coverage": 0.8,
            },
            "top_hypothesis": {
                "intent": "alpha candidate",
                "brainwave_band": "alpha",
                "difference_hz": 8.0,
                "ranking_score": score,
            },
        }
    return {
        "relative_path": path,
        "source": "reference",
        "category": "focus",
        "stated_intent": "deep_work",
        "index_status": status,
        "provenance_status": provenance,
        "metadata_status": "validated",
        "input_sha256": digest,
        "duplicate_input_paths": [],
        "evidence_summary": evidence,
    }


def test_dashboard_deduplicates_comparisons_but_preserves_aliases():
    first = record("one.wav", "same", score=0.75)
    second = record("renamed.wav", "same", score=0.75)
    deferred = record(
        "long.wav", "different", status="deferred", provenance="not_available"
    )
    index = {
        "index_schema_version": "1.0.0",
        "duplicate_input_groups": [
            {"input_sha256": "same", "relative_paths": ["one.wav", "renamed.wav"]}
        ],
        "recordings": [second, deferred, first],
    }

    data = build_dashboard_data(index)

    assert data["overview"] == {
        "recording_alias_count": 3,
        "unique_input_count": 2,
        "unique_indexed_count": 1,
        "indexed_evidence_count": 10,
        "duplicate_group_count": 1,
        "protocol_family_count": 0,
    }
    assert len(data["recordings"]) == 3
    assert len(data["comparison_recordings"]) == 2
    canonical = next(
        item for item in data["comparison_recordings"] if item["input_sha256"] == "same"
    )
    assert canonical["all_aliases"] == ["one.wav", "renamed.wav"]
    assert canonical["hypothesis_ranking_score"] == 0.75
    assert {item["kind"] for item in data["warnings"]} == {
        "deferred",
        "duplicate_aliases",
    }


def test_dashboard_html_is_self_contained_and_deterministic(tmp_path):
    index = {
        "index_schema_version": "1.0.0",
        "duplicate_input_groups": [],
        "recordings": [record("danger-</script>.wav", "abc")],
    }
    data = build_dashboard_data(index)

    first = write_dashboard(data, tmp_path)
    first_text = first.read_text()
    second = write_dashboard(data, tmp_path)

    assert first == second
    assert first_text == second.read_text()
    assert "__AVE_DASHBOARD_DATA__" not in first_text
    assert "danger-<\\/script>.wav" in first_text
    assert "Reference-Library Comparison" in first_text
    embedded = first_text.split(
        '<script id="dashboard-data" type="application/json">', 1
    )[1].split("</script>", 1)[0]
    parsed = json.loads(embedded.replace("<\\/", "</"))
    assert parsed["overview"]["unique_input_count"] == 1


def test_dashboard_accepts_clustering_bound_to_the_same_index():
    from clustering.protocol_families import build_protocol_families
    from tests.test_protocol_clustering import synthetic_index

    index = synthetic_index()
    clustering = build_protocol_families(index)
    data = build_dashboard_data(index, clustering)

    assert data["clustering_status"] == "validated"
    assert data["overview"]["protocol_family_count"] == 2
    assert all(
        record["protocol_family_id"]
        for record in data["comparison_recordings"]
        if record["index_status"] == "indexed"
    )
