from __future__ import annotations

import csv
import hashlib
import json
import math
import re
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np
from scipy.cluster.hierarchy import fcluster, linkage
from scipy.spatial.distance import cdist


CLUSTERING_SCHEMA_VERSION = "1.0.0"
METHOD_VERSION = "ave_hierarchical_protocol_families_1.0.0"
FAMILY_ID_PATTERN = re.compile(r"^ave_family_[0-9]{2}$")

NUMERIC_FEATURES = (
    "carrier_center_hz",
    "carrier_difference_hz",
    "carrier_confidence",
    "envelope_modulation_hz",
    "envelope_relative_power",
    "envelope_modulation_depth",
    "shared_modulation_hz",
    "shared_window_coverage",
    "phase_window_coverage",
    "phase_median_difference_hz",
    "hypothesis_difference_hz",
)
LOG_FEATURES = {
    "carrier_center_hz",
    "carrier_difference_hz",
    "envelope_modulation_hz",
    "shared_modulation_hz",
    "phase_median_difference_hz",
    "hypothesis_difference_hz",
}
CATEGORICAL_FEATURES = (
    "carrier_pair_type",
    "modulation_classification",
    "phase_behavior",
)
EXCLUDED_CONTEXT_FIELDS = (
    "source",
    "category",
    "stated_intent",
    "notes",
    "filename",
    "vendor_claims",
    "transcript",
)


