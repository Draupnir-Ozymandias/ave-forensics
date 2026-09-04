from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from alignment.intent_alignment import validate_intent_alignment
from clustering.protocol_families import validate_protocol_families
from longitudinal.schema import (
    COMPARISON_SCHEMA_VERSION,
    SNAPSHOT_SCHEMA_VERSION,
    document_sha256,
    validate_comparison,
    validate_snapshot,
)


METHOD_VERSION = "ave_longitudinal_corpus_1.0.0"


def _provider_context(record: dict[str, Any]) -> dict[str, Any]:
    provider = record.get("provider_metadata") or {}
    taxonomy = provider.get("taxonomy") or {}
    return {
        "relative_path": record["relative_path"],
        "category": record.get("category") or "unknown",
        "stated_intent": record.get("stated_intent") or "unknown",
        "label_source": record.get("label_source") or "unknown",
        "provider_mental_state": taxonomy.get("mental_state"),
        "provider_activity": taxonomy.get("activity"),
        "provider_style": taxonomy.get("style"),
    }


def build_corpus_snapshot(
    index: dict[str, Any],
    clustering: dict[str, Any],
    alignment: dict[str, Any],
    *,
    captured_at: str | None = None,
) -> dict[str, Any]:
    validate_protocol_families(clustering)
    validate_intent_alignment(alignment)
    index_sha256 = document_sha256(index)
    clustering_sha256 = document_sha256(clustering)
    if clustering.get("source_index_sha256") != index_sha256:
        raise ValueError("clustering artifact does not match the corpus index")
    if (
        alignment.get("source_index_sha256") != index_sha256
        or alignment.get("source_clustering_sha256") != clustering_sha256
    ):
        raise ValueError("alignment artifact does not match index and clustering inputs")

    groups: dict[str, list[dict[str, Any]]] = {}
    without_digest = []
    for record in index.get("recordings", []):
        digest = record.get("input_sha256")
        if digest:
            groups.setdefault(digest, []).append(record)
        else:
            without_digest.append(record.get("relative_path"))

    assignment_lookup = {
        item["input_sha256"]: item for item in clustering["assignments"]
    }
    family_lookup = {
        item["family_id"]: item for item in clustering["families"]
    }
    assessment_lookup = {
        item["input_sha256"]: item for item in alignment["recording_assessments"]
    }
    recordings = []
    reuse_groups = []
    for digest in sorted(groups):
        aliases = sorted(groups[digest], key=lambda item: item["relative_path"])
        contexts = [_provider_context(record) for record in aliases]
        categories = sorted({item["category"] for item in contexts})
        intents = sorted({item["stated_intent"] for item in contexts})
        assignment = assignment_lookup.get(digest)
        family = family_lookup.get(assignment["family_id"]) if assignment else None
        assessment = assessment_lookup.get(digest)
        cross_context = len(categories) > 1 or len(intents) > 1
        item = {
            "input_sha256": digest,
            "aliases": [record["relative_path"] for record in aliases],
            "contexts": contexts,
            "categories": categories,
            "stated_intents": intents,
            "cross_context_reuse": cross_context,
            "index_statuses": sorted(
                {record.get("index_status") or "unknown" for record in aliases}
            ),
            "analysis_configuration_versions": sorted(
                {
                    record["analysis_configuration_version"]
                    for record in aliases
                    if record.get("analysis_configuration_version")
                }
            ),
            "family_id": assignment.get("family_id") if assignment else None,
            "family_label": family.get("semantic_label") if family else None,
            "family_silhouette_score": assignment.get("silhouette_score")
            if assignment
            else None,
            "intent_alignment_status": assessment.get("assessment_status")
            if assessment
            else "not_available",
            "intent_alignment_score": assessment.get("normalized_alignment_score")
            if assessment
            else None,
        }
        recordings.append(item)
        if len(aliases) > 1:
            reuse_groups.append(
                {
                    "input_sha256": digest,
                    "aliases": item["aliases"],
                    "categories": categories,
                    "stated_intents": intents,
                    "reuse_classification": "cross_context_reuse"
                    if cross_context
                    else "consistent_duplicate",
                }
            )

    family_counts = Counter(
        item["family_label"] for item in recordings if item["family_label"]
    )
    core = {
        "snapshot_schema_version": SNAPSHOT_SCHEMA_VERSION,
        "method_version": METHOD_VERSION,
        "source_documents": {
            "corpus_index_sha256": index_sha256,
            "clustering_sha256": clustering_sha256,
            "alignment_sha256": document_sha256(alignment),
            "index_schema_version": index.get("index_schema_version"),
            "clustering_schema_version": clustering.get("clustering_schema_version"),
            "alignment_schema_version": alignment.get("alignment_schema_version"),
        },
        "summary": {
            "recording_alias_count": len(index.get("recordings", [])),
            "unique_input_count": len(recordings),
            "clustered_input_count": len(assignment_lookup),
            "alignment_eligible_count": alignment["eligible_recording_count"],
            "alignment_scored_count": alignment["scored_recording_count"],
            "cross_context_reuse_count": sum(
                item["reuse_classification"] == "cross_context_reuse"
                for item in reuse_groups
            ),
            "family_counts_by_label": dict(sorted(family_counts.items())),
            "analysis_configuration_version_counts": index.get(
                "analysis_configuration_version_counts", {}
            ),
        },
        "global_intent_association": alignment["global_association"],
        "intent_profiles": alignment["intent_profiles"],
        "reuse_groups": reuse_groups,
        "records_without_digest": sorted(path for path in without_digest if path),
        "recordings": recordings,
    }
    snapshot_id = f"ave_snapshot_{document_sha256(core)[:16]}"
    document = {
        **core,
        "snapshot_id": snapshot_id,
        "captured_at": captured_at
        or datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
    }
    validate_snapshot(document)
    return document


