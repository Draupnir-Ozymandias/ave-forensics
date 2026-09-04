from __future__ import annotations

from collections import Counter
from statistics import median
from typing import Any

from analysis.protocol_tracker import build_protocol_tracks
from transcripts.sidecar import validate_transcript_sidecar


SPEECH_CONTEXT_SCHEMA_VERSION = "1.0.0"
CONTEXTS = ("speech_active", "mixed", "speech_sparse")


def merge_intervals(
    intervals: list[tuple[float, float]],
    *,
    duration_seconds: float,
    padding_seconds: float = 0.5,
) -> list[tuple[float, float]]:
    """Pad, clamp, sort, and merge transcript speech intervals."""
    if duration_seconds <= 0:
        raise ValueError("duration_seconds must be positive")
    if padding_seconds < 0:
        raise ValueError("padding_seconds cannot be negative")

    padded = []
    for start, end in intervals:
        if start < 0 or end < start or end > duration_seconds + 0.25:
            raise ValueError("invalid speech interval")
        padded.append(
            (
                max(0.0, start - padding_seconds),
                min(duration_seconds, end + padding_seconds),
            )
        )

    merged: list[list[float]] = []
    for start, end in sorted(padded):
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return [(round(start, 6), round(end, 6)) for start, end in merged]


def complement_intervals(
    intervals: list[tuple[float, float]], duration_seconds: float
) -> list[tuple[float, float]]:
    """Return regions outside a normalized interval collection."""
    complement = []
    cursor = 0.0
    for start, end in intervals:
        if start > cursor:
            complement.append((round(cursor, 6), round(start, 6)))
        cursor = max(cursor, end)
    if cursor < duration_seconds:
        complement.append((round(cursor, 6), round(duration_seconds, 6)))
    return complement


def interval_overlap_seconds(
    start: float,
    end: float,
    intervals: list[tuple[float, float]],
) -> float:
    return sum(
        max(0.0, min(end, interval_end) - max(start, interval_start))
        for interval_start, interval_end in intervals
    )


def classify_windows(
    timeline: list[dict[str, Any]],
    speech_intervals: list[tuple[float, float]],
    *,
    active_minimum_overlap: float = 0.5,
    sparse_maximum_overlap: float = 0.1,
) -> list[dict[str, Any]]:
    """Add text-free speech overlap and context labels to analysis windows."""
    if not 0 <= sparse_maximum_overlap < active_minimum_overlap <= 1:
        raise ValueError("speech overlap thresholds must satisfy 0 <= sparse < active <= 1")

    classified = []
    for item in timeline:
        start = float(item["start_seconds"])
        end = float(item["end_seconds"])
        if end <= start:
            raise ValueError("analysis windows must have positive duration")
        ratio = interval_overlap_seconds(start, end, speech_intervals) / (end - start)
        if ratio >= active_minimum_overlap:
            context = "speech_active"
        elif ratio <= sparse_maximum_overlap:
            context = "speech_sparse"
        else:
            context = "mixed"
        classified.append(
            {
                **item,
                "speech_overlap_ratio": round(ratio, 6),
                "speech_context": context,
            }
        )
    return classified


def _base_summary(items: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "window_count": len(items),
        "median_speech_overlap_ratio": (
            round(median(item["speech_overlap_ratio"] for item in items), 6)
            if items
            else None
        ),
    }


def _entrainment_summary(items: list[dict[str, Any]]) -> dict[str, Any]:
    summary = _base_summary(items)
    candidates = [item["top_candidate"] for item in items if item.get("top_candidate")]
    band_counts = Counter(item["brainwave_band"] for item in candidates)
    dominant_band, dominant_count = band_counts.most_common(1)[0] if band_counts else (None, 0)
    dominant_candidates = [
        item for item in candidates if item["brainwave_band"] == dominant_band
    ]
    summary.update(
        {
            "candidate_window_count": len(candidates),
            "candidate_window_rate": round(len(candidates) / len(items), 6) if items else None,
            "median_difference_hz": (
                round(median(float(item["difference_hz"]) for item in candidates), 6)
                if candidates
                else None
            ),
            "median_confidence": (
                round(median(float(item["confidence"]) for item in candidates), 6)
                if candidates
                else None
            ),
            "brainwave_band_counts": dict(sorted(band_counts.items())),
            "dominant_brainwave_band": dominant_band,
            "dominant_band_coverage": (
                round(dominant_count / len(candidates), 6) if candidates else None
            ),
            "dominant_band_median_difference_hz": (
                round(
                    median(float(item["difference_hz"]) for item in dominant_candidates),
                    6,
                )
                if dominant_candidates
                else None
            ),
        }
    )
    return summary