def _source_index_digest(index: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(index, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _measurements(record: dict[str, Any]) -> dict[str, Any]:
    summary = record.get("evidence_summary") or {}
    carrier = summary.get("strongest_carrier_pair") or {}
    envelope = summary.get("dominant_envelope") or {}
    modulation = summary.get("modulation_reconstruction") or {}
    phase = summary.get("phase_relationship") or {}
    hypothesis = summary.get("top_hypothesis") or {}
    left = carrier.get("left_hz")
    right = carrier.get("right_hz")
    center = (float(left) + float(right)) / 2 if left is not None and right is not None else None
    return {
        "relative_path": record["relative_path"],
        "input_sha256": record.get("input_sha256"),
        "source": record.get("source") or "unknown",
        "category": record.get("category") or "unknown",
        "stated_intent": record.get("stated_intent") or "unknown",
        "evidence_count": summary.get("evidence_count"),
        "carrier_center_hz": center,
        "carrier_difference_hz": carrier.get("difference_hz"),
        "carrier_confidence": carrier.get("confidence"),
        "carrier_pair_type": carrier.get("pair_type"),
        "envelope_modulation_hz": envelope.get("modulation_hz"),
        "envelope_relative_power": envelope.get("relative_power"),
        "envelope_modulation_depth": envelope.get("modulation_depth"),
        "shared_modulation_hz": modulation.get("primary_shared_modulation_hz"),
        "shared_window_coverage": modulation.get("shared_window_coverage"),
        "modulation_classification": modulation.get("classification"),
        "phase_behavior": phase.get("behavior"),
        "phase_window_coverage": phase.get("window_coverage"),
        "phase_median_difference_hz": phase.get("median_difference_hz"),
        "hypothesis_difference_hz": hypothesis.get("difference_hz"),
        "hypothesis_ranking_score": hypothesis.get("ranking_score"),
    }


def _unique_analyzed_records(index: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    excluded = []
    for record in index.get("recordings", []):
        if record.get("index_status") != "indexed" or not record.get("evidence_summary"):
            excluded.append(
                {
                    "relative_path": record.get("relative_path"),
                    "input_sha256": record.get("input_sha256"),
                    "reason": record.get("index_status") or "missing_evidence",
                }
            )
            continue
        identity = record.get("input_sha256") or f"path:{record['relative_path']}"
        groups.setdefault(identity, []).append(record)

    selected = []
    for identity in sorted(groups):
        aliases = sorted(groups[identity], key=lambda item: item["relative_path"])
        projected = _measurements(aliases[0])
        projected["aliases"] = [item["relative_path"] for item in aliases]
        selected.append(projected)
        for duplicate in aliases[1:]:
            excluded.append(
                {
                    "relative_path": duplicate["relative_path"],
                    "input_sha256": duplicate.get("input_sha256"),
                    "reason": "duplicate_alias",
                }
            )
    selected.sort(key=lambda item: item["relative_path"])
    excluded.sort(key=lambda item: item["relative_path"] or "")
    return selected, excluded


def _feature_matrix(records: list[dict[str, Any]]) -> tuple[np.ndarray, list[str], dict[str, Any]]:
    columns: list[np.ndarray] = []
    names = []
    normalization: dict[str, Any] = {}
    for feature in NUMERIC_FEATURES:
        raw = np.array(
            [float(record[feature]) if record.get(feature) is not None else np.nan for record in records],
            dtype=float,
        )
        transformed = raw.copy()
        if feature in LOG_FEATURES:
            transformed = np.log1p(np.maximum(transformed, 0.0))
        missing = np.isnan(transformed)
        if missing.all():
            median = 0.0
            scale = 1.0
        else:
            median = float(np.nanmedian(transformed))
            q1, q3 = np.nanpercentile(transformed, [25, 75])
            scale = float(q3 - q1)
            if not math.isfinite(scale) or scale < 1e-9:
                scale = float(np.nanstd(transformed))
            if not math.isfinite(scale) or scale < 1e-9:
                scale = 1.0
        standardized = np.clip(
            (np.nan_to_num(transformed, nan=median) - median) / scale,
            -5.0,
            5.0,
        )
        columns.append(standardized)
        names.append(feature)
        normalization[feature] = {
            "transform": "log1p_nonnegative" if feature in LOG_FEATURES else "identity",
            "imputation": "median",
            "median": round(median, 8),
            "scale": "interquartile_range",
            "scale_value": round(scale, 8),
            "clip": [-5.0, 5.0],
        }
        if missing.any():
            columns.append(missing.astype(float))
            names.append(f"{feature}__missing")

    for feature in CATEGORICAL_FEATURES:
        levels = sorted(str(record.get(feature) or "missing") for record in records)
        levels = sorted(set(levels))
        for level in levels:
            columns.append(
                np.array(
                    [float(str(record.get(feature) or "missing") == level) for record in records]
                )
            )
            names.append(f"{feature}={level}")
        normalization[feature] = {"transform": "one_hot", "levels": levels}
    return np.column_stack(columns), names, normalization


def _silhouette_samples(matrix: np.ndarray, labels: np.ndarray) -> np.ndarray:
    distances = cdist(matrix, matrix, metric="euclidean")
    unique_labels = sorted(set(int(label) for label in labels))
    scores = np.zeros(len(labels), dtype=float)
    for index, label in enumerate(labels):
        own = np.where(labels == label)[0]
        if len(own) <= 1:
            scores[index] = 0.0
            continue
        own_without_self = own[own != index]
        within = float(np.mean(distances[index, own_without_self]))
        nearest = min(
            float(np.mean(distances[index, np.where(labels == other)[0]]))
            for other in unique_labels
            if other != label
        )
        denominator = max(within, nearest)
        scores[index] = (nearest - within) / denominator if denominator else 0.0
    return scores


def _select_partition(matrix: np.ndarray, *, maximum_families: int) -> tuple[np.ndarray, list[dict[str, Any]]]:
    count = len(matrix)
    if count < 4:
        return np.ones(count, dtype=int), []
    hierarchy = linkage(matrix, method="ward", metric="euclidean")
    minimum_size = max(2, math.ceil(count * 0.07))
    candidates = []
    partitions: dict[int, np.ndarray] = {}
    for family_count in range(2, min(maximum_families, count - 1) + 1):
        labels = fcluster(hierarchy, family_count, criterion="maxclust").astype(int)
        sizes = sorted(Counter(int(label) for label in labels).values())
        score = float(np.mean(_silhouette_samples(matrix, labels)))
        valid = min(sizes) >= minimum_size
        candidates.append(
            {
                "family_count": family_count,
                "silhouette_score": round(score, 6),
                "minimum_family_size": min(sizes),
                "accepted": valid,
            }
        )
        partitions[family_count] = labels
    valid_candidates = [item for item in candidates if item["accepted"]]
    pool = valid_candidates or candidates
    selected = max(pool, key=lambda item: (item["silhouette_score"], -item["family_count"]))
    return partitions[selected["family_count"]], candidates


def _dominant(records: list[dict[str, Any]], field: str) -> str:
    counts = Counter(str(record.get(field) or "missing") for record in records)
    return sorted(counts.items(), key=lambda item: (-item[1], item[0]))[0][0]


def _median(records: list[dict[str, Any]], field: str) -> float | None:
    values = [float(record[field]) for record in records if record.get(field) is not None]
    return round(float(np.median(values)), 6) if values else None


def _descriptor(records: list[dict[str, Any]]) -> str:
    pair = _dominant(records, "carrier_pair_type").replace("_", "-")
    phase = _dominant(records, "phase_behavior").replace("_", "-")
    center = _median(records, "carrier_center_hz")
    shared = _median(records, "shared_modulation_hz")
    carrier = f"{center:.1f} Hz {pair}" if center is not None else pair
    modulation = f"{shared:.2f} Hz shared modulation" if shared is not None else "no shared-modulation estimate"
    return f"{carrier} · {modulation} · {phase}"


def build_protocol_families(
    index: dict[str, Any],
    *,
    maximum_families: int = 8,
) -> dict[str, Any]:
    if not isinstance(index.get("recordings"), list):
        raise ValueError("corpus index must contain a recordings list")
    if maximum_families < 2:
        raise ValueError("maximum_families must be at least 2")
    records, excluded = _unique_analyzed_records(index)
    if not records:
        raise ValueError("no unique analyzed recordings are available for clustering")
    matrix, feature_names, normalization = _feature_matrix(records)
    raw_labels, candidates = _select_partition(
        matrix,
        maximum_families=maximum_families,
    )
    silhouettes = (
        _silhouette_samples(matrix, raw_labels)
        if len(set(raw_labels)) > 1
        else np.zeros(len(records))
    )

    raw_groups = []
    for raw_label in sorted(set(int(label) for label in raw_labels)):
        indices = np.where(raw_labels == raw_label)[0]
        members = [records[index] for index in indices]
        raw_groups.append(
            {
                "raw_label": raw_label,
                "indices": indices,
                "records": members,
                "sort_key": (
                    _dominant(members, "carrier_pair_type"),
                    _median(members, "carrier_center_hz") or -1,
                    _median(members, "carrier_difference_hz") or -1,
                    _median(members, "shared_modulation_hz") or -1,
                    _dominant(members, "phase_behavior"),
                ),
            }
        )
    raw_groups.sort(key=lambda item: item["sort_key"])

    families = []
    assignments = []
    for family_number, group in enumerate(raw_groups, start=1):
        family_id = f"ave_family_{family_number:02d}"
        indices = group["indices"]
        members = group["records"]
        centroid = np.mean(matrix[indices], axis=0)
        member_distances = np.linalg.norm(matrix[indices] - centroid, axis=1)
        family_members = []
        for row_index, distance in zip(indices, member_distances):
            record = records[int(row_index)]
            assignment = {
                "relative_path": record["relative_path"],
                "input_sha256": record["input_sha256"],
                "aliases": record["aliases"],
                "family_id": family_id,
                "silhouette_score": round(float(silhouettes[int(row_index)]), 6),
                "distance_to_centroid": round(float(distance), 6),
            }
            assignments.append(assignment)
            family_members.append(assignment)
        family_members.sort(key=lambda item: item["relative_path"])
        numeric_profile = {
            feature: _median(members, feature) for feature in NUMERIC_FEATURES
        }
        categorical_profile = {
            feature: _dominant(members, feature) for feature in CATEGORICAL_FEATURES
        }
        context_distribution = {
            field: dict(sorted(Counter(record[field] for record in members).items()))
            for field in ("source", "category", "stated_intent")
        }
        families.append(
            {
                "family_id": family_id,
                "descriptor": _descriptor(members),
                "member_count": len(members),
                "mean_silhouette_score": round(float(np.mean(silhouettes[indices])), 6),
                "numeric_medians": numeric_profile,
                "dominant_categorical_signatures": categorical_profile,
                "context_distribution_not_used_for_clustering": context_distribution,
                "members": family_members,
            }
        )
    assignments.sort(key=lambda item: item["relative_path"])
    overall_silhouette = float(np.mean(silhouettes)) if len(families) > 1 else 0.0
    document = {
        "clustering_schema_version": CLUSTERING_SCHEMA_VERSION,
        "source_index_schema_version": index.get("index_schema_version"),
        "source_index_sha256": _source_index_digest(index),
        "method": {
            "name": METHOD_VERSION,
            "algorithm": "Ward hierarchical agglomerative clustering",
            "distance_metric": "Euclidean distance on robust-standardized evidence features",
            "selection_metric": "mean silhouette score",
            "maximum_families": maximum_families,
            "selected_family_count": len(families),
            "overall_silhouette_score": round(overall_silhouette, 6),
            "candidate_partitions": candidates,
        },
        "feature_specification": {
            "numeric_features": list(NUMERIC_FEATURES),
            "categorical_features": list(CATEGORICAL_FEATURES),
            "excluded_measurements": {
                "hypothesis_ranking_score": "legacy and current evidence documents use different ranking sources",
                "hypothesis_confidence": "not available with equivalent semantics across the legacy corpus",
            },
            "expanded_feature_columns": feature_names,
            "normalization": normalization,
            "explicitly_excluded_context": list(EXCLUDED_CONTEXT_FIELDS),
        },
        "clustered_unique_input_count": len(records),
        "excluded_recordings": excluded,
        "families": families,
        "assignments": assignments,
    }
    validate_protocol_families(document)
    return document


def validate_protocol_families(document: dict[str, Any]) -> None:
    if document.get("clustering_schema_version") != CLUSTERING_SCHEMA_VERSION:
        raise ValueError("unsupported clustering_schema_version")
    families = document.get("families")
    assignments = document.get("assignments")
    if not isinstance(families, list) or not families:
        raise ValueError("families must be a non-empty list")
    if not isinstance(assignments, list):
        raise ValueError("assignments must be a list")
    family_ids = [family.get("family_id") for family in families]
    if len(family_ids) != len(set(family_ids)):
        raise ValueError("family_id values must be unique")
    if any(not isinstance(value, str) or not FAMILY_ID_PATTERN.match(value) for value in family_ids):
        raise ValueError("invalid family_id")
    assignment_paths = [item.get("relative_path") for item in assignments]
    if len(assignment_paths) != len(set(assignment_paths)):
        raise ValueError("each canonical recording may have only one assignment")
    if any(item.get("family_id") not in family_ids for item in assignments):
        raise ValueError("assignment references an unknown family")
    if document.get("clustered_unique_input_count") != len(assignments):
        raise ValueError("clustered_unique_input_count does not match assignments")
    member_total = sum(family.get("member_count", -1) for family in families)
    if member_total != len(assignments):
        raise ValueError("family member counts do not match assignments")


CSV_FIELDS = [
    "relative_path",
    "input_sha256",
    "aliases",
    "family_id",
    "family_descriptor",
    "silhouette_score",
    "distance_to_centroid",
]


def write_protocol_families(
    document: dict[str, Any],
    output_directory: Path,
) -> tuple[Path, Path]:
    validate_protocol_families(document)
    output_directory.mkdir(parents=True, exist_ok=True)
    json_path = output_directory / "protocol_families.json"
    csv_path = output_directory / "protocol_family_assignments.csv"
    json_path.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n")
    descriptors = {
        family["family_id"]: family["descriptor"] for family in document["families"]
    }
    with csv_path.open("w", newline="") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for assignment in document["assignments"]:
            writer.writerow(
                {
                    **assignment,
                    "aliases": " | ".join(assignment["aliases"]),
                    "family_descriptor": descriptors[assignment["family_id"]],
                }
            )
    return json_path, csv_path