def _record_map(snapshot: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {item["input_sha256"]: item for item in snapshot["recordings"]}


def _set_change(before: list[str], after: list[str]) -> dict[str, list[str]]:
    return {
        "added": sorted(set(after) - set(before)),
        "removed": sorted(set(before) - set(after)),
    }


def compare_corpus_snapshots(
    baseline: dict[str, Any], current: dict[str, Any]
) -> dict[str, Any]:
    validate_snapshot(baseline)
    validate_snapshot(current)
    before = _record_map(baseline)
    after = _record_map(current)
    before_ids = set(before)
    after_ids = set(after)
    retained_ids = sorted(before_ids & after_ids)

    family_transitions = []
    context_changes = []
    configuration_changes = []
    for digest in retained_ids:
        old = before[digest]
        new = after[digest]
        if (
            old.get("family_id") != new.get("family_id")
            or old.get("family_label") != new.get("family_label")
        ):
            family_transitions.append(
                {
                    "input_sha256": digest,
                    "aliases": new["aliases"],
                    "from_family_id": old.get("family_id"),
                    "from_family_label": old.get("family_label"),
                    "to_family_id": new.get("family_id"),
                    "to_family_label": new.get("family_label"),
                }
            )
        category_change = _set_change(old["categories"], new["categories"])
        intent_change = _set_change(old["stated_intents"], new["stated_intents"])
        alias_change = _set_change(old["aliases"], new["aliases"])
        if any(category_change.values()) or any(intent_change.values()) or any(alias_change.values()):
            context_changes.append(
                {
                    "input_sha256": digest,
                    "category_change": category_change,
                    "intent_change": intent_change,
                    "alias_change": alias_change,
                }
            )
        if (
            old["analysis_configuration_versions"]
            != new["analysis_configuration_versions"]
        ):
            configuration_changes.append(
                {
                    "input_sha256": digest,
                    "before": old["analysis_configuration_versions"],
                    "after": new["analysis_configuration_versions"],
                }
            )

    old_families: dict[str, dict[str, Any]] = {}
    new_families: dict[str, dict[str, Any]] = {}
    for digest, item in before.items():
        if item.get("family_id"):
            family = old_families.setdefault(
                item["family_id"], {"label": item.get("family_label"), "members": set()}
            )
            family["members"].add(digest)
    for digest, item in after.items():
        if item.get("family_id"):
            family = new_families.setdefault(
                item["family_id"], {"label": item.get("family_label"), "members": set()}
            )
            family["members"].add(digest)
    family_overlap = []
    for new_id in sorted(new_families):
        candidates = []
        for old_id in sorted(old_families):
            intersection = len(
                new_families[new_id]["members"] & old_families[old_id]["members"]
            )
            union = len(
                new_families[new_id]["members"] | old_families[old_id]["members"]
            )
            candidates.append((intersection / union if union else 0.0, old_id))
        score, matched_id = max(candidates, default=(0.0, None))
        family_overlap.append(
            {
                "current_family_id": new_id,
                "current_family_label": new_families[new_id]["label"],
                "matched_baseline_family_id": matched_id,
                "matched_baseline_family_label": old_families[matched_id]["label"]
                if matched_id
                else None,
                "jaccard_overlap": round(score, 6),
                "stability": "stable"
                if score >= 0.8
                else "shifted"
                if score >= 0.5
                else "reconfigured"
                if matched_id
                else "new",
            }
        )

    metrics = {}
    keys = sorted(
        set(baseline["global_intent_association"])
        | set(current["global_intent_association"])
    )
    for key in keys:
        old_value = baseline["global_intent_association"].get(key)
        new_value = current["global_intent_association"].get(key)
        metrics[key] = {
            "baseline": old_value,
            "current": new_value,
            "delta": round(new_value - old_value, 6)
            if isinstance(old_value, (int, float)) and isinstance(new_value, (int, float))
            else None,
        }

    document = {
        "comparison_schema_version": COMPARISON_SCHEMA_VERSION,
        "method_version": METHOD_VERSION,
        "baseline_snapshot_id": baseline["snapshot_id"],
        "current_snapshot_id": current["snapshot_id"],
        "summary": {
            "added_input_count": len(after_ids - before_ids),
            "removed_input_count": len(before_ids - after_ids),
            "retained_input_count": len(retained_ids),
            "family_transition_count": len(family_transitions),
            "context_change_count": len(context_changes),
            "configuration_change_count": len(configuration_changes),
            "cross_context_reuse_delta": current["summary"]["cross_context_reuse_count"]
            - baseline["summary"]["cross_context_reuse_count"],
        },
        "added_inputs": [after[digest] for digest in sorted(after_ids - before_ids)],
        "removed_inputs": [before[digest] for digest in sorted(before_ids - after_ids)],
        "family_transitions": family_transitions,
        "family_overlap": family_overlap,
        "context_changes": context_changes,
        "configuration_changes": configuration_changes,
        "intent_association_changes": metrics,
    }
    validate_comparison(document)
    return document


def write_snapshot(document: dict[str, Any], directory: Path) -> tuple[Path, bool]:
    validate_snapshot(document)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{document['snapshot_id']}.json"
    if path.exists():
        validate_snapshot(json.loads(path.read_text()))
        return path, False
    path.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n")
    return path, True


def write_comparison(document: dict[str, Any], output_directory: Path) -> Path:
    validate_comparison(document)
    output_directory.mkdir(parents=True, exist_ok=True)
    path = output_directory / "latest_comparison.json"
    path.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n")
    return path
