from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any


DASHBOARD_SCHEMA_VERSION = "1.7.0"
TEMPLATE_PATH = Path(__file__).with_name("dashboard.html")


def _flatten_record(record: dict[str, Any]) -> dict[str, Any]:
    summary = record.get("evidence_summary") or {}
    carrier = summary.get("strongest_carrier_pair") or {}
    envelope = summary.get("dominant_envelope") or {}
    modulation = summary.get("modulation_reconstruction") or {}
    phase = summary.get("phase_relationship") or {}
    speech_context = summary.get("speech_context_comparison") or {}
    hypothesis = summary.get("top_hypothesis") or {}
    hypothesis_bands = summary.get("hypothesis_band_summary") or {}
    provider_metadata = record.get("provider_metadata") or {}
    provider_track = provider_metadata.get("provider_track") or {}
    provider_taxonomy = provider_metadata.get("taxonomy") or {}
    provider_measurements = provider_metadata.get("provider_measurements") or {}
    transcript_sidecar = record.get("transcript_sidecar") or {}
    transcript_engine = transcript_sidecar.get("transcription_engine") or {}
    transcript_statistics = transcript_sidecar.get("statistics") or {}
    aliases = sorted(record.get("duplicate_input_paths") or [])
    return {
        "relative_path": record["relative_path"],
        "filename": Path(record["relative_path"]).name,
        "source": record.get("source") or "unknown",
        "category": record.get("category") or "unknown",
        "stated_intent": record.get("stated_intent") or "unknown",
        "notes": record.get("notes") or "",
        "index_status": record.get("index_status") or "unknown",
        "provenance_status": record.get("provenance_status") or "not_available",
        "metadata_status": record.get("metadata_status") or "missing",
        "run_id": record.get("run_id"),
        "analysis_configuration_version": record.get(
            "analysis_configuration_version"
        ),
        "input_sha256": record.get("input_sha256"),
        "input_size_bytes": record.get("input_size_bytes"),
        "duration_seconds": record.get("duration_seconds"),
        "evidence_count": summary.get("evidence_count"),
        "evidence_path": record.get("evidence_path"),
        "metadata_manifest_path": record.get("metadata_manifest_path"),
        "provider_metadata_status": record.get("provider_metadata_status") or "missing",
        "provider_metadata_path": record.get("provider_metadata_path"),
        "provider_track_id": provider_track.get("track_id"),
        "provider_title": provider_track.get("title"),
        "provider_mental_state": provider_taxonomy.get("mental_state"),
        "provider_activity": provider_taxonomy.get("activity"),
        "provider_style": provider_taxonomy.get("style"),
        "provider_genres": provider_taxonomy.get("genres") or [],
        "provider_subgenres": provider_taxonomy.get("subgenres") or [],
        "provider_moods": provider_taxonomy.get("moods") or [],
        "provider_instruments": provider_taxonomy.get("instruments") or [],
        "provider_beats_per_minute": provider_measurements.get("beats_per_minute"),
        "provider_brightness_level": provider_measurements.get("brightness_level"),
        "provider_complexity_level": provider_measurements.get("complexity_level"),
        "provider_neural_effect_level": provider_measurements.get(
            "neural_effect_level"
        ),
        "transcript_status": record.get("transcript_status") or "missing",
        "transcript_path": record.get("transcript_path"),
        "transcript_provider": transcript_engine.get("provider"),
        "transcript_language_code": transcript_engine.get("language_code"),
        "transcript_segment_count": transcript_statistics.get("segment_count"),
        "transcript_timed_pronunciation_count": transcript_statistics.get(
            "timed_pronunciation_count"
        ),
        "transcript_speech_coverage_ratio": transcript_statistics.get(
            "speech_coverage_ratio"
        ),
        "transcript_mean_pronunciation_confidence": transcript_statistics.get(
            "mean_pronunciation_confidence"
        ),
        "speech_context_comparison_available": speech_context.get(
            "direct_comparison_available", False
        ),
        "speech_context_buffered_coverage_ratio": speech_context.get(
            "buffered_speech_coverage"
        ),
        "speech_active_window_count": speech_context.get("active_window_count"),
        "speech_sparse_window_count": speech_context.get("sparse_window_count"),
        "speech_active_candidate_rate": speech_context.get("active_candidate_rate"),
        "speech_sparse_candidate_rate": speech_context.get("sparse_candidate_rate"),
        "speech_active_median_difference_hz": speech_context.get(
            "active_median_difference_hz"
        ),
        "speech_sparse_median_difference_hz": speech_context.get(
            "sparse_median_difference_hz"
        ),
        "speech_active_median_phase_locking": speech_context.get(
            "active_median_phase_locking"
        ),
        "speech_sparse_median_phase_locking": speech_context.get(
            "sparse_median_phase_locking"
        ),
        "speech_active_persistent_difference_hz": speech_context.get(
            "active_persistent_difference_hz"
        ),
        "speech_sparse_persistent_difference_hz": speech_context.get(
            "sparse_persistent_difference_hz"
        ),
        "speech_active_persistent_band": speech_context.get(
            "active_persistent_band"
        ),
        "speech_sparse_persistent_band": speech_context.get(
            "sparse_persistent_band"
        ),
        "speech_active_persistent_score": speech_context.get(
            "active_persistent_score"
        ),
        "speech_sparse_persistent_score": speech_context.get(
            "sparse_persistent_score"
        ),
        "speech_active_band_counts": speech_context.get("active_band_counts") or {},
        "speech_sparse_band_counts": speech_context.get("sparse_band_counts") or {},
        "index_error": record.get("index_error"),
        "duplicate_aliases": aliases,
        "carrier_left_hz": carrier.get("left_hz"),
        "carrier_right_hz": carrier.get("right_hz"),
        "carrier_difference_hz": carrier.get("difference_hz"),
        "carrier_pair_type": carrier.get("pair_type"),
        "carrier_confidence": carrier.get("confidence"),
        "envelope_modulation_hz": envelope.get("modulation_hz"),
        "envelope_relative_power": envelope.get("relative_power"),
        "envelope_modulation_depth": envelope.get("modulation_depth"),
        "modulation_classification": modulation.get("classification"),
        "shared_modulation_hz": modulation.get("primary_shared_modulation_hz"),
        "shared_window_coverage": modulation.get("shared_window_coverage"),
        "phase_behavior": phase.get("behavior"),
        "phase_window_coverage": phase.get("window_coverage"),
        "phase_median_difference_hz": phase.get("median_difference_hz"),
        "hypothesis_intent": hypothesis.get("intent"),
        "hypothesis_band": hypothesis.get("brainwave_band"),
        "hypothesis_difference_hz": hypothesis.get("difference_hz"),
        "hypothesis_ranking_score": hypothesis.get("ranking_score"),
        "hypothesis_confidence": hypothesis.get("confidence"),
        "retained_hypothesis_count": hypothesis_bands.get("candidate_count", 0),
        "hypothesis_band_counts": hypothesis_bands.get("counts") or {},
        "hypothesis_best_by_band": hypothesis_bands.get("best_by_band") or {},
        "protocol_family_id": None,
        "protocol_family_label": None,
        "protocol_family_descriptor": None,
        "protocol_family_silhouette": None,
        "intent_alignment_status": "not_available",
        "intent_same_peer_support": None,
        "intent_corpus_baseline": None,
        "intent_association_lift": None,
        "intent_alignment_score": None,
        "recommendation_in_degree": None,
        "recommendation_out_degree": None,
        "recommendation_list_variant_count": None,
        "recommendation_community_id": None,
    }


