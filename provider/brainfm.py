from __future__ import annotations

import base64
import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from core.hashing import sha256_file
from core.media import AUDIO_EXTENSIONS


PROVIDER_SIDECAR_SCHEMA_VERSION = "1.0.0"
EXTRACTOR_VERSION = "1.0.0"
SENSITIVE_KEY_PATTERN = re.compile(
    r"(?:token|authorization|cookie|password|secret|session)", re.IGNORECASE
)


class ProviderMetadataError(ValueError):
    """Raised when provider metadata cannot be extracted or validated safely."""


@dataclass(frozen=True)
class ProviderBatchEntry:
    status: str
    recording_path: Path | None = None
    capture_path: Path | None = None
    output_path: Path | None = None
    sidecar: dict[str, Any] | None = None
    message: str | None = None


def provider_sidecar_path_for(recording_path: Path) -> Path:
    return recording_path.with_name(f"{recording_path.name}.provider.json")


def _parse_concatenated_json(text: str) -> list[Any]:
    decoder = json.JSONDecoder()
    documents = []
    position = 0
    while True:
        while position < len(text) and text[position].isspace():
            position += 1
        if position >= len(text):
            break
        try:
            document, position = decoder.raw_decode(text, position)
        except json.JSONDecodeError as error:
            raise ProviderMetadataError(
                f"invalid concatenated JSON at character {error.pos}: {error.msg}"
            ) from error
        documents.append(document)
    if not documents:
        raise ProviderMetadataError("capture contains no JSON documents")
    return documents


def _har_documents(document: dict[str, Any]) -> list[Any] | None:
    log = document.get("log")
    if not isinstance(log, dict) or not isinstance(log.get("entries"), list):
        return None
    extracted = []
    for entry in log["entries"]:
        if not isinstance(entry, dict):
            continue
        content = (entry.get("response") or {}).get("content")
        if not isinstance(content, dict) or not isinstance(content.get("text"), str):
            continue
        text = content["text"]
        if content.get("encoding") == "base64":
            try:
                text = base64.b64decode(text).decode("utf-8")
            except (ValueError, UnicodeDecodeError):
                # Mixed HAR exports commonly include base64-encoded audio, images,
                # and compressed bodies alongside JSON. They are unrelated to the
                # metadata extractor and must not abort the entire capture.
                continue
        try:
            extracted.extend(_parse_concatenated_json(text))
        except ProviderMetadataError:
            continue
    if not extracted:
        raise ProviderMetadataError("HAR contains no JSON response bodies")
    return extracted


def parse_capture(capture_path: Path) -> tuple[list[Any], str]:
    text = capture_path.read_text(errors="strict")
    documents = _parse_concatenated_json(text)
    if len(documents) == 1 and isinstance(documents[0], dict):
        har = _har_documents(documents[0])
        if har is not None:
            return har, "har_json_responses"
    return documents, "concatenated_json" if len(documents) > 1 else "json"