def _compact_track(track: dict[str, Any]) -> dict[str, Any]:
    return {
        "start_seconds": track["start_seconds"],
        "end_seconds": track["end_seconds"],
        "duration_seconds": track["duration_seconds"],
        "average_difference_hz": track["average_difference_hz"],
        "brainwave_band": track["brainwave_band"],
        "average_confidence": track["average_confidence"],
        "frequency_stability": track["frequency_stability"],
        "window_count": track["window_count"],
        "score": track["score"],
    }


def _summarize_entrainment_timeline(
    timeline: list[dict[str, Any]],
    speech_intervals: list[tuple[float, float]],
    *,
    active_minimum_overlap: float,
    sparse_maximum_overlap: float,
) -> dict[str, Any]:
    classified = classify_windows(
        timeline,
        speech_intervals,
        active_minimum_overlap=active_minimum_overlap,
        sparse_maximum_overlap=sparse_maximum_overlap,
    )
    summaries = {}
    for context in CONTEXTS:
        context_items = [
            item for item in classified if item["speech_context"] == context
        ]
        summary = _entrainment_summary(context_items)
        masked_timeline = [
            {
                **item,
                "candidates": item.get("candidates", [])
                if item["speech_context"] == context
                else [],
            }
            for item in classified
        ]
        tracks = build_protocol_tracks(masked_timeline)
        summary["persistent_track_count"] = len(tracks)
        summary["top_persistent_track"] = _compact_track(tracks[0]) if tracks else None
        summaries[context] = summary
    return summaries


def _envelope_summary(items: list[dict[str, Any]]) -> dict[str, Any]:
    summary = _base_summary(items)
    dominant = [item["dominant_modulation"] for item in items if item.get("dominant_modulation")]
    summary.update(
        {
            "dominant_window_count": len(dominant),
            "dominant_window_rate": round(len(dominant) / len(items), 6) if items else None,
            "median_modulation_hz": (
                round(median(float(item["modulation_hz"]) for item in dominant), 6)
                if dominant
                else None
            ),
            "median_relative_power": (
                round(median(float(item["relative_power"]) for item in dominant), 6)
                if dominant
                else None
            ),
            "median_modulation_depth": (
                round(median(float(item["modulation_depth"]) for item in items), 6)
                if items
                else None
            ),
        }
    )
    return summary


def _phase_summary(items: list[dict[str, Any]]) -> dict[str, Any]:
    summary = _base_summary(items)
    behaviors = Counter(item["phase_behavior"] for item in items)
    dominant_behavior, dominant_count = behaviors.most_common(1)[0] if behaviors else (None, 0)
    summary.update(
        {
            "behavior_counts": dict(sorted(behaviors.items())),
            "dominant_behavior": dominant_behavior,
            "dominant_behavior_coverage": (
                round(dominant_count / len(items), 6) if items else None
            ),
            "median_difference_hz": (
                round(median(float(item["estimated_difference_hz"]) for item in items), 6)
                if items
                else None
            ),
            "median_detrended_phase_locking": (
                round(
                    median(float(item["detrended_phase_locking_value"]) for item in items),
                    6,
                )
                if items
                else None
            ),
        }
    )
    return summary


def _summarize_timeline(
    timeline: list[dict[str, Any]],
    speech_intervals: list[tuple[float, float]],
    summarizer: Any,
    *,
    active_minimum_overlap: float,
    sparse_maximum_overlap: float,
) -> dict[str, Any]:
    classified = classify_windows(
        timeline,
        speech_intervals,
        active_minimum_overlap=active_minimum_overlap,
        sparse_maximum_overlap=sparse_maximum_overlap,
    )
    return {
        context: summarizer(
            [item for item in classified if item["speech_context"] == context]
        )
        for context in CONTEXTS
    }


def _difference(active: Any, sparse: Any) -> float | None:
    if active is None or sparse is None:
        return None
    return round(float(active) - float(sparse), 6)