def _canonical_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        identity = record["input_sha256"] or f"path:{record['relative_path']}"
        groups.setdefault(identity, []).append(record)

    canonical = []
    for identity in sorted(groups):
        candidates = sorted(
            groups[identity],
            key=lambda item: (
                item["index_status"] != "indexed",
                item["provider_metadata_status"] != "validated",
                item["transcript_status"] != "validated",
                item["relative_path"],
            ),
        )
        selected = dict(candidates[0])
        selected["all_aliases"] = sorted(
            item["relative_path"] for item in candidates
        )
        canonical.append(selected)
    return sorted(canonical, key=lambda item: item["relative_path"])


def build_dashboard_data(
    index: dict[str, Any],
    clustering: dict[str, Any] | None = None,
    alignment: dict[str, Any] | None = None,
    recommendation_graph: dict[str, Any] | None = None,
    recommendation_communities: dict[str, Any] | None = None,
    recommendation_drift: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not isinstance(index.get("recordings"), list):
        raise ValueError("corpus index must contain a recordings list")
    index_digest = hashlib.sha256(
        json.dumps(index, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    records = [_flatten_record(item) for item in index["recordings"]]
    records.sort(key=lambda item: item["relative_path"])
    protocol_families = []
    clustering_status = "not_available"
    clustering_digest = None
    if clustering is not None:
        from clustering.protocol_families import validate_protocol_families

        validate_protocol_families(clustering)
        if clustering["source_index_sha256"] == index_digest:
            clustering_status = "validated"
            clustering_digest = hashlib.sha256(
                json.dumps(clustering, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()
            family_lookup = {
                family["family_id"]: family for family in clustering["families"]
            }
            assignment_lookup = {
                item["input_sha256"]: item for item in clustering["assignments"]
            }
            for record in records:
                assignment = assignment_lookup.get(record["input_sha256"])
                if assignment:
                    family = family_lookup[assignment["family_id"]]
                    record["protocol_family_id"] = assignment["family_id"]
                    record["protocol_family_label"] = family["semantic_label"]
                    record["protocol_family_descriptor"] = family["descriptor"]
                    record["protocol_family_silhouette"] = assignment[
                        "silhouette_score"
                    ]
            protocol_families = [
                {key: value for key, value in family.items() if key != "members"}
                for family in clustering["families"]
            ]
        else:
            clustering_status = "stale_index_mismatch"

    alignment_status = "not_available"
    intent_profiles = []
    global_intent_association = None
    alignment_eligible_count = 0
    alignment_excluded_count = 0
    if alignment is not None:
        from alignment.intent_alignment import validate_intent_alignment

        validate_intent_alignment(alignment)
        if (
            clustering_status == "validated"
            and alignment["source_index_sha256"] == index_digest
            and alignment["source_clustering_sha256"] == clustering_digest
        ):
            alignment_status = "validated"
            assessment_lookup = {
                item["input_sha256"]: item
                for item in alignment["recording_assessments"]
            }
            for record in records:
                assessment = assessment_lookup.get(record["input_sha256"])
                if assessment:
                    record["intent_alignment_status"] = assessment[
                        "assessment_status"
                    ]
                    record["intent_same_peer_support"] = assessment[
                        "same_intent_peer_support"
                    ]
                    record["intent_corpus_baseline"] = assessment[
                        "corpus_peer_baseline"
                    ]
                    record["intent_association_lift"] = assessment[
                        "association_lift"
                    ]
                    record["intent_alignment_score"] = assessment[
                        "normalized_alignment_score"
                    ]
            intent_profiles = alignment["intent_profiles"]
            global_intent_association = alignment["global_association"]
            alignment_eligible_count = alignment["eligible_recording_count"]
            alignment_excluded_count = len(alignment["excluded_recordings"])
        else:
            alignment_status = "stale_input_mismatch"

    recommendation_status = "not_available"
    recommendation_summary = None
    top_recommended_tracks = []
    if recommendation_graph is not None:
        from recommendations.graph import validate_recommendation_graph

        validate_recommendation_graph(recommendation_graph)
        recommendation_status = "validated"
        node_lookup = {
            item["track_id"]: item for item in recommendation_graph["nodes"]
        }
        incoming = Counter(
            item["recommended_track_id"] for item in recommendation_graph["edges"]
        )
        outgoing = Counter(item["seed_track_id"] for item in recommendation_graph["edges"])
        variant_counts = {
            item["seed_track_id"]: item["variant_count"]
            for item in recommendation_graph["seed_list_variants"]
        }
        local_counts = Counter(
            record["provider_track_id"] for record in records if record["provider_track_id"]
        )
        for record in records:
            track_id = record["provider_track_id"]
            if track_id and track_id in node_lookup:
                record["recommendation_in_degree"] = incoming[track_id]
                record["recommendation_out_degree"] = outgoing[track_id]
                record["recommendation_list_variant_count"] = variant_counts.get(
                    track_id, 0
                )
        recommendation_summary = {
            **recommendation_graph["summary"],
            "local_provider_track_count": len(local_counts),
            "local_provider_track_matched_count": sum(
                track_id in node_lookup for track_id in local_counts
            ),
        }
        ranked_ids = sorted(
            node_lookup,
            key=lambda track_id: (
                -incoming[track_id],
                -outgoing[track_id],
                (node_lookup[track_id].get("observed_titles") or [track_id])[0],
                track_id,
            ),
        )
        top_recommended_tracks = [
            {
                "track_id": track_id,
                "title": (node_lookup[track_id].get("observed_titles") or [track_id])[0],
                "incoming_recommendation_count": incoming[track_id],
                "outgoing_recommendation_count": outgoing[track_id],
                "local_recording_count": local_counts[track_id],
            }
            for track_id in ranked_ids[:15]
        ]

    recommendation_community_status = "not_available"
    recommendation_community_summary = None
    recommendation_community_profiles = []
    recommendation_context_association = None
    if recommendation_communities is not None:
        from recommendations.communities import validate_recommendation_communities

        validate_recommendation_communities(recommendation_communities)
        context_sources = recommendation_communities["context_sources"]
        if (
            recommendation_status == "validated"
            and recommendation_communities["source_graph_sha256"]
            == hashlib.sha256(
                json.dumps(
                    recommendation_graph, sort_keys=True, separators=(",", ":")
                ).encode()
            ).hexdigest()
            and context_sources.get("corpus_index_sha256") == index_digest
            and context_sources.get("clustering_sha256") == clustering_digest
        ):
            recommendation_community_status = "validated"
            community_lookup = {
                item["track_id"]: item["community_id"]
                for item in recommendation_communities["assignments"]
            }
            for record in records:
                if record["provider_track_id"] in community_lookup:
                    record["recommendation_community_id"] = community_lookup[
                        record["provider_track_id"]
                    ]
            recommendation_community_summary = recommendation_communities["summary"]
            recommendation_community_profiles = [
                {key: value for key, value in item.items() if key != "members"}
                for item in recommendation_communities["communities"][:15]
            ]
            recommendation_context_association = recommendation_communities[
                "posthoc_context_association"
            ]
        else:
            recommendation_community_status = "stale_input_mismatch"

    recommendation_drift_status = "not_available"
    recommendation_drift_summary = None
    if recommendation_drift is not None:
        from recommendations.communities import validate_recommendation_drift

        validate_recommendation_drift(recommendation_drift)
        graph_observations = {
            item["observation_id"]
            for item in (recommendation_graph or {}).get("source_observations", [])
        }
        if set(recommendation_drift["source_observations"]) == graph_observations:
            recommendation_drift_status = "validated"
            recommendation_drift_summary = recommendation_drift["summary"]
        else:
            recommendation_drift_status = "stale_input_mismatch"
    canonical = _canonical_records(records)
    warnings = []
    legacy_count = sum(r["provenance_status"] == "legacy_missing" for r in records)
    invalid_count = sum(r["index_status"] == "invalid_evidence" for r in records)
    deferred_count = sum(r["index_status"] == "deferred" for r in records)
    duplicate_alias_count = len(records) - len(canonical)
    if legacy_count:
        warnings.append(
            {
                "kind": "legacy_provenance",
                "count": legacy_count,
                "message": "analyses predate run provenance and must be rerun for validated lineage",
            }
        )
    if deferred_count:
        warnings.append(
            {
                "kind": "deferred",
                "count": deferred_count,
                "message": "recordings are indexed but have no completed evidence analysis",
            }
        )
    if invalid_count:
        warnings.append(
            {
                "kind": "invalid_evidence",
                "count": invalid_count,
                "message": "evidence documents failed validation",
            }
        )
    if duplicate_alias_count:
        warnings.append(
            {
                "kind": "duplicate_aliases",
                "count": duplicate_alias_count,
                "message": "duplicate aliases are excluded from comparison statistics by default",
            }
        )
    if clustering_status == "stale_index_mismatch":
        warnings.append(
            {
                "kind": "stale_clustering",
                "count": 1,
                "message": "protocol families were built from a different corpus index and were not displayed",
            }
        )
    if alignment_status == "stale_input_mismatch":
        warnings.append(
            {
                "kind": "stale_intent_alignment",
                "count": 1,
                "message": "intent alignment was built from different corpus or clustering inputs and was not displayed",
            }
        )
    if alignment_status == "validated" and alignment_excluded_count:
        warnings.append(
            {
                "kind": "intent_alignment_exclusions",
                "count": alignment_excluded_count,
                "message": "unique inputs were excluded from intent alignment because duplicate copies carry conflicting intent labels",
            }
        )
    if recommendation_community_status == "stale_input_mismatch":
        warnings.append(
            {
                "kind": "stale_recommendation_communities",
                "count": 1,
                "message": "recommendation communities were built from different graph or corpus inputs and were not displayed",
            }
        )
    if recommendation_drift_status == "validated" and not recommendation_drift_summary[
        "assessed_seed_count"
    ]:
        warnings.append(
            {
                "kind": "insufficient_recommendation_drift",
                "count": recommendation_drift_summary["repeated_seed_count"],
                "message": "repeated seed appearances exist, but none have non-empty recommendation sets in two distinct captures; temporal drift is not yet measurable",
            }
        )
    if clustering_status == "validated":
        silhouette = float(clustering["method"]["overall_silhouette_score"])
        if silhouette < 0.25:
            warnings.append(
                {
                    "kind": "exploratory_clustering",
                    "count": len(protocol_families),
                    "message": f"protocol families are tentative (overall silhouette {silhouette:.3f}); interpret boundaries cautiously",
                }
            )
    configuration_counts = index.get("analysis_configuration_version_counts", {})
    if len(configuration_counts) > 1:
        warnings.append(
            {
                "kind": "mixed_analysis_configuration",
                "count": sum(configuration_counts.values()),
                "message": (
                    "analyses span multiple configuration versions; rerun the corpus "
                    "before treating cross-recording comparisons as calibrated"
                ),
            }
        )
    return {
        "dashboard_schema_version": DASHBOARD_SCHEMA_VERSION,
        "source_index_schema_version": index.get("index_schema_version"),
        "source_index_sha256": index_digest,
        "overview": {
            "recording_alias_count": len(records),
            "unique_input_count": len(canonical),
            "unique_indexed_count": sum(
                item["index_status"] == "indexed" for item in canonical
            ),
            "indexed_evidence_count": sum(
                int(item["evidence_count"] or 0) for item in canonical
            ),
            "duplicate_group_count": len(index.get("duplicate_input_groups", [])),
            "protocol_family_count": len(protocol_families),
            "scored_intent_alignment_count": sum(
                item["intent_alignment_status"] == "scored" for item in canonical
            ),
            "eligible_intent_alignment_count": alignment_eligible_count,
            "excluded_intent_alignment_count": alignment_excluded_count,
            "provider_metadata_count": sum(
                item["provider_metadata_status"] == "validated" for item in canonical
            ),
            "transcript_sidecar_count": sum(
                item["transcript_status"] == "validated" for item in canonical
            ),
            "speech_context_comparison_count": sum(
                item["speech_context_comparison_available"] for item in canonical
            ),
            "analysis_configuration_versions": configuration_counts,
        },
        "facets": {
            "sources": sorted(Counter(r["source"] for r in records)),
            "categories": sorted(Counter(r["category"] for r in records)),
            "stated_intents": sorted(Counter(r["stated_intent"] for r in records)),
            "index_statuses": sorted(Counter(r["index_status"] for r in records)),
            "provenance_statuses": sorted(
                Counter(r["provenance_status"] for r in records)
            ),
            "protocol_families": [
                family["family_id"] for family in protocol_families
            ],
            "provider_metadata_statuses": sorted(
                Counter(r["provider_metadata_status"] for r in records)
            ),
            "provider_mental_states": sorted(
                {r["provider_mental_state"] for r in records if r["provider_mental_state"]}
            ),
            "provider_activities": sorted(
                {r["provider_activity"] for r in records if r["provider_activity"]}
            ),
            "provider_styles": sorted(
                {r["provider_style"] for r in records if r["provider_style"]}
            ),
            "transcript_statuses": sorted(
                Counter(r["transcript_status"] for r in records)
            ),
            "transcript_languages": sorted(
                {
                    r["transcript_language_code"]
                    for r in records
                    if r["transcript_language_code"]
                }
            ),
        },
        "clustering_status": clustering_status,
        "clustering_method": clustering.get("method") if clustering_status == "validated" else None,
        "protocol_families": protocol_families,
        "alignment_status": alignment_status,
        "global_intent_association": global_intent_association,
        "intent_profiles": intent_profiles,
        "recommendation_status": recommendation_status,
        "recommendation_summary": recommendation_summary,
        "top_recommended_tracks": top_recommended_tracks,
        "recommendation_community_status": recommendation_community_status,
        "recommendation_community_summary": recommendation_community_summary,
        "recommendation_communities": recommendation_community_profiles,
        "recommendation_context_association": recommendation_context_association,
        "recommendation_drift_status": recommendation_drift_status,
        "recommendation_drift_summary": recommendation_drift_summary,
        "warnings": warnings,
        "recordings": records,
        "comparison_recordings": canonical,
    }


def write_dashboard(data: dict[str, Any], output_directory: Path) -> Path:
    template = TEMPLATE_PATH.read_text()
    payload = json.dumps(data, sort_keys=True, separators=(",", ":"))
    payload = payload.replace("</", "<\\/")
    html = template.replace("__AVE_DASHBOARD_DATA__", payload)
    if html == template:
        raise ValueError("dashboard template data marker is missing")
    output_directory.mkdir(parents=True, exist_ok=True)
    output_path = output_directory / "index.html"
    output_path.write_text(html)
    return output_path
