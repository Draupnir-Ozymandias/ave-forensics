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
        "scored_intent_alignment_count": 0,
        "eligible_intent_alignment_count": 0,
        "excluded_intent_alignment_count": 0,
        "provider_metadata_count": 0,
        "transcript_sidecar_count": 0,
        "speech_context_comparison_count": 0,
        "analysis_configuration_versions": {},
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
    assert 'id="provider-activity"' in first_text
    assert 'id="hypothesis-mode"' in first_text
    assert "All retained" in first_text
    assert "Provider taxonomy" in first_text
    assert 'id="transcript-status"' in first_text
    assert "Speech context" in first_text
    assert 'id="speech-difference-chart"' in first_text
    assert 'id="speech-band-chart"' in first_text
    assert 'id="alignment-profiles"' in first_text
    assert 'id="recommendation-top"' in first_text
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
    assert all(
        record["protocol_family_label"]
        for record in data["comparison_recordings"]
        if record["index_status"] == "indexed"
    )
    assert all(family["defining_signatures"] for family in data["protocol_families"])


def test_dashboard_accepts_alignment_bound_to_current_inputs():
    from alignment.intent_alignment import build_intent_alignment
    from clustering.protocol_families import build_protocol_families
    from tests.test_intent_alignment import aligned_index

    index = aligned_index()
    clustering = build_protocol_families(index)
    alignment = build_intent_alignment(index, clustering)
    data = build_dashboard_data(index, clustering, alignment)

    assert data["alignment_status"] == "validated"
    assert data["overview"]["scored_intent_alignment_count"] == 12
    assert data["overview"]["eligible_intent_alignment_count"] == 12
    assert data["overview"]["excluded_intent_alignment_count"] == 0
    assert data["global_intent_association"]["cramers_v"] == 1.0
    assert all(
        record["intent_alignment_score"] == 1.0
        for record in data["comparison_recordings"]
        if record["index_status"] == "indexed"
    )


def test_dashboard_links_sanitized_recommendations_to_provider_tracks(tmp_path):
    from recommendations.graph import (
        aggregate_recommendation_captures,
        extract_recommendation_capture,
    )
    from tests.test_recommendation_graph import track

    item = record("local.wav", "local-hash")
    item["provider_metadata_status"] = "validated"
    item["provider_metadata"] = {
        "provider_track": {"track_id": "alpha", "title": "Alpha"}
    }
    index = {
        "index_schema_version": "1.0.0",
        "duplicate_input_groups": [],
        "recordings": [item],
    }
    capture_path = tmp_path / "recommendations.json"
    capture_path.write_text(
        json.dumps({"result": track("alpha", "Alpha", [track("beta", "Beta")])})
    )
    capture = extract_recommendation_capture(capture_path)
    graph = aggregate_recommendation_captures([capture])
    data = build_dashboard_data(index, recommendation_graph=graph)

    assert data["recommendation_status"] == "validated"
    assert data["recommendation_summary"]["edge_count"] == 1
    assert data["recommendation_summary"]["local_provider_track_matched_count"] == 1
    local = data["comparison_recordings"][0]
    assert local["recommendation_out_degree"] == 1
    assert local["recommendation_in_degree"] == 0


def test_dashboard_exposes_provider_taxonomy_as_context():
    item = record("guided.wav", "provider-hash")
    item.update(
        {
            "provider_metadata_status": "validated",
            "provider_metadata_path": "samples/guided.wav.provider.json",
            "provider_metadata": {
                "provider_track": {"title": "Quiet Mind"},
                "taxonomy": {
                    "mental_state": "Meditate",
                    "activity": "Guided",
                    "style": "guided",
                    "genres": ["Atmospheric"],
                    "subgenres": [],
                    "moods": ["Calm"],
                    "instruments": ["Voice"],
                },
                "provider_measurements": {
                    "beats_per_minute": 120,
                    "brightness_level": 0.25,
                    "complexity_level": 0.5,
                    "neural_effect_level": 0.8,
                },
            },
        }
    )

    data = build_dashboard_data(
        {
            "index_schema_version": "1.0.0",
            "duplicate_input_groups": [],
            "recordings": [item],
        }
    )

    flattened = data["recordings"][0]
    assert data["overview"]["provider_metadata_count"] == 1
    assert data["facets"]["provider_mental_states"] == ["Meditate"]
    assert data["facets"]["provider_activities"] == ["Guided"]
    assert flattened["provider_title"] == "Quiet Mind"
    assert flattened["provider_moods"] == ["Calm"]
    assert flattened["provider_neural_effect_level"] == 0.8


