"""Strict consumer for the Lumenate Nova protocol export contract 0.2.0."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

import jsonschema
from referencing import Registry, Resource


ROOT = Path(__file__).resolve().parent
CONTRACTS = ROOT / "contracts"
PROTOCOL_SCHEMA_PATH = CONTRACTS / "lumenate-protocol-export-0.2.0.schema.json"
AVE_SCHEMA_PATH = CONTRACTS / "ave-evidence-object-1.0.0.schema.json"
AVE_SCHEMA_URI = (
    "https://example.invalid/lumenate-nova/contracts/"
    "ave-evidence-object-1.0.0.schema.json"
)
SUPPORTED_PROTOCOL_VERSIONS = frozenset({"0.2.0"})
SUPPORTED_AVE_EVIDENCE_VERSIONS = frozenset({"1.0.0"})


class LumenateContractError(ValueError):
    """Raised when a Lumenate export is unsupported or internally inconsistent."""


@dataclass(frozen=True)
class NormalizedLightEvent:
    """A light segment normalized to seconds without changing producer claims."""

    segment_id: str
    start_seconds: float
    end_seconds: float
    execution_layer: str
    intensity: float | None
    color_rgb: tuple[int, int, int] | None
    pulse_frequency_hz: float | None
    duty_cycle: float | None
    pulse_shape: str | None
    command_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]


@dataclass(frozen=True)
class ImportedLumenateProtocol:
    """Validated export and its normalized light-event timeline."""

    export_id: str
    schema_version: str
    session_id: str
    title: str | None
    duration_seconds: float
    audio_identity_status: str
    timeline: tuple[NormalizedLightEvent, ...]
    source_hashes: Mapping[str, str]
    evidence_by_id: Mapping[str, Mapping[str, Any]]
    document: Mapping[str, Any]


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise LumenateContractError(f"cannot read protocol export {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise LumenateContractError("protocol export root must be an object")
    return value


def _duplicates(values: Iterable[str]) -> set[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    return duplicates


def _check_references(errors, owner, values, available, kind) -> None:
    for value in values:
        if value not in available:
            errors.append(f"{owner} references unknown {kind} {value!r}")


def _semantic_errors(document: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    duration = document["session"]["duration_ms"]
    collections = {
        "clock": (document["clocks"], "clock_id"),
        "segment": (document["segments"], "segment_id"),
        "transition": (document["transitions"], "transition_id"),
        "command": (document["commands"], "command_id"),
        "anchor": (document["sync_anchors"], "anchor_id"),
        "evidence": (document["ave_evidence"], "evidence_id"),
        "source": (document["provenance"]["source_hashes"], "source_id"),
    }
    ids: dict[str, set[str]] = {}
    for kind, (items, field) in collections.items():
        values = [item[field] for item in items]
        duplicates = _duplicates(values)
        if duplicates:
            errors.append(f"duplicate {kind} IDs: {', '.join(sorted(duplicates))}")
        ids[kind] = set(values)

    for name in ("light_timeline_origin", "audio_timeline_origin"):
        origin = document["session"][name]
        if origin is not None:
            _check_references(errors, f"session.{name}", [origin["clock_id"]], ids["clock"], "clock")
            _check_references(errors, f"session.{name}", origin["evidence_ids"], ids["evidence"], "evidence")

    audio = document["audio_asset"]
    if audio["identity_status"] == "verified":
        source_hashes = {item["source_id"]: item["sha256"] for item in document["provenance"]["source_hashes"]}
        if source_hashes.get(audio["source_id"]) != audio["sha256"]:
            errors.append("verified audio identity must match a provenance source hash")

    previous_start = -1
    segments = document["segments"]
    for segment in segments:
        owner = f"segment {segment['segment_id']!r}"
        start, end = segment["start_ms"], segment["end_ms"]
        if start < previous_start:
            errors.append(f"{owner} is not ordered by start_ms")
        previous_start = start
        if end < start:
            errors.append(f"{owner} ends before it starts")
        if end > duration:
            errors.append(f"{owner} exceeds session duration")
        _check_references(errors, owner, segment["command_ids"], ids["command"], "command")
        _check_references(errors, owner, segment["evidence_ids"], ids["evidence"], "evidence")
        _check_references(errors, owner, segment["overlap_with_segment_ids"], ids["segment"], "segment")
        if segment["segment_id"] in segment["overlap_with_segment_ids"]:
            errors.append(f"{owner} declares an overlap with itself")

    for index, left in enumerate(segments):
        for right in segments[index + 1 :]:
            overlaps = left["start_ms"] < right["end_ms"] and right["start_ms"] < left["end_ms"]
            left_declares = right["segment_id"] in left["overlap_with_segment_ids"]
            right_declares = left["segment_id"] in right["overlap_with_segment_ids"]
            if overlaps and not (left_declares and right_declares):
                errors.append(f"overlap between {left['segment_id']!r} and {right['segment_id']!r} must be declared by both segments")
            if not overlaps and (left_declares or right_declares):
                errors.append(f"declared overlap between {left['segment_id']!r} and {right['segment_id']!r} does not occur")

    for transition in document["transitions"]:
        owner = f"transition {transition['transition_id']!r}"
        start, end = transition["start_ms"], transition["end_ms"]
        if end < start:
            errors.append(f"{owner} ends before it starts")
        if end > duration:
            errors.append(f"{owner} exceeds session duration")
        for field in ("from_segment_id", "to_segment_id"):
            value = transition[field]
            if value is not None:
                _check_references(errors, owner, [value], ids["segment"], "segment")
        _check_references(errors, owner, transition["evidence_ids"], ids["evidence"], "evidence")

    for clock in document["clocks"]:
        _check_references(errors, f"clock {clock['clock_id']!r}", clock["evidence_ids"], ids["evidence"], "evidence")
    for command in document["commands"]:
        owner = f"command {command['command_id']!r}"
        _check_references(errors, owner, [command["clock_id"]], ids["clock"], "clock")
        _check_references(errors, owner, command["evidence_ids"], ids["evidence"], "evidence")
    for anchor in document["sync_anchors"]:
        owner = f"anchor {anchor['anchor_id']!r}"
        clocks = [anchor["from_clock_id"], anchor["to_clock_id"]]
        _check_references(errors, owner, clocks, ids["clock"], "clock")
        if clocks[0] == clocks[1]:
            errors.append(f"{owner} must relate two different clocks")
        _check_references(errors, owner, anchor["evidence_ids"], ids["evidence"], "evidence")
    for evidence in document["ave_evidence"]:
        _check_references(errors, f"evidence {evidence['evidence_id']!r}", evidence["supporting_evidence_ids"], ids["evidence"], "evidence")
    return errors


def validate_lumenate_export(document: Mapping[str, Any]) -> None:
    """Validate versions, JSON Schema, and cross-field integrity."""
    if not isinstance(document, Mapping):
        raise LumenateContractError("protocol export root must be an object")
    protocol_version = document.get("schema_version")
    if protocol_version not in SUPPORTED_PROTOCOL_VERSIONS:
        raise LumenateContractError(f"unsupported Lumenate protocol schema_version {protocol_version!r}; supported: 0.2.0")
    evidence_version = document.get("ave_evidence_schema_version")
    if evidence_version not in SUPPORTED_AVE_EVIDENCE_VERSIONS:
        raise LumenateContractError(f"unsupported AVE evidence schema version {evidence_version!r}; supported: 1.0.0")

    protocol_schema = _load_json(PROTOCOL_SCHEMA_PATH)
    ave_schema = _load_json(AVE_SCHEMA_PATH)
    registry = Registry().with_resource(AVE_SCHEMA_URI, Resource.from_contents(ave_schema))
    validator = jsonschema.validators.Draft202012Validator(protocol_schema, registry=registry, format_checker=jsonschema.FormatChecker())
    schema_errors = sorted(validator.iter_errors(document), key=lambda item: list(item.path))
    if schema_errors:
        details = []
        for error in schema_errors:
            location = ".".join(str(part) for part in error.absolute_path) or "<root>"
            details.append(f"{location}: {error.message}")
        raise LumenateContractError("schema validation failed:\n- " + "\n- ".join(details))
    errors = _semantic_errors(document)
    if errors:
        raise LumenateContractError("semantic validation failed:\n- " + "\n- ".join(errors))


def _normalize_segment(segment: Mapping[str, Any]) -> NormalizedLightEvent:
    pulse = segment["pulse"]
    color = segment["color_rgb"]
    return NormalizedLightEvent(
        segment_id=segment["segment_id"],
        start_seconds=segment["start_ms"] / 1000.0,
        end_seconds=segment["end_ms"] / 1000.0,
        execution_layer=segment["execution_layer"],
        intensity=segment["intensity"],
        color_rgb=tuple(color) if color is not None else None,
        pulse_frequency_hz=pulse["frequency_hz"] if pulse is not None else None,
        duty_cycle=pulse["duty_cycle"] if pulse is not None else None,
        pulse_shape=pulse["shape"] if pulse is not None else None,
        command_ids=tuple(segment["command_ids"]),
        evidence_ids=tuple(segment["evidence_ids"]),
    )


def import_lumenate_export(source: str | Path | Mapping[str, Any]) -> ImportedLumenateProtocol:
    """Validate and import a file or in-memory Lumenate protocol document."""
    document = deepcopy(dict(source)) if isinstance(source, Mapping) else _load_json(Path(source))
    validate_lumenate_export(document)
    source_hashes = {item["source_id"]: item["sha256"] for item in document["provenance"]["source_hashes"]}
    evidence_by_id = {item["evidence_id"]: item for item in document["ave_evidence"]}
    return ImportedLumenateProtocol(
        export_id=document["export_id"], schema_version=document["schema_version"],
        session_id=document["session"]["session_id"], title=document["session"]["title"],
        duration_seconds=document["session"]["duration_ms"] / 1000.0,
        audio_identity_status=document["audio_asset"]["identity_status"],
        timeline=tuple(_normalize_segment(item) for item in document["segments"]),
        source_hashes=source_hashes, evidence_by_id=evidence_by_id, document=document,
    )
