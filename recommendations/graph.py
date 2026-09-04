from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.hashing import sha256_file
from provider.brainfm import parse_capture


CAPTURE_SCHEMA_VERSION = "1.0.0"
GRAPH_SCHEMA_VERSION = "1.0.0"
EXTRACTOR_VERSION = "ave_brainfm_recommendations_1.1.0"
OBSERVATION_ID_PATTERN = re.compile(r"^ave_recommendation_observation_[0-9a-f]{16}$")


def _document_sha256(document: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(document, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _walk(value: Any):
    if isinstance(value, dict):
        yield value
        for nested in value.values():
            yield from _walk(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from _walk(nested)


def _display_value(value: Any) -> str | None:
    if not isinstance(value, dict):
        return None
    display = value.get("displayValue")
    return display if isinstance(display, str) and display else None


def _safe_track_values(track: dict[str, Any]) -> dict[str, set[Any]]:
    values: dict[str, set[Any]] = defaultdict(set)
    title = track.get("name")
    if isinstance(title, str) and title:
        values["titles"].add(title)
    mental_state = _display_value(track.get("mentalState")) or _display_value(
        track.get("dynamicMentalState")
    )
    activity = _display_value(track.get("mobileActivity"))
    if mental_state:
        values["mental_states"].add(mental_state)
    if activity:
        values["activities"].add(activity)
    for source_field, output_field in (
        ("beatsPerMinute", "beats_per_minute_values"),
        ("brightnessLevel", "brightness_levels"),
        ("complexityLevel", "complexity_levels"),
    ):
        value = track.get(source_field)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            values[output_field].add(value)
    release_status = track.get("releaseStatus")
    if isinstance(release_status, str) and release_status:
        values["release_statuses"].add(release_status)
    variations = track.get("variations")
    if isinstance(variations, list):
        for variation in variations:
            if not isinstance(variation, dict):
                continue
            style = variation.get("style")
            if isinstance(style, str) and style:
                values["styles"].add(style)
            for source_field, output_field in (
                ("neuralEffectLevel", "neural_effect_levels"),
                ("lengthInSeconds", "declared_duration_seconds_values"),
            ):
                value = variation.get(source_field)
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    values[output_field].add(value)
    tags = track.get("tags")
    if isinstance(tags, list):
        for tag in tags:
            if not isinstance(tag, dict):
                continue
            tag_type = tag.get("type")
            tag_value = tag.get("value")
            if isinstance(tag_type, str) and isinstance(tag_value, str):
                values[f"tags:{tag_type}"].add(tag_value)
    return values


def _merge_track(
    nodes: dict[str, dict[str, set[Any]]], track: dict[str, Any]
) -> str | None:
    track_id = track.get("id")
    if not isinstance(track_id, str) or not track_id:
        return None
    target = nodes.setdefault(track_id, defaultdict(set))
    for field, values in _safe_track_values(track).items():
        target[field].update(values)
    return track_id


def _project_nodes(nodes: dict[str, dict[str, set[Any]]]) -> list[dict[str, Any]]:
    projected = []
    for track_id in sorted(nodes):
        values = nodes[track_id]
        tags = {
            key.split(":", 1)[1]: sorted(items)
            for key, items in sorted(values.items())
            if key.startswith("tags:")
        }
        projected.append(
            {
                "track_id": track_id,
                "observed_titles": sorted(values.get("titles", set())),
                "mental_states": sorted(values.get("mental_states", set())),
                "activities": sorted(values.get("activities", set())),
                "styles": sorted(values.get("styles", set())),
                "beats_per_minute_values": sorted(
                    values.get("beats_per_minute_values", set())
                ),
                "brightness_levels": sorted(values.get("brightness_levels", set())),
                "complexity_levels": sorted(values.get("complexity_levels", set())),
                "neural_effect_levels": sorted(
                    values.get("neural_effect_levels", set())
                ),
                "declared_duration_seconds_values": sorted(
                    values.get("declared_duration_seconds_values", set())
                ),
                "release_statuses": sorted(values.get("release_statuses", set())),
                "tags": tags,
            }
        )
    return projected


def _reject_sensitive_output(value: Any, path: str = "root") -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            if re.search(
                r"(?:^|_)(?:token|cookie|authorization|password|secret|session_token)(?:$|_)",
                key,
                re.I,
            ):
                raise ValueError(f"forbidden sensitive field: {path}.{key}")
            _reject_sensitive_output(nested, f"{path}.{key}")
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            _reject_sensitive_output(nested, f"{path}[{index}]")
    elif isinstance(value, str):
        if re.search(r"https?://|[?&](?:token|signature|auth)=", value, re.I):
            raise ValueError(f"forbidden URL or credential at {path}")


def extract_recommendation_capture(
    capture_path: Path,
    *,
    visible_category: str | None = None,
    visible_intent: str | None = None,
    seed_track_id: str | None = None,
    captured_at: str | None = None,
    context_method: str = "not_recorded",
) -> dict[str, Any]:
    documents, capture_format = parse_capture(capture_path)
    nodes: dict[str, dict[str, set[Any]]] = {}
    list_observations: Counter[tuple[str, tuple[str, ...]]] = Counter()
    list_documents: dict[tuple[str, tuple[str, ...]], set[int]] = defaultdict(set)
    edge_occurrences: Counter[tuple[str, str]] = Counter()
    edge_ranks: dict[tuple[str, str], set[int]] = defaultdict(set)
    edge_documents: dict[tuple[str, str], set[int]] = defaultdict(set)
    seed_occurrences: Counter[str] = Counter()

    for document_index, document in enumerate(documents, start=1):
        for track in _walk(document):
            similar = track.get("similarTracks")
            if not isinstance(similar, list):
                continue
            source_id = _merge_track(nodes, track)
            if source_id is None:
                continue
            recommended_ids = []
            for rank, recommended in enumerate(similar, start=1):
                if not isinstance(recommended, dict):
                    continue
                target_id = _merge_track(nodes, recommended)
                if target_id is None:
                    continue
                recommended_ids.append(target_id)
                edge = (source_id, target_id)
                edge_occurrences[edge] += 1
                edge_ranks[edge].add(rank)
                edge_documents[edge].add(document_index)
            signature = (source_id, tuple(recommended_ids))
            list_observations[signature] += 1
            list_documents[signature].add(document_index)
            seed_occurrences[source_id] += 1

    capture_hash = sha256_file(capture_path)
    context = {
        "visible_category": visible_category,
        "visible_intent": visible_intent,
        "seed_track_id": seed_track_id,
        "context_method": context_method,
    }
    source_capture = {
        "filename": capture_path.name,
        "sha256": capture_hash,
        "size_bytes": capture_path.stat().st_size,
        "format": capture_format,
        "json_document_count": len(documents),
        "captured_at": captured_at,
    }
    observations = [
        {
            "seed_track_id": source_id,
            "recommended_track_ids": list(recommended_ids),
            "recommendation_count": len(recommended_ids),
            "occurrence_count": count,
            "document_indices": sorted(list_documents[(source_id, recommended_ids)]),
        }
        for (source_id, recommended_ids), count in sorted(list_observations.items())
    ]
    edges = [
        {
            "seed_track_id": source_id,
            "recommended_track_id": target_id,
            "observed_ranks": sorted(edge_ranks[(source_id, target_id)]),
            "occurrence_count": count,
            "document_indices": sorted(edge_documents[(source_id, target_id)]),
        }
        for (source_id, target_id), count in sorted(edge_occurrences.items())
    ]
    variant_counts = Counter(item["seed_track_id"] for item in observations)
    core = {
        "recommendation_capture_schema_version": CAPTURE_SCHEMA_VERSION,
        "provider": "brain.fm",
        "source_capture": source_capture,
        "observation_context": context,
        "summary": {
            "observed_node_count": len(nodes),
            "observed_seed_count": len(seed_occurrences),
            "seed_with_nonempty_list_count": len(
                {item["seed_track_id"] for item in observations if item["recommendation_count"]}
            ),
            "seed_with_only_empty_lists_count": len(
                {
                    item["seed_track_id"]
                    for item in observations
                    if not item["recommendation_count"]
                    and not any(
                        other["seed_track_id"] == item["seed_track_id"]
                        and other["recommendation_count"]
                        for other in observations
                    )
                }
            ),
            "unique_edge_count": len(edges),
            "seed_with_multiple_list_variants_count": sum(
                count > 1 for count in variant_counts.values()
            ),
        },
        "nodes": _project_nodes(nodes),
        "list_observations": observations,
        "edges": edges,
        "extraction_provenance": {
            "generator": "recommendations.graph",
            "generator_version": EXTRACTOR_VERSION,
            "sensitive_data_policy": "omit_urls_tokens_cookies_and_session_data",
        },
    }
    observation_id = f"ave_recommendation_observation_{_document_sha256(core)[:16]}"
    document = {
        **core,
        "observation_id": observation_id,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
    }
    validate_recommendation_capture(document)
    return document


def validate_recommendation_capture(document: dict[str, Any]) -> None:
    if document.get("recommendation_capture_schema_version") != CAPTURE_SCHEMA_VERSION:
        raise ValueError("unsupported recommendation capture schema version")
    observation_id = document.get("observation_id")
    if not isinstance(observation_id, str) or not OBSERVATION_ID_PATTERN.match(
        observation_id
    ):
        raise ValueError("invalid observation_id")
    core = {
        key: value
        for key, value in document.items()
        if key not in {"observation_id", "generated_at"}
    }
    expected = f"ave_recommendation_observation_{_document_sha256(core)[:16]}"
    if observation_id != expected:
        raise ValueError("observation_id does not match content")
    node_ids = {node.get("track_id") for node in document.get("nodes", [])}
    if None in node_ids or len(node_ids) != len(document.get("nodes", [])):
        raise ValueError("recommendation node identifiers must be unique")
    for edge in document.get("edges", []):
        if edge.get("seed_track_id") not in node_ids or edge.get(
            "recommended_track_id"
        ) not in node_ids:
            raise ValueError("recommendation edge references an unknown node")
    _reject_sensitive_output(document)


def aggregate_recommendation_captures(
    captures: list[dict[str, Any]],
) -> dict[str, Any]:
    unique = {}
    for capture in captures:
        validate_recommendation_capture(capture)
        unique[capture["observation_id"]] = capture
    ordered = [unique[key] for key in sorted(unique)]
    if not ordered:
        raise ValueError("at least one recommendation capture is required")

    nodes: dict[str, dict[str, set[Any]]] = {}
    edge_observations: dict[tuple[str, str], set[str]] = defaultdict(set)
    edge_ranks: dict[tuple[str, str], set[int]] = defaultdict(set)
    edge_occurrences: Counter[tuple[str, str]] = Counter()
    contexts: dict[tuple[str, str], set[tuple[str | None, str | None]]] = defaultdict(set)
    seed_variants: dict[str, set[tuple[str, ...]]] = defaultdict(set)
    for capture in ordered:
        observation_id = capture["observation_id"]
        for node in capture["nodes"]:
            target = nodes.setdefault(node["track_id"], defaultdict(set))
            for source_field, target_field in (
                ("observed_titles", "titles"),
                ("mental_states", "mental_states"),
                ("activities", "activities"),
                ("styles", "styles"),
                ("beats_per_minute_values", "beats_per_minute_values"),
                ("brightness_levels", "brightness_levels"),
                ("complexity_levels", "complexity_levels"),
                ("neural_effect_levels", "neural_effect_levels"),
                ("declared_duration_seconds_values", "declared_duration_seconds_values"),
                ("release_statuses", "release_statuses"),
            ):
                target[target_field].update(node.get(source_field, []))
            for tag_type, values in node["tags"].items():
                target[f"tags:{tag_type}"].update(values)
        for observation in capture["list_observations"]:
            seed_variants[observation["seed_track_id"]].add(
                tuple(observation["recommended_track_ids"])
            )
        context = capture["observation_context"]
        for edge in capture["edges"]:
            key = (edge["seed_track_id"], edge["recommended_track_id"])
            edge_observations[key].add(observation_id)
            edge_ranks[key].update(edge["observed_ranks"])
            edge_occurrences[key] += edge["occurrence_count"]
            contexts[key].add(
                (context.get("visible_category"), context.get("visible_intent"))
            )

    edges = [
        {
            "seed_track_id": source_id,
            "recommended_track_id": target_id,
            "observation_ids": sorted(edge_observations[(source_id, target_id)]),
            "observation_count": len(edge_observations[(source_id, target_id)]),
            "occurrence_count": edge_occurrences[(source_id, target_id)],
            "observed_ranks": sorted(edge_ranks[(source_id, target_id)]),
            "observed_contexts": [
                {"visible_category": category, "visible_intent": intent}
                for category, intent in sorted(
                    contexts[(source_id, target_id)],
                    key=lambda item: (item[0] or "", item[1] or ""),
                )
            ],
        }
        for source_id, target_id in sorted(edge_occurrences)
    ]
    graph = {
        "recommendation_graph_schema_version": GRAPH_SCHEMA_VERSION,
        "provider": "brain.fm",
        "source_observations": [
            {
                "observation_id": capture["observation_id"],
                "source_capture_sha256": capture["source_capture"]["sha256"],
                "observation_context": capture["observation_context"],
            }
            for capture in ordered
        ],
        "summary": {
            "observation_count": len(ordered),
            "node_count": len(nodes),
            "seed_count": len(seed_variants),
            "edge_count": len(edges),
            "seed_with_multiple_list_variants_count": sum(
                len(variants) > 1 for variants in seed_variants.values()
            ),
        },
        "nodes": _project_nodes(nodes),
        "edges": edges,
        "seed_list_variants": [
            {
                "seed_track_id": seed_id,
                "variant_count": len(variants),
                "recommended_track_id_lists": [list(items) for items in sorted(variants)],
            }
            for seed_id, variants in sorted(seed_variants.items())
        ],
        "interpretation": {
            "edge_meaning": "provider-declared similarTracks relationship observed in a captured response",
            "does_not_establish": [
                "playback order",
                "recommendation causality",
                "personalization mechanism",
                "therapeutic similarity",
            ],
        },
    }
    validate_recommendation_graph(graph)
    return graph


def validate_recommendation_graph(document: dict[str, Any]) -> None:
    if document.get("recommendation_graph_schema_version") != GRAPH_SCHEMA_VERSION:
        raise ValueError("unsupported recommendation graph schema version")
    nodes = document.get("nodes")
    edges = document.get("edges")
    if not isinstance(nodes, list) or not isinstance(edges, list):
        raise ValueError("recommendation graph nodes and edges must be lists")
    node_ids = {node.get("track_id") for node in nodes}
    if None in node_ids or len(node_ids) != len(nodes):
        raise ValueError("recommendation graph node identifiers must be unique")
    edge_keys = set()
    for edge in edges:
        key = (edge.get("seed_track_id"), edge.get("recommended_track_id"))
        if key in edge_keys:
            raise ValueError("recommendation graph edges must be unique")
        edge_keys.add(key)
        if key[0] not in node_ids or key[1] not in node_ids:
            raise ValueError("recommendation graph edge references an unknown node")


def write_recommendation_capture(
    document: dict[str, Any], output_directory: Path
) -> Path:
    validate_recommendation_capture(document)
    output_directory.mkdir(parents=True, exist_ok=True)
    stem = re.sub(r"[^a-z0-9]+", "-", document["source_capture"]["filename"].lower()).strip("-")
    path = output_directory / f"{stem}-{document['observation_id'][-8:]}.recommendation.json"
    if path.exists():
        existing = json.loads(path.read_text())
        validate_recommendation_capture(existing)
        return path
    path.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n")
    return path


def write_recommendation_graph(document: dict[str, Any], path: Path) -> Path:
    validate_recommendation_graph(document)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n")
    return path
