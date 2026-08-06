from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from evidence.schema import SCHEMA_VERSION, validate_evidence_object


INDEX_SCHEMA_VERSION = "1.0.0"


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as input_file:
        for chunk in iter(lambda: input_file.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _measurement_map(evidence: dict[str, Any]) -> dict[str, Any]:
    return {item["name"]: item["value"] for item in evidence["measurements"]}


def _confidence_score(evidence: dict[str, Any]) -> float:
    confidence = evidence.get("confidence")
    return float(confidence["score"]) if confidence else 0.0


def _strongest_carrier_pair(evidence: list[dict[str, Any]]) -> dict[str, Any] | None:
    candidates = [
        item for item in evidence if item["evidence_type"] == "persistent_carrier_pair"
    ]
    if not candidates:
        return None
    strongest = max(candidates, key=_confidence_score)
    values = _measurement_map(strongest)
    return {
        "left_hz": values["left_carrier_frequency"],
        "right_hz": values["right_carrier_frequency"],
        "difference_hz": values["carrier_difference"],
        "pair_type": strongest["context"]["pair_type"],
        "confidence": _confidence_score(strongest),
    }


def _dominant_envelope(evidence: list[dict[str, Any]]) -> dict[str, Any] | None:
    candidates = []
    for item in evidence:
        if item["evidence_type"] != "carrier_envelope_analysis":
            continue
        values = _measurement_map(item)
        if "dominant_modulation_frequency" not in values:
            continue
        candidates.append((item, values))
    if not candidates:
        return None
    item, values = max(
        candidates,
        key=lambda candidate: candidate[1]["dominant_modulation_relative_power"],
    )
    channels = item["scope"]["channels"]
    return {
        "channel": channels[0] if channels else None,
        "carrier_center_hz": values["carrier_center_frequency"],
        "modulation_hz": values["dominant_modulation_frequency"],
        "relative_power": values["dominant_modulation_relative_power"],
        "modulation_depth": values["modulation_depth"],
    }


def _modulation_reconstruction(
    evidence: list[dict[str, Any]],
) -> dict[str, Any] | None:
    item = next(
        (
            candidate
            for candidate in evidence
            if candidate["evidence_type"] == "modulation_spectrum_reconstruction"
        ),
        None,
    )
    if item is None:
        return None
    values = _measurement_map(item)
    return {
        "classification": values["classification"],
        "primary_shared_modulation_hz": values.get("primary_shared_modulation"),
        "shared_window_coverage": values.get("shared_window_coverage"),
        "confidence": _confidence_score(item) if item.get("confidence") else None,
    }


def _phase_relationship(evidence: list[dict[str, Any]]) -> dict[str, Any] | None:
    item = next(
        (
            candidate
            for candidate in evidence
            if candidate["evidence_type"] == "time_resolved_phase_relationship"
        ),
        None,
    )
    if item is None:
        return None
    values = _measurement_map(item)
    return {
        "behavior": values["dominant_phase_behavior"],
        "window_coverage": values["behavior_window_coverage"],
        "median_difference_hz": values["median_phase_derived_difference"],
        "confidence": _confidence_score(item),
    }


def _top_hypothesis(evidence: list[dict[str, Any]]) -> dict[str, Any] | None:
    candidates = []
    for item in evidence:
        if item["evidence_type"] != "protocol_intent_hypothesis":
            continue
        values = _measurement_map(item)
        if "hypothesis_score" in values:
            ranking_score = float(values["hypothesis_score"])
            ranking_source = "hypothesis_score_measurement"
        elif (
            item.get("confidence")
            and item["confidence"].get("method") == "protocol_hypothesis_score"
        ):
            ranking_score = _confidence_score(item)
            ranking_source = "legacy_protocol_hypothesis_confidence"
        else:
            continue
        candidates.append((ranking_score, ranking_source, item, values))
    if not candidates:
        return None
    ranking_score, ranking_source, item, values = max(
        candidates,
        key=lambda candidate: candidate[0],
    )
    return {
        "intent": item["summary"],
        "difference_hz": values["average_difference_frequency"],
        "brainwave_band": values["brainwave_band"],
        "duration_seconds": values["duration"],
        "ranking_score": ranking_score,
        "ranking_source": ranking_source,
        "confidence": (
            _confidence_score(item)
            if ranking_source == "hypothesis_score_measurement"
            else None
        ),
    }


def summarize_evidence_document(document: dict[str, Any]) -> dict[str, Any]:
    if document.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unsupported evidence document schema version")
    evidence = document.get("evidence")
    if not isinstance(evidence, list):
        raise ValueError("evidence document must contain an evidence list")
    if document.get("evidence_count") != len(evidence):
        raise ValueError("evidence_count does not match evidence list")
    for item in evidence:
        validate_evidence_object(item)

    type_counts = Counter(item["evidence_type"] for item in evidence)
    level_counts = Counter(item["evidence_level"] for item in evidence)
    return {
        "evidence_schema_version": document["schema_version"],
        "evidence_count": len(evidence),
        "evidence_type_counts": dict(sorted(type_counts.items())),
        "evidence_level_counts": dict(sorted(level_counts.items())),
        "run_metadata": document.get("run_metadata", {}),
        "strongest_carrier_pair": _strongest_carrier_pair(evidence),
        "dominant_envelope": _dominant_envelope(evidence),
        "modulation_reconstruction": _modulation_reconstruction(evidence),
        "phase_relationship": _phase_relationship(evidence),
        "top_hypothesis": _top_hypothesis(evidence),
    }


def _relative_path(path: Path, project_root: Path) -> str:
    try:
        return str(path.resolve().relative_to(project_root.resolve()))
    except ValueError:
        return str(path)


def build_corpus_index(
    batch_summary_path: Path,
    project_root: Path,
    *,
    hash_inputs: bool = True,
) -> dict[str, Any]:
    from corpus.manifests import (
        manifest_path_for,
        resolved_labels,
        validate_recording_manifest,
    )

    batch = json.loads(batch_summary_path.read_text())
    indexed_recordings = []

    for batch_record in sorted(
        batch["recordings"],
        key=lambda item: item["relative_path"],
    ):
        input_path = Path(batch_record["path"]) if batch_record.get("path") else None
        record = {
            "relative_path": batch_record["relative_path"],
            "source": batch_record.get("source", ""),
            "category": batch_record.get("category", ""),
            "stated_intent": batch_record.get("stated_intent", ""),
            "notes": batch_record.get("notes", ""),
            "batch_metadata": {
                "relative_path": batch_record["relative_path"],
                "source": batch_record.get("source", ""),
                "category": batch_record.get("category", ""),
                "stated_intent": batch_record.get("stated_intent", ""),
            },
            "metadata_status": "missing",
            "metadata_manifest_path": None,
            "metadata_schema_version": None,
            "metadata_error": None,
            "label_source": "batch_summary",
            "batch_status": batch_record["status"],
            "index_status": batch_record["status"],
            "input_size_bytes": None,
            "input_sha256": None,
            "duplicate_input_paths": [],
            "duration_seconds": batch_record.get("duration_seconds"),
            "evidence_path": None,
            "evidence_summary": None,
            "index_error": None,
        }

        if input_path and input_path.exists():
            record["input_size_bytes"] = input_path.stat().st_size
            if hash_inputs:
                record["input_sha256"] = sha256_file(input_path)

            metadata_path = manifest_path_for(input_path)
            if metadata_path.exists():
                record["metadata_manifest_path"] = _relative_path(
                    metadata_path,
                    project_root,
                )
                try:
                    metadata = json.loads(metadata_path.read_text())
                    validate_recording_manifest(metadata)
                    metadata_hash = metadata["identity"]["sha256"]
                    if record["input_sha256"] and metadata_hash != record["input_sha256"]:
                        raise ValueError("metadata SHA-256 does not match input")
                    labels = resolved_labels(metadata)
                    record["relative_path"] = metadata["relative_path"]
                    record["source"] = labels["source"]
                    record["category"] = labels["category"]
                    record["stated_intent"] = labels["claimed_intent"]
                    record["label_source"] = labels["label_source"]
                    record["metadata_schema_version"] = metadata[
                        "manifest_schema_version"
                    ]
                    record["metadata_status"] = "validated"
                    if metadata["curation"]["notes"]:
                        record["notes"] = metadata["curation"]["notes"]
                except (OSError, ValueError, TypeError, KeyError) as exc:
                    record["metadata_status"] = "invalid"
                    record["metadata_error"] = str(exc)

        output_dir = batch_record.get("output_dir")
        evidence_path = Path(output_dir) / "ave_evidence.json" if output_dir else None
        if evidence_path and evidence_path.exists():
            record["evidence_path"] = _relative_path(evidence_path, project_root)
            try:
                document = json.loads(evidence_path.read_text())
                record["evidence_summary"] = summarize_evidence_document(document)
                record["duration_seconds"] = document.get("run_metadata", {}).get(
                    "duration_seconds",
                    record["duration_seconds"],
                )
                record["index_status"] = "indexed"
            except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
                record["index_status"] = "invalid_evidence"
                record["index_error"] = str(exc)

        indexed_recordings.append(record)

    indexed_recordings.sort(key=lambda item: item["relative_path"])

    records_by_hash: dict[str, list[dict[str, Any]]] = {}
    for record in indexed_recordings:
        if record["input_sha256"]:
            records_by_hash.setdefault(record["input_sha256"], []).append(record)
    duplicate_groups = []
    for input_hash, records in sorted(records_by_hash.items()):
        if len(records) < 2:
            continue
        paths = sorted(record["relative_path"] for record in records)
        duplicate_groups.append({"input_sha256": input_hash, "relative_paths": paths})
        for record in records:
            record["duplicate_input_paths"] = [
                path for path in paths if path != record["relative_path"]
            ]

    batch_counts = Counter(item["batch_status"] for item in indexed_recordings)
    index_counts = Counter(item["index_status"] for item in indexed_recordings)
    source_counts = Counter(item["source"] for item in indexed_recordings)
    category_counts = Counter(item["category"] for item in indexed_recordings)
    intent_counts = Counter(item["stated_intent"] for item in indexed_recordings)
    metadata_counts = Counter(item["metadata_status"] for item in indexed_recordings)
    evidence_total = sum(
        item["evidence_summary"]["evidence_count"]
        for item in indexed_recordings
        if item["evidence_summary"] is not None
    )
    return {
        "index_schema_version": INDEX_SCHEMA_VERSION,
        "evidence_schema_version": SCHEMA_VERSION,
        "recording_count": len(indexed_recordings),
        "indexed_recording_count": index_counts["indexed"],
        "indexed_evidence_count": evidence_total,
        "input_hash_algorithm": "sha256" if hash_inputs else None,
        "batch_status_counts": dict(sorted(batch_counts.items())),
        "index_status_counts": dict(sorted(index_counts.items())),
        "source_counts": dict(sorted(source_counts.items())),
        "category_counts": dict(sorted(category_counts.items())),
        "stated_intent_counts": dict(sorted(intent_counts.items())),
        "metadata_status_counts": dict(sorted(metadata_counts.items())),
        "duplicate_input_groups": duplicate_groups,
        "recordings": indexed_recordings,
    }


CSV_FIELDS = [
    "relative_path",
    "source",
    "category",
    "stated_intent",
    "label_source",
    "metadata_status",
    "metadata_manifest_path",
    "batch_status",
    "index_status",
    "duration_seconds",
    "input_size_bytes",
    "input_sha256",
    "duplicate_input_paths",
    "evidence_count",
    "strongest_carrier_left_hz",
    "strongest_carrier_right_hz",
    "strongest_carrier_difference_hz",
    "dominant_envelope_modulation_hz",
    "modulation_classification",
    "primary_shared_modulation_hz",
    "phase_behavior",
    "phase_window_coverage",
    "top_hypothesis_intent",
    "top_hypothesis_difference_hz",
    "top_hypothesis_ranking_score",
    "top_hypothesis_ranking_source",
    "evidence_path",
    "index_error",
]


def _csv_row(record: dict[str, Any]) -> dict[str, Any]:
    summary = record["evidence_summary"] or {}
    carrier = summary.get("strongest_carrier_pair") or {}
    envelope = summary.get("dominant_envelope") or {}
    modulation = summary.get("modulation_reconstruction") or {}
    phase = summary.get("phase_relationship") or {}
    hypothesis = summary.get("top_hypothesis") or {}
    return {
        "relative_path": record["relative_path"],
        "source": record["source"],
        "category": record["category"],
        "stated_intent": record["stated_intent"],
        "label_source": record.get("label_source"),
        "metadata_status": record.get("metadata_status"),
        "metadata_manifest_path": record.get("metadata_manifest_path"),
        "batch_status": record["batch_status"],
        "index_status": record["index_status"],
        "duration_seconds": record["duration_seconds"],
        "input_size_bytes": record["input_size_bytes"],
        "input_sha256": record["input_sha256"],
        "duplicate_input_paths": " | ".join(
            record.get("duplicate_input_paths", [])
        ),
        "evidence_count": summary.get("evidence_count"),
        "strongest_carrier_left_hz": carrier.get("left_hz"),
        "strongest_carrier_right_hz": carrier.get("right_hz"),
        "strongest_carrier_difference_hz": carrier.get("difference_hz"),
        "dominant_envelope_modulation_hz": envelope.get("modulation_hz"),
        "modulation_classification": modulation.get("classification"),
        "primary_shared_modulation_hz": modulation.get(
            "primary_shared_modulation_hz"
        ),
        "phase_behavior": phase.get("behavior"),
        "phase_window_coverage": phase.get("window_coverage"),
        "top_hypothesis_intent": hypothesis.get("intent"),
        "top_hypothesis_difference_hz": hypothesis.get("difference_hz"),
        "top_hypothesis_ranking_score": hypothesis.get("ranking_score"),
        "top_hypothesis_ranking_source": hypothesis.get("ranking_source"),
        "evidence_path": record["evidence_path"],
        "index_error": record["index_error"],
    }


def write_corpus_index(index: dict[str, Any], output_directory: Path) -> tuple[Path, Path]:
    output_directory.mkdir(parents=True, exist_ok=True)
    json_path = output_directory / "corpus_index.json"
    csv_path = output_directory / "corpus_index.csv"
    json_path.write_text(json.dumps(index, indent=2, sort_keys=True) + "\n")
    with csv_path.open("w", newline="") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(_csv_row(record) for record in index["recordings"])
    return json_path, csv_path
