from __future__ import annotations

import csv
import hashlib
import itertools
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from clustering.protocol_families import validate_protocol_families
from recommendations.graph import validate_recommendation_graph


CONTEXT_DRIFT_SCHEMA_VERSION = "1.0.0"
METHOD_VERSION = "ave_provider_context_drift_1.0.0"


def _digest(document: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(document, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _normalize(value: str | None) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    expanded = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", value.strip())
    normalized = re.sub(r"[^a-z0-9]+", "_", expanded.lower()).strip("_")
    return normalized or None


def _normalized_values(values: list[str] | tuple[str, ...] | set[str]) -> list[str]:
    return sorted({item for value in values if (item := _normalize(value))})


def _filename_activity_candidates(filename: str, vocabulary: set[str]) -> list[str]:
    stem = Path(filename).stem
    normalized_stem = f"_{_normalize(stem) or ''}_"
    matches = {
        label
        for label in vocabulary
        if label and f"_{label}_" in normalized_stem
    }
    # Prefer the more specific label when one label is wholly contained in another.
    return sorted(
        label
        for label in matches
        if not any(label != other and f"_{label}_" in f"_{other}_" for other in matches)
    )


def _canonical_records(index: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in index.get("recordings", []):
        digest = record.get("input_sha256")
        if digest and record.get("index_status") == "indexed":
            grouped[digest].append(record)
    canonical = []
    exclusions = []
    for digest, records in sorted(grouped.items()):
        intents = sorted(
            {
                value
                for record in records
                if (value := _normalize(record.get("stated_intent")))
                and value != "unknown"
            }
        )
        if len(intents) > 1:
            exclusions.append(
                {
                    "input_sha256": digest,
                    "relative_paths": sorted(item["relative_path"] for item in records),
                    "reason": "conflicting_duplicate_intents",
                    "directory_claimed_intents": intents,
                }
            )
            continue
        canonical.append(
            sorted(
                records,
                key=lambda item: (
                    item.get("provider_metadata_status") != "validated",
                    item["relative_path"],
                ),
            )[0]
        )
    return canonical, exclusions


def _provider_layers(
    record: dict[str, Any],
) -> tuple[list[str], list[str], list[str]]:
    provider = record.get("provider_metadata") or {}
    taxonomy = provider.get("taxonomy") or {}
    mobile = _normalized_values(
        [taxonomy.get("mobile_activity") or taxonomy.get("activity")]
    )
    web = _normalized_values([taxonomy.get("web_activity")])
    tags = taxonomy.get("all_provider_tags") or {}
    activity_tags = _normalized_values(tags.get("activity") or [])
    return mobile, web, activity_tags


def _pairwise_layers(layers: dict[str, list[str]]) -> list[dict[str, Any]]:
    comparisons = []
    for left, right in itertools.combinations(sorted(layers), 2):
        left_values = set(layers[left])
        right_values = set(layers[right])
        if not left_values or not right_values:
            continue
        overlap = sorted(left_values & right_values)
        comparisons.append(
            {
                "left_layer": left,
                "right_layer": right,
                "status": "overlap" if overlap else "different",
                "overlap": overlap,
            }
        )
    return comparisons


def _comparison_status(comparisons: list[dict[str, Any]]) -> str:
    if not comparisons:
        return "insufficient_context"
    overlap_count = sum(item["status"] == "overlap" for item in comparisons)
    if overlap_count == len(comparisons):
        return "consistent"
    if overlap_count == 0:
        return "divergent"
    return "mixed"


def build_context_drift(
    index: dict[str, Any],
    clustering: dict[str, Any],
    recommendation_graph: dict[str, Any],
) -> dict[str, Any]:
    validate_protocol_families(clustering)
    validate_recommendation_graph(recommendation_graph)
    index_digest = _digest(index)
    clustering_digest = _digest(clustering)
    graph_digest = _digest(recommendation_graph)
    if clustering.get("source_index_sha256") != index_digest:
        raise ValueError("clustering artifact does not match the corpus index")

    family_by_digest = {
        item["input_sha256"]: item["family_id"]
        for item in clustering.get("assignments", [])
    }
    family_labels = {
        item["family_id"]: item["semantic_label"]
        for item in clustering.get("families", [])
    }
    node_by_id = {item["track_id"]: item for item in recommendation_graph["nodes"]}
    contexts_by_seed: dict[str, set[str]] = defaultdict(set)
    for observation in recommendation_graph.get("source_observations", []):
        context = observation.get("observation_context") or {}
        seed_id = context.get("seed_track_id")
        visible_intent = _normalize(context.get("visible_intent"))
        if seed_id and visible_intent:
            contexts_by_seed[seed_id].add(visible_intent)
    for edge in recommendation_graph["edges"]:
        for context in edge.get("observed_contexts", []):
            if visible_intent := _normalize(context.get("visible_intent")):
                contexts_by_seed[edge["seed_track_id"]].add(visible_intent)

    canonical, exclusions = _canonical_records(index)
    vocabulary = {
        value
        for record in canonical
        if (value := _normalize(record.get("stated_intent"))) and value != "unknown"
    }
    for record in canonical:
        mobile, web, tags = _provider_layers(record)
        vocabulary.update(mobile)
        vocabulary.update(web)
        vocabulary.update(tags)
    for node in recommendation_graph["nodes"]:
        vocabulary.update(_normalized_values(node.get("activities") or []))
        vocabulary.update(_normalized_values((node.get("tags") or {}).get("activity") or []))
    for values in contexts_by_seed.values():
        vocabulary.update(values)

    outgoing: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for edge in recommendation_graph["edges"]:
        outgoing[edge["seed_track_id"]].append(edge)

    assessments = []
    transition_counts: Counter[tuple[str, str]] = Counter()
    for record in canonical:
        provider = record.get("provider_metadata") or {}
        track_id = (provider.get("provider_track") or {}).get("track_id")
        mobile, web, tags = _provider_layers(record)
        directory_claim = _normalized_values([record.get("stated_intent")])
        filename_claim = _filename_activity_candidates(
            Path(record["relative_path"]).name, vocabulary
        )
        visible = sorted(contexts_by_seed.get(track_id, set())) if track_id else []
        layers = {
            "directory_claimed_intent": directory_claim,
            "filename_activity": filename_claim,
            "provider_mobile_activity": mobile,
            "provider_web_activity": web,
            "provider_activity_tags": tags,
            "visible_session_intent": visible,
        }
        comparisons = _pairwise_layers(layers)

        target_activity_counts: Counter[str] = Counter()
        known_targets: set[str] = set()
        all_targets: set[str] = set()
        within_visible_targets: set[str] = set()
        for edge in outgoing.get(track_id, []):
            target_id = edge["recommended_track_id"]
            all_targets.add(target_id)
            target = node_by_id[target_id]
            target_activities = set(_normalized_values(target.get("activities") or []))
            target_activities.update(
                _normalized_values((target.get("tags") or {}).get("activity") or [])
            )
            if target_activities:
                known_targets.add(target_id)
                for activity in target_activities:
                    target_activity_counts[activity] += 1
            edge_contexts = {
                normalized
                for context in edge.get("observed_contexts", [])
                if (normalized := _normalize(context.get("visible_intent")))
            }
            if target_activities & edge_contexts:
                within_visible_targets.add(target_id)
            for source_context in edge_contexts:
                for target_activity in target_activities:
                    transition_counts[(source_context, target_activity)] += 1

        status = _comparison_status(comparisons)
        assessments.append(
            {
                "relative_path": record["relative_path"],
                "input_sha256": record["input_sha256"],
                "provider_track_id": track_id,
                "provider_title": (provider.get("provider_track") or {}).get("title"),
                "context_layers": layers,
                "pairwise_comparisons": comparisons,
                "context_status": status,
                "overlap_count": sum(item["status"] == "overlap" for item in comparisons),
                "difference_count": sum(item["status"] == "different" for item in comparisons),
                "protocol_family_id": family_by_digest.get(record["input_sha256"]),
                "protocol_family_label": family_labels.get(
                    family_by_digest.get(record["input_sha256"])
                ),
                "recommendation_context": {
                    "unique_target_count": len(all_targets),
                    "target_with_activity_count": len(known_targets),
                    "target_activity_distribution": [
                        {"activity": activity, "target_count": count}
                        for activity, count in sorted(
                            target_activity_counts.items(), key=lambda item: (-item[1], item[0])
                        )
                    ],
                    "within_visible_context_target_count": len(within_visible_targets),
                    "within_visible_context_rate": round(
                        len(within_visible_targets) / len(known_targets), 6
                    )
                    if known_targets and visible
                    else None,
                },
            }
        )

    status_counts = Counter(item["context_status"] for item in assessments)
    layer_coverage = {
        layer: sum(bool(item["context_layers"][layer]) for item in assessments)
        for layer in (
            "directory_claimed_intent",
            "filename_activity",
            "provider_mobile_activity",
            "provider_web_activity",
            "provider_activity_tags",
            "visible_session_intent",
        )
    }
    document = {
        "context_drift_schema_version": CONTEXT_DRIFT_SCHEMA_VERSION,
        "method": {
            "name": "provider_context_layer_comparison",
            "version": METHOD_VERSION,
            "normalization": "case_and_separator_only_no_semantic_synonyms",
            "unit_of_analysis": "one_canonical_recording_per_input_sha256",
        },
        "source_index_sha256": index_digest,
        "source_clustering_sha256": clustering_digest,
        "source_recommendation_graph_sha256": graph_digest,
        "summary": {
            "assessed_recording_count": len(assessments),
            "provider_linked_recording_count": sum(
                bool(item["provider_track_id"]) for item in assessments
            ),
            "recommendation_context_recording_count": sum(
                bool(item["context_layers"]["visible_session_intent"])
                for item in assessments
            ),
            "context_status_counts": dict(sorted(status_counts.items())),
            "layer_coverage": layer_coverage,
            "excluded_duplicate_input_count": len(exclusions),
        },
        "context_transitions": [
            {
                "visible_session_intent": source,
                "recommended_track_activity": target,
                "unique_relationship_count": count,
            }
            for (source, target), count in sorted(
                transition_counts.items(), key=lambda item: (-item[1], item[0])
            )
        ],
        "recording_assessments": assessments,
        "excluded_recordings": exclusions,
        "interpretation": {
            "status_meaning": "exact normalized overlap among independently preserved context labels",
            "does_not_measure": [
                "therapeutic efficacy",
                "provider catalog correctness",
                "recommendation causality or personalization",
                "equivalence between a context label and an observed protocol family",
            ],
            "web_activity_note": "provider sidecar 1.1 preserves mobile and web activity separately; legacy 1.0 sidecars preserve mobile activity as taxonomy.activity",
        },
    }
    validate_context_drift(document)
    return document


def validate_context_drift(document: dict[str, Any]) -> None:
    if document.get("context_drift_schema_version") != CONTEXT_DRIFT_SCHEMA_VERSION:
        raise ValueError("unsupported context drift schema version")
    for field in (
        "source_index_sha256",
        "source_clustering_sha256",
        "source_recommendation_graph_sha256",
    ):
        if not re.fullmatch(r"[0-9a-f]{64}", str(document.get(field, ""))):
            raise ValueError(f"{field} must be a SHA-256 digest")
    assessments = document.get("recording_assessments")
    if not isinstance(assessments, list):
        raise ValueError("recording_assessments must be a list")
    identities = [item.get("input_sha256") for item in assessments]
    if len(identities) != len(set(identities)):
        raise ValueError("recording assessments must use unique input identities")
    allowed = {"consistent", "mixed", "divergent", "insufficient_context"}
    if any(item.get("context_status") not in allowed for item in assessments):
        raise ValueError("invalid recording context status")


def write_context_drift(document: dict[str, Any], output_directory: Path) -> tuple[Path, Path]:
    validate_context_drift(document)
    output_directory.mkdir(parents=True, exist_ok=True)
    json_path = output_directory / "context_drift.json"
    csv_path = output_directory / "context_drift.csv"
    json_path.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n")
    fields = [
        "relative_path",
        "input_sha256",
        "provider_track_id",
        "provider_title",
        "context_status",
        "overlap_count",
        "difference_count",
        "protocol_family_id",
        "protocol_family_label",
        "directory_claimed_intent",
        "filename_activity",
        "provider_mobile_activity",
        "provider_web_activity",
        "provider_activity_tags",
        "visible_session_intent",
        "recommendation_target_count",
        "within_visible_context_rate",
    ]
    with csv_path.open("w", newline="") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=fields)
        writer.writeheader()
        for item in document["recording_assessments"]:
            layers = item["context_layers"]
            writer.writerow(
                {
                    **{field: item.get(field) for field in fields[:9]},
                    **{field: "|".join(layers[field]) for field in fields[9:15]},
                    "recommendation_target_count": item["recommendation_context"]["unique_target_count"],
                    "within_visible_context_rate": item["recommendation_context"]["within_visible_context_rate"],
                }
            )
    return json_path, csv_path
