from __future__ import annotations

import hashlib
import json
import math
import re
import statistics
from pathlib import Path
from typing import Any

import soundfile as sf

from core.hashing import sha256_file


TRANSCRIPT_SIDECAR_SCHEMA_VERSION = "1.0.0"
IMPORTER_VERSION = "1.0.0"
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
AWS_REGION_PATTERN = re.compile(r"^[a-z]{2}(?:-gov)?-[a-z]+-\d+$")
FORBIDDEN_KEYS = {
    "account",
    "account_id",
    "accountid",
    "bucket",
    "content",
    "job_name",
    "jobname",
    "media_file_uri",
    "s3_uri",
    "transcript",
    "transcript_file_uri",
    "uri",
    "url",
}


class TranscriptSidecarError(ValueError):
    """Raised when transcript data cannot be normalized or validated safely."""


def transcript_sidecar_path_for(recording_path: Path) -> Path:
    return recording_path.with_name(f"{recording_path.name}.transcript.json")


def _number(value: Any, field: str) -> float:
    if isinstance(value, bool):
        raise TranscriptSidecarError(f"{field} must be numeric")
    try:
        result = float(value)
    except (TypeError, ValueError) as error:
        raise TranscriptSidecarError(f"{field} must be numeric") from error
    if not math.isfinite(result):
        raise TranscriptSidecarError(f"{field} must be finite")
    return result


def _nonnegative_number(value: Any, field: str) -> float:
    result = _number(value, field)
    if result < 0:
        raise TranscriptSidecarError(f"{field} cannot be negative")
    return result


def _confidence(item: dict[str, Any], field: str) -> float:
    alternatives = item.get("alternatives")
    if not isinstance(alternatives, list) or not alternatives:
        raise TranscriptSidecarError(f"{field}.alternatives must not be empty")
    alternative = alternatives[0]
    if not isinstance(alternative, dict):
        raise TranscriptSidecarError(f"{field}.alternatives[0] must be an object")
    score = _number(alternative.get("confidence"), f"{field}.confidence")
    if not 0 <= score <= 1:
        raise TranscriptSidecarError(f"{field}.confidence must be within 0..1")
    return score


def _merge_intervals(intervals: list[tuple[float, float]]) -> list[tuple[float, float]]:
    merged: list[list[float]] = []
    for start, end in sorted(intervals):
        if not merged or start > merged[-1][1]:
            merged.append([start, end])
        else:
            merged[-1][1] = max(merged[-1][1], end)
    return [(start, end) for start, end in merged]


def _content_digest(transcripts: list[dict[str, Any]]) -> tuple[str, int]:
    values = []
    for index, item in enumerate(transcripts):
        if not isinstance(item, dict) or not isinstance(item.get("transcript"), str):
            raise TranscriptSidecarError(
                f"results.transcripts[{index}].transcript must be text"
            )
        values.append(item["transcript"])
    if not values:
        raise TranscriptSidecarError("results.transcripts must not be empty")
    content = "\n".join(values)
    return hashlib.sha256(content.encode("utf-8")).hexdigest(), len(content)


def _reject_private_content(value: Any, path: str = "root") -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            if key.lower() in FORBIDDEN_KEYS:
                raise TranscriptSidecarError(f"private field is forbidden: {path}.{key}")
            _reject_private_content(nested, f"{path}.{key}")
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            _reject_private_content(nested, f"{path}[{index}]")
    elif isinstance(value, str):
        lowered = value.lower()
        if lowered.startswith(("s3://", "http://", "https://")):
            raise TranscriptSidecarError(f"private location is forbidden: {path}")