def build_speech_context_analysis(
    *,
    transcript_sidecar: dict[str, Any],
    duration_seconds: float,
    entrainment_timeline: list[dict[str, Any]],
    left_envelope_timeline: list[dict[str, Any]] | None = None,
    right_envelope_timeline: list[dict[str, Any]] | None = None,
    phase_timeline: list[dict[str, Any]] | None = None,
    padding_seconds: float = 0.5,
    active_minimum_overlap: float = 0.5,
    sparse_maximum_overlap: float = 0.1,
) -> dict[str, Any]:
    """Compare existing AVE analysis windows by text-free speech context."""
    validate_transcript_sidecar(transcript_sidecar)
    declared_duration = float(transcript_sidecar["recording"]["duration_seconds"])
    if abs(declared_duration - duration_seconds) > 0.25:
        raise ValueError("transcript sidecar duration does not match analysis input")

    source_intervals = [
        (float(item["start_seconds"]), float(item["end_seconds"]))
        for item in transcript_sidecar["speech_timeline"]["segments"]
    ]
    speech_intervals = merge_intervals(
        source_intervals,
        duration_seconds=duration_seconds,
        padding_seconds=padding_seconds,
    )
    sparse_intervals = complement_intervals(speech_intervals, duration_seconds)
    buffered_speech_duration = sum(end - start for start, end in speech_intervals)

    analyses: dict[str, Any] = {
        "entrainment": _summarize_entrainment_timeline(
            entrainment_timeline,
            speech_intervals,
            active_minimum_overlap=active_minimum_overlap,
            sparse_maximum_overlap=sparse_maximum_overlap,
        )
    }
    if left_envelope_timeline is not None and right_envelope_timeline is not None:
        analyses["envelope"] = {
            "left": _summarize_timeline(
                left_envelope_timeline,
                speech_intervals,
                _envelope_summary,
                active_minimum_overlap=active_minimum_overlap,
                sparse_maximum_overlap=sparse_maximum_overlap,
            ),
            "right": _summarize_timeline(
                right_envelope_timeline,
                speech_intervals,
                _envelope_summary,
                active_minimum_overlap=active_minimum_overlap,
                sparse_maximum_overlap=sparse_maximum_overlap,
            ),
        }
    if phase_timeline is not None:
        analyses["phase"] = _summarize_timeline(
            phase_timeline,
            speech_intervals,
            _phase_summary,
            active_minimum_overlap=active_minimum_overlap,
            sparse_maximum_overlap=sparse_maximum_overlap,
        )

    active = analyses["entrainment"]["speech_active"]
    sparse = analyses["entrainment"]["speech_sparse"]
    active_track = active["top_persistent_track"] or {}
    sparse_track = sparse["top_persistent_track"] or {}
    comparison = {
        "candidate_rate_difference_active_minus_sparse": _difference(
            active["candidate_window_rate"], sparse["candidate_window_rate"]
        ),
        "median_difference_hz_active_minus_sparse": _difference(
            active["median_difference_hz"], sparse["median_difference_hz"]
        ),
        "direct_comparison_available": bool(
            active["window_count"] and sparse["window_count"]
        ),
        "active_persistent_difference_hz": active_track.get(
            "average_difference_hz"
        ),
        "active_persistent_band": active_track.get("brainwave_band"),
        "active_persistent_score": active_track.get("score"),
        "sparse_persistent_difference_hz": sparse_track.get(
            "average_difference_hz"
        ),
        "sparse_persistent_band": sparse_track.get("brainwave_band"),
        "sparse_persistent_score": sparse_track.get("score"),
    }

    return {
        "speech_context_schema_version": SPEECH_CONTEXT_SCHEMA_VERSION,
        "recording": {
            "filename": transcript_sidecar["recording"]["filename"],
            "sha256": transcript_sidecar["recording"]["sha256"],
            "duration_seconds": duration_seconds,
        },
        "transcript_binding": {
            "sidecar_schema_version": transcript_sidecar[
                "transcript_sidecar_schema_version"
            ],
            "raw_response_sha256": transcript_sidecar["raw_transcript"]["sha256"],
            "verbatim_content_sha256": transcript_sidecar["raw_transcript"][
                "verbatim_content_sha256"
            ],
            "contains_verbatim_text": False,
        },
        "configuration": {
            "padding_seconds": padding_seconds,
            "active_minimum_overlap": active_minimum_overlap,
            "sparse_maximum_overlap": sparse_maximum_overlap,
            "classification": (
                "speech_active when overlap >= active threshold; speech_sparse when "
                "overlap <= sparse threshold; otherwise mixed"
            ),
        },
        "regions": {
            "speech_active": {
                "interval_count": len(speech_intervals),
                "duration_seconds": round(buffered_speech_duration, 6),
                "coverage_ratio": round(buffered_speech_duration / duration_seconds, 6),
                "intervals": [
                    {"start_seconds": start, "end_seconds": end}
                    for start, end in speech_intervals
                ],
            },
            "speech_sparse": {
                "interval_count": len(sparse_intervals),
                "duration_seconds": round(duration_seconds - buffered_speech_duration, 6),
                "coverage_ratio": round(
                    (duration_seconds - buffered_speech_duration) / duration_seconds, 6
                ),
                "intervals": [
                    {"start_seconds": start, "end_seconds": end}
                    for start, end in sparse_intervals
                ],
            },
        },
        "window_analyses": analyses,
        "comparison": comparison,
        "limitations": [
            "Speech regions originate from transcription-provider segments, not sample-accurate source separation.",
            "Window overlap can mix narration and background audio; mixed windows are excluded from direct active-versus-sparse comparison.",
            "Observed persistence describes signal structure and does not establish listener response or efficacy.",
        ],
    }
