from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any


DASHBOARD_SCHEMA_VERSION = "1.0.0"
TEMPLATE_PATH = Path(__file__).with_name("dashboard.html")


def _flatten_record(record: dict[str, Any]) -> dict[str, Any]:
    summary = record.get("evidence_summary") or {}
    carrier = summary.get("strongest_carrier_pair") or {}
    envelope = summary.get("dominant_envelope") or {}
    modulation = summary.get("modulation_reconstruction") or {}
    phase = summary.get("phase_relationship") or {}
    hypothesis = summary.get("top_hypothesis") or {}
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
        "input_sha256": record.get("input_sha256"),
        "input_size_bytes": record.get("input_size_bytes"),
        "duration_seconds": record.get("duration_seconds"),
        "evidence_count": summary.get("evidence_count"),
        "evidence_path": record.get("evidence_path"),
        "metadata_manifest_path": record.get("metadata_manifest_path"),
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
        "protocol_family_id": None,
        "protocol_family_descriptor": None,
        "protocol_family_silhouette": None,
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
    if clustering is not None:
        from clustering.protocol_families import validate_protocol_families

        validate_protocol_families(clustering)
        if clustering["source_index_sha256"] == index_digest:
            clustering_status = "validated"
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
        },
        "clustering_status": clustering_status,
        "clustering_method": clustering.get("method") if clustering_status == "validated" else None,
        "protocol_families": protocol_families,
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