def test_dashboard_preserves_retained_hypothesis_band_summary():
    item = record("gamma.wav", "gamma-hash")
    item["evidence_summary"]["hypothesis_band_summary"] = {
        "candidate_count": 4,
        "counts": {"delta": 1, "gamma": 3},
        "best_by_band": {
            "delta": {
                "brainwave_band": "delta",
                "difference_hz": 2.0,
                "ranking_score": 0.7,
            },
            "gamma": {
                "brainwave_band": "gamma",
                "difference_hz": 38.0,
                "ranking_score": 0.3,
            },
        },
    }

    data = build_dashboard_data(
        {
            "index_schema_version": "1.1.0",
            "duplicate_input_groups": [],
            "recordings": [item],
        }
    )

    flattened = data["recordings"][0]
    assert flattened["retained_hypothesis_count"] == 4
    assert flattened["hypothesis_band_counts"] == {"delta": 1, "gamma": 3}
    assert flattened["hypothesis_best_by_band"]["gamma"]["ranking_score"] == 0.3


def test_dashboard_exposes_text_free_transcript_context():
    item = record("guided.wav", "transcript-hash")
    item.update(
        {
            "transcript_status": "validated",
            "transcript_path": "samples/guided.wav.transcript.json",
            "transcript_sidecar": {
                "transcription_engine": {
                    "provider": "aws",
                    "language_code": "en-US",
                },
                "statistics": {
                    "segment_count": 71,
                    "timed_pronunciation_count": 557,
                    "speech_coverage_ratio": 0.321,
                    "mean_pronunciation_confidence": 0.976,
                },
            },
        }
    )

    data = build_dashboard_data(
        {
            "index_schema_version": "1.2.0",
            "duplicate_input_groups": [],
            "recordings": [item],
        }
    )

    flattened = data["recordings"][0]
    assert data["overview"]["transcript_sidecar_count"] == 1
    assert data["facets"]["transcript_statuses"] == ["validated"]
    assert data["facets"]["transcript_languages"] == ["en-US"]
    assert flattened["transcript_segment_count"] == 71
    assert flattened["transcript_speech_coverage_ratio"] == 0.321


def test_dashboard_exposes_speech_aware_signal_comparison():
    item = record("guided.wav", "speech-context-hash")
    item["evidence_summary"]["speech_context_comparison"] = {
        "buffered_speech_coverage": 0.38,
        "active_window_count": 72,
        "sparse_window_count": 106,
        "direct_comparison_available": True,
        "active_candidate_rate": 1.0,
        "sparse_candidate_rate": 1.0,
        "active_median_difference_hz": 1.25,
        "sparse_median_difference_hz": 0.5,
        "active_median_phase_locking": 0.0815,
        "sparse_median_phase_locking": 0.0902,
        "active_persistent_difference_hz": 0.8,
        "sparse_persistent_difference_hz": 0.6,
        "active_persistent_band": "delta",
        "sparse_persistent_band": "delta",
        "active_persistent_score": 0.4,
        "sparse_persistent_score": 0.5,
        "active_band_counts": {"beta": 15, "delta": 42, "gamma": 10},
        "sparse_band_counts": {"delta": 106},
    }

    data = build_dashboard_data(
        {
            "index_schema_version": "1.3.0",
            "duplicate_input_groups": [],
            "recordings": [item],
        }
    )

    flattened = data["recordings"][0]
    assert data["overview"]["speech_context_comparison_count"] == 1
    assert flattened["speech_active_median_difference_hz"] == 1.25
    assert flattened["speech_sparse_persistent_difference_hz"] == 0.6
    assert flattened["speech_sparse_band_counts"] == {"delta": 106}


def test_dashboard_warns_when_analysis_configurations_are_mixed():
    index = {
        "index_schema_version": "1.4.0",
        "analysis_configuration_version_counts": {"1.0.0": 34, "1.2.0": 4},
        "duplicate_input_groups": [],
        "recordings": [record("guided.wav", "mixed-config")],
    }

    data = build_dashboard_data(index)

    assert any(
        warning["kind"] == "mixed_analysis_configuration"
        for warning in data["warnings"]
    )
