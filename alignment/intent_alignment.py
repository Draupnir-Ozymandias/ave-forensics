from __future__ import annotations

import csv
import hashlib
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any

from clustering.protocol_families import validate_protocol_families


ALIGNMENT_SCHEMA_VERSION = "1.0.0"
METHOD_VERSION = "ave_claimed_intent_family_alignment_1.0.0"
MINIMUM_COHORT_SIZE = 3


def _digest(document: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(document, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _normalized_excess(observed: float, baseline: float) -> float:
    if observed >= baseline:
        denominator = 1.0 - baseline
    else:
        denominator = baseline
    if denominator <= 0:
        return 0.0
    return round((observed - baseline) / denominator, 6)


def _association_metrics(rows: list[dict[str, str]]) -> dict[str, float]:
    intents = sorted({row["stated_intent"] for row in rows})
    families = sorted({row["family_id"] for row in rows})
    total = len(rows)
    intent_counts = Counter(row["stated_intent"] for row in rows)
    family_counts = Counter(row["family_id"] for row in rows)
    joint_counts = Counter((row["stated_intent"], row["family_id"]) for row in rows)

    chi_square = 0.0
    mutual_information = 0.0
    for intent in intents:
        for family in families:
            observed = joint_counts[(intent, family)]
            expected = intent_counts[intent] * family_counts[family] / total
            if expected:
                chi_square += (observed - expected) ** 2 / expected
            if observed:
                probability = observed / total
                mutual_information += probability * math.log(
                    probability
                    / ((intent_counts[intent] / total) * (family_counts[family] / total))
                )

    intent_entropy = -sum(
        (count / total) * math.log(count / total) for count in intent_counts.values()
    )
    family_entropy = -sum(
        (count / total) * math.log(count / total) for count in family_counts.values()
    )
    entropy_denominator = math.sqrt(intent_entropy * family_entropy)
    cramers_denominator = total * min(len(intents) - 1, len(families) - 1)
    consistency = sum(
        max(joint_counts[(intent, family)] for family in families)
        for intent in intents
    ) / total
    majority_baseline = max(family_counts.values()) / total
    return {
        "cramers_v": round(math.sqrt(chi_square / cramers_denominator), 6)
        if cramers_denominator > 0
        else 0.0,
        "normalized_mutual_information": round(
            mutual_information / entropy_denominator, 6
        )
        if entropy_denominator > 0
        else 0.0,
        "within_intent_family_consistency": round(consistency, 6),
        "corpus_majority_family_baseline": round(majority_baseline, 6),
        "normalized_excess_consistency": _normalized_excess(
            consistency, majority_baseline
        ),
    }


def build_intent_alignment(
    index: dict[str, Any],
    clustering: dict[str, Any],
    *,
    minimum_cohort_size: int = MINIMUM_COHORT_SIZE,
) -> dict[str, Any]:
    if minimum_cohort_size < 2:
        raise ValueError("minimum_cohort_size must be at least 2")
    validate_protocol_families(clustering)
    index_digest = _digest(index)
    if clustering.get("source_index_sha256") != index_digest:
        raise ValueError("clustering artifact does not match the corpus index")

    records_by_digest: dict[str, list[dict[str, Any]]] = {}
    for record in index.get("recordings", []):
        digest = record.get("input_sha256")
        if digest and record.get("index_status") == "indexed":
            records_by_digest.setdefault(digest, []).append(record)

    family_labels = {
        family["family_id"]: family["semantic_label"]
        for family in clustering["families"]
    }
    rows = []
    excluded = []
    for assignment in clustering["assignments"]:
        candidate_records = records_by_digest.get(assignment.get("input_sha256"), [])
        if not candidate_records:
            excluded.append(
                {
                    "relative_path": assignment.get("relative_path"),
                    "reason": "missing_indexed_record",
                }
            )
            continue
        claimed_intents = sorted(
            {
                str(record.get("stated_intent") or "").strip()
                for record in candidate_records
                if str(record.get("stated_intent") or "").strip()
                and str(record.get("stated_intent") or "").strip().lower() != "unknown"
            }
        )
        if len(claimed_intents) > 1:
            excluded.append(
                {
                    "relative_path": assignment["relative_path"],
                    "aliases": sorted(
                        record["relative_path"] for record in candidate_records
                    ),
                    "reason": "conflicting_duplicate_intents",
                    "stated_intents": claimed_intents,
                }
            )
            continue
        record = sorted(candidate_records, key=lambda item: item["relative_path"])[0]
        intent = str(record.get("stated_intent") or "").strip()
        if not intent or intent.lower() == "unknown":
            excluded.append(
                {"relative_path": assignment["relative_path"], "reason": "missing_intent"}
            )
            continue
        rows.append(
            {
                "relative_path": assignment["relative_path"],
                "input_sha256": assignment["input_sha256"],
                "stated_intent": intent,
                "family_id": assignment["family_id"],
                "family_label": family_labels[assignment["family_id"]],
            }
        )

    if not rows:
        raise ValueError("no recordings have both a claimed intent and family assignment")
    intent_counts = Counter(row["stated_intent"] for row in rows)
    family_counts = Counter(row["family_id"] for row in rows)
    joint_counts = Counter((row["stated_intent"], row["family_id"]) for row in rows)
    total = len(rows)

    profiles = []
    for intent in sorted(intent_counts):
        cohort_size = intent_counts[intent]
        counts = {
            family_id: joint_counts[(intent, family_id)]
            for family_id in sorted(family_labels)
        }
        dominant_family_id = sorted(counts, key=lambda key: (-counts[key], key))[0]
        consistency = counts[dominant_family_id] / cohort_size
        baseline = family_counts[dominant_family_id] / total
        sufficient = cohort_size >= minimum_cohort_size
        profiles.append(
            {
                "stated_intent": intent,
                "cohort_size": cohort_size,
                "assessment_status": "scored" if sufficient else "insufficient_cohort",
                "dominant_family_id": dominant_family_id if sufficient else None,
                "dominant_family_label": family_labels[dominant_family_id]
                if sufficient
                else None,
                "family_consistency": round(consistency, 6) if sufficient else None,
                "corpus_family_baseline": round(baseline, 6) if sufficient else None,
                "association_lift": round(consistency / baseline, 6)
                if sufficient and baseline
                else None,
                "normalized_excess_consistency": _normalized_excess(consistency, baseline)
                if sufficient
                else None,
                "family_distribution": [
                    {
                        "family_id": family_id,
                        "family_label": family_labels[family_id],
                        "count": counts[family_id],
                        "proportion": round(counts[family_id] / cohort_size, 6),
                    }
                    for family_id in sorted(family_labels)
                ],
            }
        )

    assessments = []
    for row in sorted(rows, key=lambda item: item["relative_path"]):
        cohort_size = intent_counts[row["stated_intent"]]
        sufficient = cohort_size >= minimum_cohort_size
        peer_count = cohort_size - 1
        same_family_peer_count = (
            joint_counts[(row["stated_intent"], row["family_id"])] - 1
        )
        corpus_peer_count = total - 1
        same_family_corpus_peers = family_counts[row["family_id"]] - 1
        peer_support = same_family_peer_count / peer_count if peer_count else 0.0
        baseline_support = (
            same_family_corpus_peers / corpus_peer_count if corpus_peer_count else 0.0
        )
        assessments.append(
            {
                **row,
                "cohort_size": cohort_size,
                "assessment_status": "scored" if sufficient else "insufficient_cohort",
                "same_intent_peer_support": round(peer_support, 6) if sufficient else None,
                "corpus_peer_baseline": round(baseline_support, 6) if sufficient else None,
                "association_lift": round(peer_support / baseline_support, 6)
                if sufficient and baseline_support
                else None,
                "normalized_alignment_score": _normalized_excess(
                    peer_support, baseline_support
                )
                if sufficient
                else None,
            }
        )

    document = {
        "alignment_schema_version": ALIGNMENT_SCHEMA_VERSION,
        "source_index_sha256": index_digest,
        "source_clustering_sha256": _digest(clustering),
        "method": {
            "name": METHOD_VERSION,
            "claimed_dimension": "stated_intent",
            "observed_dimension": "protocol_family_id",
            "minimum_cohort_size": minimum_cohort_size,
            "recording_estimator": "leave-one-out peer support versus corpus family baseline",
            "context_excluded_from_family_discovery": True,
        },
        "interpretation": {
            "measures": "association and within-label consistency",
            "does_not_measure": [
                "therapeutic efficacy",
                "causal effect",
                "subjective outcome",
                "clinical validity",
            ],
        },
        "eligible_recording_count": total,
        "scored_recording_count": sum(
            item["assessment_status"] == "scored" for item in assessments
        ),
        "excluded_recordings": sorted(excluded, key=lambda item: item["relative_path"]),
        "global_association": _association_metrics(rows),
        "intent_profiles": profiles,
        "recording_assessments": assessments,
    }
    validate_intent_alignment(document)
    return document


def validate_intent_alignment(document: dict[str, Any]) -> None:
    if document.get("alignment_schema_version") != ALIGNMENT_SCHEMA_VERSION:
        raise ValueError("unsupported alignment_schema_version")
    if document.get("interpretation", {}).get("does_not_measure") is None:
        raise ValueError("interpretation limitations are required")
    assessments = document.get("recording_assessments")
    profiles = document.get("intent_profiles")
    if not isinstance(assessments, list) or not isinstance(profiles, list):
        raise ValueError("alignment profiles and assessments must be lists")
    if document.get("eligible_recording_count") != len(assessments):
        raise ValueError("eligible_recording_count does not match assessments")
    profile_intents = {profile.get("stated_intent") for profile in profiles}
    if any(item.get("stated_intent") not in profile_intents for item in assessments):
        raise ValueError("assessment references an unknown intent profile")
    for item in assessments:
        score = item.get("normalized_alignment_score")
        if score is not None and not -1.0 <= score <= 1.0:
            raise ValueError("normalized_alignment_score must be between -1 and 1")


CSV_FIELDS = [
    "relative_path",
    "input_sha256",
    "stated_intent",
    "family_id",
    "family_label",
    "cohort_size",
    "assessment_status",
    "same_intent_peer_support",
    "corpus_peer_baseline",
    "association_lift",
    "normalized_alignment_score",
]


def write_intent_alignment(
    document: dict[str, Any], output_directory: Path
) -> tuple[Path, Path]:
    validate_intent_alignment(document)
    output_directory.mkdir(parents=True, exist_ok=True)
    json_path = output_directory / "intent_alignment.json"
    csv_path = output_directory / "intent_alignment.csv"
    json_path.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n")
    with csv_path.open("w", newline="") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(document["recording_assessments"])
    return json_path, csv_path
