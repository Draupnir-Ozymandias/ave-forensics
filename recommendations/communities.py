from __future__ import annotations

import csv
import hashlib
import json
import math
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path
from typing import Any

from clustering.protocol_families import validate_protocol_families
from recommendations.graph import (
    validate_recommendation_capture,
    validate_recommendation_graph,
)


COMMUNITY_SCHEMA_VERSION = "1.0.0"
DRIFT_SCHEMA_VERSION = "1.0.0"
COMMUNITY_METHOD_VERSION = "ave_deterministic_weighted_label_propagation_1.0.0"
DRIFT_METHOD_VERSION = "ave_repeated_recommendation_capture_drift_1.0.0"


def _digest(document: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(document, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _topology(graph: dict[str, Any]) -> tuple[list[str], dict[str, Counter[str]]]:
    nodes = sorted(node["track_id"] for node in graph["nodes"])
    adjacency: dict[str, Counter[str]] = {node: Counter() for node in nodes}
    for edge in graph["edges"]:
        source = edge["seed_track_id"]
        target = edge["recommended_track_id"]
        if source == target:
            continue
        adjacency[source][target] += 1
        adjacency[target][source] += 1
    return nodes, adjacency


def _label_propagation(
    nodes: list[str], adjacency: dict[str, Counter[str]], *, maximum_iterations: int
) -> tuple[dict[str, str], int]:
    labels = {node: node for node in nodes}
    order = sorted(nodes, key=lambda node: (-sum(adjacency[node].values()), node))
    completed_iterations = 0
    for iteration in range(maximum_iterations):
        changed = 0
        for node in order:
            if not adjacency[node]:
                continue
            scores: Counter[str] = Counter()
            for neighbor, weight in adjacency[node].items():
                scores[labels[neighbor]] += weight
            best_score = max(scores.values())
            choices = sorted(
                label for label, score in scores.items() if score == best_score
            )
            new_label = labels[node] if labels[node] in choices else choices[0]
            if new_label != labels[node]:
                labels[node] = new_label
                changed += 1
        completed_iterations = iteration + 1
        if not changed:
            break
    return labels, completed_iterations


def _modularity(labels: dict[str, str], adjacency: dict[str, Counter[str]]) -> float:
    degree = {node: sum(neighbors.values()) for node, neighbors in adjacency.items()}
    total_edge_weight = sum(degree.values()) / 2
    if total_edge_weight <= 0:
        return 0.0
    groups: dict[str, list[str]] = defaultdict(list)
    for node, label in labels.items():
        if adjacency[node]:
            groups[label].append(node)
    score = 0.0
    for members in groups.values():
        member_set = set(members)
        internal_twice = sum(
            weight
            for node in members
            for neighbor, weight in adjacency[node].items()
            if neighbor in member_set
        )
        internal = internal_twice / 2
        degree_sum = sum(degree[node] for node in members)
        score += internal / total_edge_weight - (
            degree_sum / (2 * total_edge_weight)
        ) ** 2
    return round(score, 6)


def _distribution(values: list[str]) -> dict[str, int]:
    return dict(sorted(Counter(values).items(), key=lambda item: (-item[1], item[0])))


def _categorical_association(pairs: list[tuple[str, str]]) -> dict[str, Any]:
    total = len(pairs)
    if not pairs:
        return {
            "sample_count": 0,
            "left_category_count": 0,
            "community_count": 0,
            "cramers_v": None,
            "normalized_mutual_information": None,
        }
    left_counts = Counter(left for left, _ in pairs)
    community_counts = Counter(right for _, right in pairs)
    joint = Counter(pairs)
    chi_square = 0.0
    mutual_information = 0.0
    for left in left_counts:
        for community in community_counts:
            observed = joint[(left, community)]
            expected = left_counts[left] * community_counts[community] / total
            if expected:
                chi_square += (observed - expected) ** 2 / expected
            if observed:
                probability = observed / total
                mutual_information += probability * math.log(
                    probability
                    / ((left_counts[left] / total) * (community_counts[community] / total))
                )
    left_entropy = -sum(
        (count / total) * math.log(count / total) for count in left_counts.values()
    )
    community_entropy = -sum(
        (count / total) * math.log(count / total)
        for count in community_counts.values()
    )
    cramers_denominator = total * min(
        len(left_counts) - 1, len(community_counts) - 1
    )
    entropy_denominator = math.sqrt(left_entropy * community_entropy)
    return {
        "sample_count": total,
        "left_category_count": len(left_counts),
        "community_count": len(community_counts),
        "cramers_v": round(math.sqrt(chi_square / cramers_denominator), 6)
        if cramers_denominator > 0
        else 0.0,
        "normalized_mutual_information": round(
            mutual_information / entropy_denominator, 6
        )
        if entropy_denominator > 0
        else 0.0,
    }


def build_recommendation_communities(
    graph: dict[str, Any],
    *,
    index: dict[str, Any] | None = None,
    clustering: dict[str, Any] | None = None,
    maximum_iterations: int = 100,
) -> dict[str, Any]:
    validate_recommendation_graph(graph)
    if maximum_iterations < 1:
        raise ValueError("maximum_iterations must be positive")
    nodes, adjacency = _topology(graph)
    raw_labels, iterations = _label_propagation(
        nodes, adjacency, maximum_iterations=maximum_iterations
    )
    raw_groups: dict[str, list[str]] = defaultdict(list)
    isolates = []
    for node in nodes:
        if adjacency[node]:
            raw_groups[raw_labels[node]].append(node)
        else:
            isolates.append(node)
    ordered_groups = sorted(
        (sorted(members) for members in raw_groups.values()),
        key=lambda members: (-len(members), members[0]),
    )
    community_by_node = {
        node: f"recommendation_community_{number:03d}"
        for number, members in enumerate(ordered_groups, start=1)
        for node in members
    }

    node_lookup = {node["track_id"]: node for node in graph["nodes"]}
    local_context: dict[str, list[dict[str, Any]]] = defaultdict(list)
    index_sha256 = _digest(index) if index is not None else None
    clustering_sha256 = _digest(clustering) if clustering is not None else None
    if clustering is not None:
        if index is None:
            raise ValueError("clustering context requires a corpus index")
        validate_protocol_families(clustering)
        if clustering.get("source_index_sha256") != index_sha256:
            raise ValueError("clustering artifact does not match corpus index")
        assignment_lookup = {
            item["input_sha256"]: item for item in clustering["assignments"]
        }
        family_lookup = {
            item["family_id"]: item["semantic_label"]
            for item in clustering["families"]
        }
        local_accumulator: dict[tuple[str, str], dict[str, Any]] = {}
        for record in index.get("recordings", []):
            provider = record.get("provider_metadata") or {}
            track_id = (provider.get("provider_track") or {}).get("track_id")
            digest = record.get("input_sha256")
            identity = (track_id, digest)
            if not track_id or not digest:
                continue
            assignment = assignment_lookup.get(digest)
            item = local_accumulator.setdefault(
                identity,
                {
                    "input_sha256": digest,
                    "relative_paths": set(),
                    "stated_intents": set(),
                    "family_id": assignment.get("family_id") if assignment else None,
                    "family_label": family_lookup.get(assignment.get("family_id"))
                    if assignment
                    else None,
                },
            )
            item["relative_paths"].add(record["relative_path"])
            item["stated_intents"].add(record.get("stated_intent") or "unknown")
        for (track_id, _), item in sorted(local_accumulator.items()):
            local_context[track_id].append(
                {
                    **item,
                    "relative_paths": sorted(item["relative_paths"]),
                    "stated_intents": sorted(item["stated_intents"]),
                }
            )

    assignments = []
    communities = []
    for number, members in enumerate(ordered_groups, start=1):
        community_id = f"recommendation_community_{number:03d}"
        member_set = set(members)
        internal_edge_count = sum(
            edge["seed_track_id"] in member_set
            and edge["recommended_track_id"] in member_set
            for edge in graph["edges"]
        )
        boundary_edge_count = sum(
            (edge["seed_track_id"] in member_set)
            != (edge["recommended_track_id"] in member_set)
            for edge in graph["edges"]
        )
        ranked = sorted(
            members,
            key=lambda node: (-sum(adjacency[node].values()), node),
        )
        local = [item for node in members for item in local_context.get(node, [])]
        mental_states = [
            value for node in members for value in node_lookup[node]["mental_states"]
        ]
        activities = [
            value for node in members for value in node_lookup[node]["activities"]
        ]
        communities.append(
            {
                "community_id": community_id,
                "member_count": len(members),
                "internal_directed_edge_count": internal_edge_count,
                "boundary_directed_edge_count": boundary_edge_count,
                "topology_hubs": [
                    {
                        "track_id": node,
                        "title": (node_lookup[node]["observed_titles"] or [node])[0],
                        "undirected_degree": sum(adjacency[node].values()),
                    }
                    for node in ranked[:5]
                ],
                "context_not_used_for_community_discovery": {
                    "mental_state_distribution": _distribution(mental_states),
                    "activity_distribution": _distribution(activities),
                    "local_recording_count": len(local),
                    "stated_intent_distribution": _distribution(
                        [
                            intent
                            for item in local
                            for intent in item["stated_intents"]
                        ]
                    ),
                    "observed_family_distribution": _distribution(
                        [item["family_label"] for item in local if item["family_label"]]
                    ),
                },
                "members": members,
            }
        )
        for node in members:
            assignments.append(
                {
                    "track_id": node,
                    "title": (node_lookup[node]["observed_titles"] or [node])[0],
                    "community_id": community_id,
                    "undirected_degree": sum(adjacency[node].values()),
                    "local_recordings": local_context.get(node, []),
                }
            )

    mental_state_pairs = []
    activity_pairs = []
    family_pairs = []
    intent_pairs = []
    for assignment in assignments:
        node = node_lookup[assignment["track_id"]]
        for value in node["mental_states"]:
            mental_state_pairs.append((value, assignment["community_id"]))
        for value in node["activities"]:
            activity_pairs.append((value, assignment["community_id"]))
        for local in assignment["local_recordings"]:
            if local["family_label"]:
                family_pairs.append((local["family_label"], assignment["community_id"]))
            for intent in local["stated_intents"]:
                intent_pairs.append((intent, assignment["community_id"]))

    document = {
        "recommendation_community_schema_version": COMMUNITY_SCHEMA_VERSION,
        "source_graph_sha256": _digest(graph),
        "context_sources": {
            "corpus_index_sha256": index_sha256,
            "clustering_sha256": clustering_sha256,
        },
        "method": {
            "name": COMMUNITY_METHOD_VERSION,
            "algorithm": "deterministic asynchronous weighted label propagation",
            "edge_projection": "directed recommendation edges projected to undirected unit weights",
            "processing_order": "descending weighted degree then track_id",
            "maximum_iterations": maximum_iterations,
            "completed_iterations": iterations,
            "context_fields_used": [],
        },
        "summary": {
            "graph_node_count": len(nodes),
            "connected_node_count": len(nodes) - len(isolates),
            "isolated_node_count": len(isolates),
            "community_count": len(communities),
            "modularity": _modularity(raw_labels, adjacency),
            "local_recording_count": sum(
                len(item["local_recordings"]) for item in assignments
            ),
        },
        "posthoc_context_association": {
            "provider_mental_state": _categorical_association(mental_state_pairs),
            "provider_activity": _categorical_association(activity_pairs),
            "local_observed_signal_family": _categorical_association(family_pairs),
            "local_stated_intent": _categorical_association(intent_pairs),
            "interpretation": "context was attached after topology-only community discovery; sparse multi-category tables may inflate apparent association",
        },
        "communities": communities,
        "assignments": sorted(assignments, key=lambda item: item["track_id"]),
        "isolated_nodes": [
            {
                "track_id": node,
                "title": (node_lookup[node]["observed_titles"] or [node])[0],
                "reason": "no_observed_recommendation_edges",
                "local_recordings": local_context.get(node, []),
            }
            for node in isolates
        ],
        "interpretation": {
            "community_meaning": "topological neighborhood in captured provider-declared similar-track edges",
            "does_not_establish": [
                "provider recommendation algorithm",
                "therapeutic equivalence",
                "observed playback sequence",
                "causal effect",
            ],
        },
    }
    validate_recommendation_communities(document)
    return document


def validate_recommendation_communities(document: dict[str, Any]) -> None:
    if document.get("recommendation_community_schema_version") != COMMUNITY_SCHEMA_VERSION:
        raise ValueError("unsupported recommendation community schema version")
    communities = document.get("communities")
    assignments = document.get("assignments")
    if not isinstance(communities, list) or not isinstance(assignments, list):
        raise ValueError("communities and assignments must be lists")
    community_ids = [item.get("community_id") for item in communities]
    if len(community_ids) != len(set(community_ids)):
        raise ValueError("community identifiers must be unique")
    assigned_nodes = [item.get("track_id") for item in assignments]
    if len(assigned_nodes) != len(set(assigned_nodes)):
        raise ValueError("track nodes may have only one community assignment")
    if any(item.get("community_id") not in community_ids for item in assignments):
        raise ValueError("assignment references an unknown community")
    if not isinstance(document.get("posthoc_context_association"), dict):
        raise ValueError("posthoc_context_association is required")


def _jaccard(left: set[str], right: set[str]) -> float:
    union = left | right
    return len(left & right) / len(union) if union else 1.0


def analyze_recommendation_drift(
    captures: list[dict[str, Any]],
) -> dict[str, Any]:
    unique = {}
    for capture in captures:
        validate_recommendation_capture(capture)
        unique[capture["observation_id"]] = capture
    ordered = [unique[key] for key in sorted(unique)]
    if not ordered:
        raise ValueError("at least one recommendation capture is required")

    per_seed: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(
        lambda: defaultdict(list)
    )
    within_capture_variants = []
    for capture in ordered:
        observation_id = capture["observation_id"]
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for item in capture["list_observations"]:
            grouped[item["seed_track_id"]].append(item)
            per_seed[item["seed_track_id"]][observation_id].append(item)
        for seed_id, variants in sorted(grouped.items()):
            if len(variants) > 1:
                within_capture_variants.append(
                    {
                        "observation_id": observation_id,
                        "seed_track_id": seed_id,
                        "variant_count": len(variants),
                        "recommendation_counts": sorted(
                            item["recommendation_count"] for item in variants
                        ),
                    }
                )

    assessments = []
    for seed_id in sorted(per_seed):
        observations = per_seed[seed_id]
        unions = {
            observation_id: {
                track_id
                for item in variants
                for track_id in item["recommended_track_ids"]
            }
            for observation_id, variants in observations.items()
        }
        nonempty = {
            observation_id: targets
            for observation_id, targets in unions.items()
            if targets
        }
        comparisons = [
            {
                "left_observation_id": left_id,
                "right_observation_id": right_id,
                "jaccard_similarity": round(
                    _jaccard(nonempty[left_id], nonempty[right_id]), 6
                ),
                "retained_count": len(nonempty[left_id] & nonempty[right_id]),
                "added_count": len(nonempty[right_id] - nonempty[left_id]),
                "removed_count": len(nonempty[left_id] - nonempty[right_id]),
            }
            for left_id, right_id in combinations(sorted(nonempty), 2)
        ]
        if len(observations) < 2:
            status = "not_repeated"
        elif len(nonempty) < 2:
            status = "insufficient_nonempty_repeats"
        else:
            status = "assessed"
        similarities = [item["jaccard_similarity"] for item in comparisons]
        assessments.append(
            {
                "seed_track_id": seed_id,
                "assessment_status": status,
                "observation_count": len(observations),
                "nonempty_observation_count": len(nonempty),
                "mean_jaccard_similarity": round(
                    sum(similarities) / len(similarities), 6
                )
                if similarities
                else None,
                "minimum_jaccard_similarity": min(similarities)
                if similarities
                else None,
                "pairwise_comparisons": comparisons,
            }
        )

    document = {
        "recommendation_drift_schema_version": DRIFT_SCHEMA_VERSION,
        "method": {
            "name": DRIFT_METHOD_VERSION,
            "comparison_unit": "union of non-empty recommendation lists per seed and capture observation",
            "similarity_metric": "Jaccard similarity on recommended track IDs",
            "empty_list_policy": "retained as representation evidence but not treated as a comparable recommendation set",
        },
        "source_observations": [item["observation_id"] for item in ordered],
        "summary": {
            "observation_count": len(ordered),
            "observed_seed_count": len(assessments),
            "repeated_seed_count": sum(
                item["observation_count"] >= 2 for item in assessments
            ),
            "assessed_seed_count": sum(
                item["assessment_status"] == "assessed" for item in assessments
            ),
            "within_capture_variant_seed_count": len(within_capture_variants),
        },
        "seed_assessments": assessments,
        "within_capture_variants": within_capture_variants,
        "interpretation": {
            "drift_requires": "at least two distinct observations with non-empty recommendation sets for the same seed",
            "does_not_infer": "temporal drift from empty versus populated object representations within one response",
        },
    }
    validate_recommendation_drift(document)
    return document


def validate_recommendation_drift(document: dict[str, Any]) -> None:
    if document.get("recommendation_drift_schema_version") != DRIFT_SCHEMA_VERSION:
        raise ValueError("unsupported recommendation drift schema version")
    assessments = document.get("seed_assessments")
    if not isinstance(assessments, list):
        raise ValueError("seed_assessments must be a list")
    if document.get("summary", {}).get("observed_seed_count") != len(assessments):
        raise ValueError("observed_seed_count does not match assessments")
    for item in assessments:
        similarity = item.get("mean_jaccard_similarity")
        if similarity is not None and not 0 <= similarity <= 1:
            raise ValueError("drift similarity must be between 0 and 1")


def write_recommendation_communities(
    document: dict[str, Any], output_directory: Path
) -> tuple[Path, Path]:
    validate_recommendation_communities(document)
    output_directory.mkdir(parents=True, exist_ok=True)
    json_path = output_directory / "recommendation_communities.json"
    csv_path = output_directory / "recommendation_community_assignments.csv"
    json_path.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n")
    with csv_path.open("w", newline="") as output_file:
        fields = ["track_id", "title", "community_id", "undirected_degree"]
        writer = csv.DictWriter(output_file, fieldnames=fields)
        writer.writeheader()
        for item in document["assignments"]:
            writer.writerow({field: item[field] for field in fields})
    return json_path, csv_path


def write_recommendation_drift(document: dict[str, Any], output_directory: Path) -> Path:
    validate_recommendation_drift(document)
    output_directory.mkdir(parents=True, exist_ok=True)
    path = output_directory / "recommendation_drift.json"
    path.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n")
    return path