def _walk(value: Any) -> Iterable[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for nested in value.values():
            yield from _walk(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from _walk(nested)


def _matching_variations(
    track: dict[str, Any], filenames: set[str]
) -> list[tuple[str, dict[str, Any]]]:
    variations = track.get("variations")
    if not isinstance(variations, list):
        return []
    matches = []
    for variation in variations:
        if not isinstance(variation, dict):
            continue
        filename = variation.get("url")
        if isinstance(filename, str) and filename in filenames:
            matches.append((filename, variation))
    return matches


def _tag_map(track: dict[str, Any]) -> dict[str, list[str]]:
    grouped: dict[str, set[str]] = defaultdict(set)
    tags = track.get("tags")
    if isinstance(tags, list):
        for tag in tags:
            if not isinstance(tag, dict):
                continue
            tag_type = tag.get("type")
            value = tag.get("value")
            if isinstance(tag_type, str) and isinstance(value, str):
                grouped[tag_type].add(value)
    return {key: sorted(values) for key, values in sorted(grouped.items())}


def _display_value(value: Any) -> str | None:
    if not isinstance(value, dict):
        return None
    display = value.get("displayValue")
    return display if isinstance(display, str) else None


def _canonical_track_projection(
    track: dict[str, Any], variation: dict[str, Any]
) -> dict[str, Any]:
    tags = _tag_map(track)
    activity = _display_value(track.get("mobileActivity"))
    mental_state = _display_value(track.get("mentalState"))
    if mental_state is None:
        mental_state = _display_value(track.get("dynamicMentalState"))
    style = variation.get("style") if isinstance(variation.get("style"), str) else None
    return {
        "provider_track": {
            "track_id": track.get("id"),
            "variation_id": variation.get("id"),
            "title": track.get("name"),
            "filename": variation.get("url"),
        },
        "taxonomy": {
            "mental_state": mental_state,
            "activity": activity,
            "style": style,
            "genres": tags.get("genre", []),
            "subgenres": tags.get("subgenre", []),
            "moods": tags.get("mood", []),
            "instruments": tags.get("instrument", []),
            "release_tags": tags.get("release", []),
            "all_provider_tags": tags,
        },
        "provider_measurements": {
            "beats_per_minute": track.get("beatsPerMinute"),
            "brightness_level": track.get("brightnessLevel"),
            "complexity_level": track.get("complexityLevel"),
            "neural_effect_level": variation.get("neuralEffectLevel"),
            "declared_duration_seconds": variation.get("lengthInSeconds"),
        },
        "provider_lifecycle": {
            "created_at": track.get("createdAt"),
            "release_status": track.get("releaseStatus"),
            "has_multiple_neural_effect_levels": track.get("hasMultipleNELs"),
        },
    }


def _projection_signature(projection: dict[str, Any]) -> str:
    return json.dumps(projection, sort_keys=True, separators=(",", ":"))


def _validate_string(value: Any, field: str) -> None:
    if not isinstance(value, str) or not value:
        raise ProviderMetadataError(f"{field} must be non-empty text")


def _reject_sensitive_content(value: Any, path: str = "root") -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            if SENSITIVE_KEY_PATTERN.search(key):
                raise ProviderMetadataError(f"sensitive field is forbidden: {path}.{key}")
            _reject_sensitive_content(nested, f"{path}.{key}")
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            _reject_sensitive_content(nested, f"{path}[{index}]")
    elif isinstance(value, str):
        lowered = value.lower()
        if "tokenedurl" in lowered or re.search(r"[?&](?:token|signature|auth)=", value, re.I):
            raise ProviderMetadataError(f"tokenized URL is forbidden: {path}")


def validate_provider_sidecar(sidecar: dict[str, Any]) -> None:
    required = {
        "provider_metadata_schema_version",
        "provider",
        "recording",
        "source_capture",
        "match",
        "provider_track",
        "taxonomy",
        "provider_measurements",
        "provider_lifecycle",
        "extraction_provenance",
    }
    missing = required - sidecar.keys()
    if missing:
        raise ProviderMetadataError(
            f"missing required fields: {', '.join(sorted(missing))}"
        )
    if sidecar["provider_metadata_schema_version"] != PROVIDER_SIDECAR_SCHEMA_VERSION:
        raise ProviderMetadataError("unsupported provider_metadata_schema_version")
    if sidecar["provider"] != "brain.fm":
        raise ProviderMetadataError("unsupported provider")
    recording = sidecar["recording"]
    _validate_string(recording.get("filename"), "recording.filename")
    if not re.fullmatch(r"[0-9a-f]{64}", str(recording.get("sha256", ""))):
        raise ProviderMetadataError("recording.sha256 must be a SHA-256 digest")
    capture = sidecar["source_capture"]
    if not re.fullmatch(r"[0-9a-f]{64}", str(capture.get("sha256", ""))):
        raise ProviderMetadataError("source_capture.sha256 must be a SHA-256 digest")
    if capture.get("format") not in {"json", "concatenated_json", "har_json_responses"}:
        raise ProviderMetadataError("unsupported source_capture.format")
    if not isinstance(capture.get("json_document_count"), int) or capture[
        "json_document_count"
    ] < 1:
        raise ProviderMetadataError("source_capture.json_document_count must be positive")
    provider_track = sidecar["provider_track"]
    for field in ("track_id", "variation_id", "title", "filename"):
        _validate_string(provider_track.get(field), f"provider_track.{field}")
    if provider_track["filename"] != recording["filename"]:
        raise ProviderMetadataError("provider filename does not match recording")
    match = sidecar["match"]
    if match.get("strategy") != "exact_variation_filename":
        raise ProviderMetadataError("unsupported match.strategy")
    for field in ("matching_occurrence_count", "unique_canonical_record_count"):
        if not isinstance(match.get(field), int) or match[field] < 1:
            raise ProviderMetadataError(f"match.{field} must be positive")
    if match["unique_canonical_record_count"] != 1:
        raise ProviderMetadataError("provider match must resolve to one canonical record")
    taxonomy = sidecar["taxonomy"]
    for field in (
        "genres",
        "subgenres",
        "moods",
        "instruments",
        "release_tags",
    ):
        values = taxonomy.get(field)
        if not isinstance(values, list) or any(not isinstance(item, str) for item in values):
            raise ProviderMetadataError(f"taxonomy.{field} must be a text list")
    for field in ("mental_state", "activity", "style"):
        value = taxonomy.get(field)
        if value is not None and not isinstance(value, str):
            raise ProviderMetadataError(f"taxonomy.{field} must be text or null")
    measurements = sidecar["provider_measurements"]
    beats = measurements.get("beats_per_minute")
    if beats is not None and (not isinstance(beats, (int, float)) or beats <= 0):
        raise ProviderMetadataError("provider_measurements.beats_per_minute must be positive")
    for field in ("brightness_level", "complexity_level", "neural_effect_level"):
        value = measurements.get(field)
        if value is not None and (
            not isinstance(value, (int, float)) or not 0 <= value <= 1
        ):
            raise ProviderMetadataError(f"provider_measurements.{field} must be 0..1")
    duration = measurements.get("declared_duration_seconds")
    if duration is not None and (
        not isinstance(duration, (int, float)) or duration <= 0
    ):
        raise ProviderMetadataError(
            "provider_measurements.declared_duration_seconds must be positive"
        )
    _reject_sensitive_content(sidecar)


def extract_brainfm_sidecars(
    capture_path: Path,
    recordings_directory: Path,
) -> list[tuple[Path, dict[str, Any]]]:
    recordings = sorted(
        path
        for path in recordings_directory.iterdir()
        if path.is_file() and path.suffix.lower() in AUDIO_EXTENSIONS
    )
    if not recordings:
        raise ProviderMetadataError("recordings directory contains no supported audio")
    return _extract_brainfm_sidecars_for_recordings(capture_path, recordings)


def _extract_brainfm_sidecars_for_recordings(
    capture_path: Path,
    recordings: list[Path],
) -> list[tuple[Path, dict[str, Any]]]:
    documents, capture_format = parse_capture(capture_path)
    filenames = {path.name for path in recordings}
    candidates: dict[str, list[dict[str, Any]]] = defaultdict(list)
    occurrence_counts: Counter[str] = Counter()
    for document in documents:
        for candidate in _walk(document):
            for filename, variation in _matching_variations(candidate, filenames):
                projection = _canonical_track_projection(candidate, variation)
                candidates[filename].append(projection)
                occurrence_counts[filename] += 1

    capture_hash = sha256_file(capture_path)
    results = []
    for recording in recordings:
        matches = candidates.get(recording.name, [])
        if not matches:
            raise ProviderMetadataError(
                f"no provider record matched recording: {recording.name}"
            )
        unique = {_projection_signature(match): match for match in matches}
        if len(unique) != 1:
            raise ProviderMetadataError(
                f"conflicting provider records matched recording: {recording.name}"
            )
        projection = next(iter(unique.values()))
        sidecar = {
            "provider_metadata_schema_version": PROVIDER_SIDECAR_SCHEMA_VERSION,
            "provider": "brain.fm",
            "recording": {
                "filename": recording.name,
                "hash_algorithm": "sha256",
                "sha256": sha256_file(recording),
                "size_bytes": recording.stat().st_size,
            },
            "source_capture": {
                "filename": capture_path.name,
                "hash_algorithm": "sha256",
                "sha256": capture_hash,
                "format": capture_format,
                "json_document_count": len(documents),
            },
            "match": {
                "strategy": "exact_variation_filename",
                "matching_occurrence_count": occurrence_counts[recording.name],
                "unique_canonical_record_count": len(unique),
            },
            **projection,
            "extraction_provenance": {
                "generator": "provider.brainfm",
                "generator_version": EXTRACTOR_VERSION,
                "sensitive_url_policy": "omit_all_provider_urls_and_tokens",
            },
        }
        validate_provider_sidecar(sidecar)
        results.append((provider_sidecar_path_for(recording), sidecar))
    return results


def _capture_key(capture_path: Path) -> str:
    name = capture_path.name
    for suffix in (".json", ".har"):
        if name.lower().endswith(suffix):
            return name[: -len(suffix)]
    return name


def _is_capture_candidate(path: Path) -> bool:
    lowered = path.name.lower()
    if path.name.startswith("."):
        return False
    if lowered.endswith(
        (
            ".png",
            ".jpg",
            ".jpeg",
            ".gif",
            ".webp",
            ".metadata.json",
            ".provider.json",
        )
    ):
        return False
    return path.is_file()


def extract_brainfm_capture_tree(
    captures_root: Path,
    recordings_root: Path,
) -> list[ProviderBatchEntry]:
    """Validate a capture tree and prepare deterministic provider sidecars.

    Capture basenames are joined to audio stems globally so a broad capture folder
    can safely feed a more specific corpus taxonomy. Every candidate is still
    verified against the exact provider variation filename inside the payload.
    """
    if not captures_root.is_dir():
        raise ProviderMetadataError(f"captures root is not a directory: {captures_root}")
    if not recordings_root.is_dir():
        raise ProviderMetadataError(
            f"recordings root is not a directory: {recordings_root}"
        )

    recordings = sorted(
        path
        for path in recordings_root.rglob("*")
        if path.is_file() and path.suffix.lower() in AUDIO_EXTENSIONS
    )
    by_stem: dict[str, list[Path]] = defaultdict(list)
    for recording in recordings:
        by_stem[recording.stem].append(recording)

    captures = sorted(
        path for path in captures_root.rglob("*") if _is_capture_candidate(path)
    )
    by_key: dict[str, list[Path]] = defaultdict(list)
    for capture in captures:
        by_key[_capture_key(capture)].append(capture)

    entries: list[ProviderBatchEntry] = []
    paired_recordings: set[Path] = set()
    for key in sorted(by_key):
        capture_group = by_key[key]
        matched_recordings = by_stem.get(key, [])
        if len(capture_group) > 1:
            for capture in capture_group:
                entries.append(
                    ProviderBatchEntry(
                        status="ambiguous_capture",
                        capture_path=capture,
                        message=f"multiple captures share basename: {key}",
                    )
                )
            continue
        capture = capture_group[0]
        if not matched_recordings:
            entries.append(
                ProviderBatchEntry(
                    status="unmatched_capture",
                    capture_path=capture,
                    message=f"no local audio has stem: {key}",
                )
            )
            continue
        try:
            sidecars = _extract_brainfm_sidecars_for_recordings(
                capture, matched_recordings
            )
        except (OSError, UnicodeError, ProviderMetadataError) as error:
            entries.append(
                ProviderBatchEntry(
                    status="invalid_capture",
                    capture_path=capture,
                    message=str(error),
                )
            )
            continue
        for (output_path, sidecar), recording in zip(
            sidecars, matched_recordings, strict=True
        ):
            paired_recordings.add(recording)
            status = "ready"
            message = None
            if output_path.exists():
                try:
                    existing = json.loads(output_path.read_text())
                    validate_provider_sidecar(existing)
                    if existing == sidecar:
                        status = "unchanged"
                    else:
                        status = "stale_sidecar"
                        message = "existing sidecar differs; use overwrite to replace it"
                except (OSError, json.JSONDecodeError, ProviderMetadataError) as error:
                    status = "stale_sidecar"
                    message = f"existing sidecar is invalid: {error}"
            entries.append(
                ProviderBatchEntry(
                    status=status,
                    recording_path=recording,
                    capture_path=capture,
                    output_path=output_path,
                    sidecar=sidecar,
                    message=message,
                )
            )

    for recording in recordings:
        if recording in paired_recordings:
            continue
        output_path = provider_sidecar_path_for(recording)
        status = "existing_sidecar" if output_path.exists() else "missing_capture"
        entries.append(
            ProviderBatchEntry(
                status=status,
                recording_path=recording,
                output_path=output_path if output_path.exists() else None,
                message=None if output_path.exists() else "no capture basename matched",
            )
        )
    return sorted(
        entries,
        key=lambda item: (
            str(item.recording_path or ""),
            str(item.capture_path or ""),
            item.status,
        ),
    )


def write_brainfm_capture_tree(
    entries: list[ProviderBatchEntry],
    *,
    overwrite: bool = False,
) -> list[Path]:
    writable_statuses = {"ready"}
    if overwrite:
        writable_statuses.add("stale_sidecar")
    sidecars = [
        (entry.output_path, entry.sidecar)
        for entry in entries
        if entry.status in writable_statuses
        and entry.output_path is not None
        and entry.sidecar is not None
    ]
    return write_provider_sidecars(sidecars)


def write_provider_sidecars(
    sidecars: list[tuple[Path, dict[str, Any]]],
) -> list[Path]:
    paths = []
    for output_path, sidecar in sidecars:
        validate_provider_sidecar(sidecar)
        output_path.write_text(json.dumps(sidecar, indent=2, sort_keys=True) + "\n")
        paths.append(output_path)
    return paths