def import_aws_transcribe(
    raw_response_path: Path,
    recording_path: Path,
    *,
    region: str,
    language_code: str,
    media_format: str,
    media_sample_rate_hz: int,
    model_name: str | None = None,
    created_at: str | None = None,
    started_at: str | None = None,
    completed_at: str | None = None,
    timestamp_timezone: str | None = None,
) -> dict[str, Any]:
    if not AWS_REGION_PATTERN.fullmatch(region):
        raise TranscriptSidecarError("AWS region is invalid")
    try:
        document = json.loads(raw_response_path.read_text())
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise TranscriptSidecarError(f"invalid AWS transcript JSON: {error}") from error
    if not isinstance(document, dict) or document.get("status") != "COMPLETED":
        raise TranscriptSidecarError("AWS transcription status must be COMPLETED")
    results = document.get("results")
    if not isinstance(results, dict):
        raise TranscriptSidecarError("AWS transcript results must be an object")
    items = results.get("items")
    segments = results.get("audio_segments")
    transcripts = results.get("transcripts")
    if not isinstance(items, list) or not isinstance(segments, list):
        raise TranscriptSidecarError("AWS transcript requires items and audio_segments")
    if not isinstance(transcripts, list):
        raise TranscriptSidecarError("AWS transcript requires transcripts")

    transcript_sha256, transcript_character_count = _content_digest(transcripts)
    item_lookup: dict[Any, dict[str, Any]] = {}
    pronunciation_items = []
    pronunciation_confidences = []
    punctuation_count = 0
    untimed_pronunciation_count = 0
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise TranscriptSidecarError(f"results.items[{index}] must be an object")
        item_id = item.get("id")
        if item_id in item_lookup:
            raise TranscriptSidecarError(f"duplicate AWS item id: {item_id}")
        item_lookup[item_id] = item
        item_type = item.get("type")
        if item_type == "punctuation":
            punctuation_count += 1
            continue
        if item_type != "pronunciation":
            raise TranscriptSidecarError(f"unsupported AWS item type: {item_type}")
        score = _confidence(item, f"results.items[{index}]")
        pronunciation_confidences.append(score)
        if "start_time" not in item or "end_time" not in item:
            untimed_pronunciation_count += 1
            continue
        start = _nonnegative_number(item["start_time"], f"results.items[{index}].start")
        end = _nonnegative_number(item["end_time"], f"results.items[{index}].end")
        if end < start:
            raise TranscriptSidecarError(f"results.items[{index}] ends before it starts")
        pronunciation_items.append(
            {
                "item_id": item_id,
                "start_seconds": start,
                "end_seconds": end,
                "confidence": score,
            }
        )

    speech_segments = []
    segment_intervals = []
    previous_end = 0.0
    for index, segment in enumerate(segments):
        if not isinstance(segment, dict):
            raise TranscriptSidecarError(
                f"results.audio_segments[{index}] must be an object"
            )
        start = _nonnegative_number(
            segment.get("start_time"), f"results.audio_segments[{index}].start"
        )
        end = _nonnegative_number(
            segment.get("end_time"), f"results.audio_segments[{index}].end"
        )
        if end < start or start < previous_end:
            raise TranscriptSidecarError("AWS audio segments must be ordered and non-overlapping")
        previous_end = end
        segment_ids = segment.get("items")
        if not isinstance(segment_ids, list):
            raise TranscriptSidecarError(
                f"results.audio_segments[{index}].items must be a list"
            )
        segment_scores = []
        timed_count = 0
        for item_id in segment_ids:
            if item_id not in item_lookup:
                raise TranscriptSidecarError(
                    f"audio segment references unknown item id: {item_id}"
                )
            item = item_lookup[item_id]
            if item.get("type") == "pronunciation":
                segment_scores.append(_confidence(item, f"item {item_id}"))
                if "start_time" in item and "end_time" in item:
                    timed_count += 1
        speech_segments.append(
            {
                "segment_id": segment.get("id"),
                "start_seconds": start,
                "end_seconds": end,
                "timed_pronunciation_count": timed_count,
                "mean_confidence": (
                    round(statistics.fmean(segment_scores), 6)
                    if segment_scores
                    else None
                ),
                "minimum_confidence": min(segment_scores) if segment_scores else None,
            }
        )
        segment_intervals.append((start, end))

    info = sf.info(recording_path)
    recording_duration = float(info.duration)
    if media_sample_rate_hz != info.samplerate:
        raise TranscriptSidecarError(
            "declared media sample rate does not match the recording"
        )
    if media_format.lower().lstrip(".") != recording_path.suffix.lower().lstrip("."):
        raise TranscriptSidecarError("declared media format does not match the recording")
    if segment_intervals and segment_intervals[-1][1] > recording_duration + 0.25:
        raise TranscriptSidecarError("speech timeline exceeds recording duration")
    merged = _merge_intervals(segment_intervals)
    speech_duration = sum(end - start for start, end in merged)

    sidecar = {
        "transcript_sidecar_schema_version": TRANSCRIPT_SIDECAR_SCHEMA_VERSION,
        "recording": {
            "filename": recording_path.name,
            "hash_algorithm": "sha256",
            "sha256": sha256_file(recording_path),
            "size_bytes": recording_path.stat().st_size,
            "duration_seconds": round(recording_duration, 6),
        },
        "raw_transcript": {
            "filename": raw_response_path.name,
            "format": "aws_transcribe_json",
            "hash_algorithm": "sha256",
            "sha256": sha256_file(raw_response_path),
            "size_bytes": raw_response_path.stat().st_size,
            "verbatim_content_sha256": transcript_sha256,
            "storage_policy": "ignored_private_capture",
        },
        "transcription_engine": {
            "provider": "aws",
            "service": "amazon_transcribe",
            "region": region,
            "language_code": language_code,
            "language_identification_mode": "specific_language",
            "model_kind": "custom" if model_name else "standard",
            "model_name": model_name,
        },
        "job_configuration": {
            "media_format": media_format,
            "media_sample_rate_hz": media_sample_rate_hz,
            "audio_identification": False,
            "alternative_results": False,
            "custom_vocabulary": None,
            "pii_redaction": False,
            "vocabulary_filter": None,
            "toxicity_detection": False,
            "speaker_labels": False,
            "channel_identification": False,
        },
        "job_timing": {
            "created_at": created_at,
            "started_at": started_at,
            "completed_at": completed_at,
            "timezone": timestamp_timezone,
        },
        "speech_timeline": {
            "timebase": "seconds_from_recording_start",
            "segments": speech_segments,
            "pronunciation_items": pronunciation_items,
        },
        "statistics": {
            "transcript_character_count": transcript_character_count,
            "segment_count": len(speech_segments),
            "pronunciation_count": len(pronunciation_confidences),
            "timed_pronunciation_count": len(pronunciation_items),
            "untimed_pronunciation_count": untimed_pronunciation_count,
            "punctuation_count": punctuation_count,
            "mean_pronunciation_confidence": (
                round(statistics.fmean(pronunciation_confidences), 6)
                if pronunciation_confidences
                else None
            ),
            "minimum_pronunciation_confidence": (
                min(pronunciation_confidences)
                if pronunciation_confidences
                else None
            ),
            "maximum_pronunciation_confidence": (
                max(pronunciation_confidences)
                if pronunciation_confidences
                else None
            ),
            "speech_start_seconds": segment_intervals[0][0] if segment_intervals else None,
            "speech_end_seconds": segment_intervals[-1][1] if segment_intervals else None,
            "speech_duration_seconds": round(speech_duration, 6),
            "speech_coverage_ratio": round(speech_duration / recording_duration, 6),
        },
        "content_policy": {
            "sidecar_contains_verbatim_text": False,
            "sidecar_contains_provider_account_identifiers": False,
            "sidecar_contains_cloud_storage_locations": False,
            "verbatim_text_location": "ignored_private_capture_only",
        },
        "extraction_provenance": {
            "generator": "transcripts.sidecar",
            "generator_version": IMPORTER_VERSION,
            "importer": "aws_transcribe",
        },
    }
    validate_transcript_sidecar(sidecar)
    return sidecar


def _require_digest(value: Any, field: str) -> None:
    if not isinstance(value, str) or not SHA256_PATTERN.fullmatch(value):
        raise TranscriptSidecarError(f"{field} must be a SHA-256 digest")


def _require_positive(value: Any, field: str, *, allow_zero: bool = False) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TranscriptSidecarError(f"{field} must be numeric")
    if not math.isfinite(value) or (value < 0 if allow_zero else value <= 0):
        qualifier = "nonnegative" if allow_zero else "positive"
        raise TranscriptSidecarError(f"{field} must be {qualifier}")


def validate_transcript_sidecar(sidecar: dict[str, Any]) -> None:
    required = {
        "transcript_sidecar_schema_version",
        "recording",
        "raw_transcript",
        "transcription_engine",
        "job_configuration",
        "job_timing",
        "speech_timeline",
        "statistics",
        "content_policy",
        "extraction_provenance",
    }
    if not isinstance(sidecar, dict) or required - sidecar.keys():
        missing = required - sidecar.keys() if isinstance(sidecar, dict) else required
        raise TranscriptSidecarError(
            f"missing required fields: {', '.join(sorted(missing))}"
        )
    if sidecar["transcript_sidecar_schema_version"] != TRANSCRIPT_SIDECAR_SCHEMA_VERSION:
        raise TranscriptSidecarError("unsupported transcript_sidecar_schema_version")

    recording = sidecar["recording"]
    if not isinstance(recording.get("filename"), str) or not recording["filename"]:
        raise TranscriptSidecarError("recording.filename must be non-empty text")
    if Path(recording["filename"]).name != recording["filename"]:
        raise TranscriptSidecarError("recording.filename cannot contain a path")
    _require_digest(recording.get("sha256"), "recording.sha256")
    if recording.get("hash_algorithm") != "sha256":
        raise TranscriptSidecarError("recording.hash_algorithm must be sha256")
    _require_positive(recording.get("size_bytes"), "recording.size_bytes")
    _require_positive(recording.get("duration_seconds"), "recording.duration_seconds")

    raw = sidecar["raw_transcript"]
    if not isinstance(raw.get("filename"), str) or not raw["filename"]:
        raise TranscriptSidecarError("raw_transcript.filename must be non-empty text")
    if Path(raw["filename"]).name != raw["filename"]:
        raise TranscriptSidecarError("raw_transcript.filename cannot contain a path")
    if not isinstance(raw.get("format"), str) or not raw["format"]:
        raise TranscriptSidecarError("raw_transcript.format is required")
    if raw.get("storage_policy") != "ignored_private_capture":
        raise TranscriptSidecarError("raw transcript must remain private")
    if raw.get("hash_algorithm") != "sha256":
        raise TranscriptSidecarError("raw_transcript.hash_algorithm must be sha256")
    for field in ("sha256", "verbatim_content_sha256"):
        _require_digest(raw.get(field), f"raw_transcript.{field}")
    _require_positive(raw.get("size_bytes"), "raw_transcript.size_bytes")

    engine = sidecar["transcription_engine"]
    for field in ("provider", "service", "language_code"):
        if not isinstance(engine.get(field), str) or not engine[field]:
            raise TranscriptSidecarError(f"transcription_engine.{field} is required")
    region = engine.get("region")
    if region is not None and (not isinstance(region, str) or not region):
        raise TranscriptSidecarError("transcription_engine.region is invalid")
    if engine.get("model_kind") not in {"standard", "custom", "unknown"}:
        raise TranscriptSidecarError("transcription_engine.model_kind is invalid")

    configuration = sidecar["job_configuration"]
    if not isinstance(configuration, dict):
        raise TranscriptSidecarError("job_configuration must be an object")
    if not isinstance(configuration.get("media_format"), str) or not configuration[
        "media_format"
    ]:
        raise TranscriptSidecarError("job_configuration.media_format is required")
    _require_positive(
        configuration.get("media_sample_rate_hz"),
        "job_configuration.media_sample_rate_hz",
    )

    timing = sidecar["job_timing"]
    if not isinstance(timing, dict):
        raise TranscriptSidecarError("job_timing must be an object")
    for field in ("created_at", "started_at", "completed_at", "timezone"):
        value = timing.get(field)
        if value is not None and (not isinstance(value, str) or not value):
            raise TranscriptSidecarError(f"job_timing.{field} is invalid")

    timeline = sidecar["speech_timeline"]
    if timeline.get("timebase") != "seconds_from_recording_start":
        raise TranscriptSidecarError("unsupported speech timeline timebase")
    duration = recording["duration_seconds"]
    for collection_name in ("segments", "pronunciation_items"):
        collection = timeline.get(collection_name)
        if not isinstance(collection, list):
            raise TranscriptSidecarError(f"speech_timeline.{collection_name} must be a list")
        previous_start = -1.0
        for index, item in enumerate(collection):
            if not isinstance(item, dict):
                raise TranscriptSidecarError(
                    f"speech_timeline.{collection_name}[{index}] must be an object"
                )
            start = item.get("start_seconds")
            end = item.get("end_seconds")
            _require_positive(start, f"{collection_name}[{index}].start", allow_zero=True)
            _require_positive(end, f"{collection_name}[{index}].end", allow_zero=True)
            if end < start or end > duration + 0.25 or start < previous_start:
                raise TranscriptSidecarError(f"invalid {collection_name} timeline")
            previous_start = start
            confidence = item.get("confidence", item.get("mean_confidence"))
            if confidence is not None and (
                not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1
            ):
                raise TranscriptSidecarError(f"invalid {collection_name} confidence")

    statistics_block = sidecar["statistics"]
    if statistics_block.get("segment_count") != len(timeline["segments"]):
        raise TranscriptSidecarError("statistics.segment_count does not match timeline")
    if statistics_block.get("timed_pronunciation_count") != len(
        timeline["pronunciation_items"]
    ):
        raise TranscriptSidecarError(
            "statistics.timed_pronunciation_count does not match timeline"
        )
    coverage = statistics_block.get("speech_coverage_ratio")
    if not isinstance(coverage, (int, float)) or not 0 <= coverage <= 1:
        raise TranscriptSidecarError("statistics.speech_coverage_ratio must be within 0..1")

    policy = sidecar["content_policy"]
    if policy != {
        "sidecar_contains_verbatim_text": False,
        "sidecar_contains_provider_account_identifiers": False,
        "sidecar_contains_cloud_storage_locations": False,
        "verbatim_text_location": "ignored_private_capture_only",
    }:
        raise TranscriptSidecarError("content_policy does not enforce private text storage")
    _reject_private_content(sidecar)


def write_transcript_sidecar(
    sidecar: dict[str, Any],
    recording_path: Path,
    *,
    overwrite: bool = False,
) -> tuple[Path, str]:
    validate_transcript_sidecar(sidecar)
    output_path = transcript_sidecar_path_for(recording_path)
    serialized = json.dumps(sidecar, indent=2, sort_keys=True) + "\n"
    if output_path.exists():
        if output_path.read_text() == serialized:
            return output_path, "unchanged"
        if not overwrite:
            raise TranscriptSidecarError(
                f"existing transcript sidecar differs: {output_path}; use overwrite to replace it"
            )
    output_path.write_text(serialized)
    return output_path, "written"
