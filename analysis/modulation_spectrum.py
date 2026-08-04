from __future__ import annotations

from statistics import median
from typing import Any

import numpy as np


def extract_modulation_observations(
    envelope_timeline: list[dict[str, Any]],
    min_relative_power: float = 0.05,
    min_modulation_depth: float = 0.02,
    peaks_per_window: int = 3,
) -> list[dict[str, Any]]:
    """Convert envelope-spectrum peaks into window-level observations."""
    observations = []

    for item in envelope_timeline:
        modulation_depth = float(item.get("modulation_depth", 0.0))

        if modulation_depth < min_modulation_depth:
            continue

        for peak in item.get("modulation_peaks", [])[:peaks_per_window]:
            relative_power = float(peak["relative_power"])

            if relative_power < min_relative_power:
                continue

            observations.append(
                {
                    "window_index": int(item["window_index"]),
                    "start_seconds": float(item["start_seconds"]),
                    "end_seconds": float(item["end_seconds"]),
                    "modulation_hz": float(peak["modulation_hz"]),
                    "relative_power": relative_power,
                    "modulation_depth": modulation_depth,
                }
            )

    return observations


def _finalize_modulation_track(
    points: list[dict[str, Any]],
    total_windows: int,
    min_track_windows: int,
) -> dict[str, Any] | None:
    if len(points) < min_track_windows:
        return None

    frequencies = np.asarray(
        [point["modulation_hz"] for point in points],
        dtype=np.float64,
    )
    centers = np.asarray(
        [
            (point["start_seconds"] + point["end_seconds"]) / 2.0
            for point in points
        ],
        dtype=np.float64,
    )

    if len(points) >= 2 and np.ptp(centers) > 0:
        drift_hz_per_second = float(np.polyfit(centers, frequencies, 1)[0])
    else:
        drift_hz_per_second = 0.0

    first_window = points[0]["window_index"]
    last_window = points[-1]["window_index"]
    possible_windows = max(1, last_window - first_window + 1)
    continuity = len(points) / possible_windows
    coverage = len(points) / max(1, total_windows)
    frequency_span_hz = float(np.ptp(frequencies))

    if frequency_span_hz >= 0.5 and abs(drift_hz_per_second) >= 0.01:
        classification = "modulation_ramp"
    elif coverage >= 0.75:
        classification = "persistent_modulation"
    else:
        classification = "episodic_modulation"

    median_power = float(median(point["relative_power"] for point in points))
    median_depth = float(median(point["modulation_depth"] for point in points))
    evidence_score = coverage * continuity * median_power * median_depth

    return {
        "type": "modulation_track",
        "start_seconds": round(points[0]["start_seconds"], 3),
        "end_seconds": round(points[-1]["end_seconds"], 3),
        "duration_seconds": round(
            points[-1]["end_seconds"] - points[0]["start_seconds"],
            3,
        ),
        "window_count": len(points),
        "total_windows": total_windows,
        "coverage": round(coverage, 4),
        "continuity": round(continuity, 4),
        "average_modulation_hz": round(float(np.mean(frequencies)), 4),
        "median_modulation_hz": round(float(np.median(frequencies)), 4),
        "minimum_modulation_hz": round(float(np.min(frequencies)), 4),
        "maximum_modulation_hz": round(float(np.max(frequencies)), 4),
        "frequency_span_hz": round(frequency_span_hz, 4),
        "drift_hz_per_second": round(drift_hz_per_second, 6),
        "median_relative_power": round(median_power, 4),
        "median_modulation_depth": round(median_depth, 4),
        "classification": classification,
        "evidence_score": round(evidence_score, 4),
        "points": points,
    }


def build_modulation_tracks(
    envelope_timeline: list[dict[str, Any]],
    max_frequency_jump_hz: float = 1.0,
    max_gap_windows: int = 1,
    min_track_windows: int = 3,
    min_relative_power: float = 0.05,
    min_modulation_depth: float = 0.02,
    peaks_per_window: int = 3,
) -> list[dict[str, Any]]:
    """Associate modulation peaks across adjacent envelope windows."""
    if max_frequency_jump_hz <= 0:
        raise ValueError("max_frequency_jump_hz must be positive")

    if max_gap_windows < 0:
        raise ValueError("max_gap_windows cannot be negative")

    observations = extract_modulation_observations(
        envelope_timeline=envelope_timeline,
        min_relative_power=min_relative_power,
        min_modulation_depth=min_modulation_depth,
        peaks_per_window=peaks_per_window,
    )
    observations_by_window: dict[int, list[dict[str, Any]]] = {}

    for observation in observations:
        observations_by_window.setdefault(
            observation["window_index"],
            [],
        ).append(observation)

    active_tracks: list[list[dict[str, Any]]] = []
    finished_tracks: list[list[dict[str, Any]]] = []

    for item in envelope_timeline:
        window_index = int(item["window_index"])
        window_observations = sorted(
            observations_by_window.get(window_index, []),
            key=lambda observation: observation["relative_power"],
            reverse=True,
        )
        used_track_indices = set()

        for observation in window_observations:
            candidates = []

            for track_index, track in enumerate(active_tracks):
                if track_index in used_track_indices:
                    continue

                last_point = track[-1]
                gap = window_index - last_point["window_index"] - 1
                frequency_distance = abs(
                    observation["modulation_hz"]
                    - last_point["modulation_hz"]
                )

                if gap <= max_gap_windows and frequency_distance <= max_frequency_jump_hz:
                    candidates.append((frequency_distance, track_index))

            if candidates:
                _, selected_index = min(candidates)
                active_tracks[selected_index].append(observation)
                used_track_indices.add(selected_index)
            else:
                active_tracks.append([observation])
                used_track_indices.add(len(active_tracks) - 1)

        still_active = []

        for track in active_tracks:
            missed_windows = window_index - track[-1]["window_index"]

            if missed_windows > max_gap_windows + 1:
                finished_tracks.append(track)
            else:
                still_active.append(track)

        active_tracks = still_active

    finished_tracks.extend(active_tracks)

    finalized = []

    for points in finished_tracks:
        track = _finalize_modulation_track(
            points=points,
            total_windows=len(envelope_timeline),
            min_track_windows=min_track_windows,
        )

        if track is not None:
            finalized.append(track)

    return sorted(
        finalized,
        key=lambda track: (
            track["evidence_score"],
            track["coverage"],
            track["median_relative_power"],
        ),
        reverse=True,
    )


def associate_stereo_modulation_tracks(
    left_tracks: list[dict[str, Any]],
    right_tracks: list[dict[str, Any]],
    max_frequency_difference_hz: float = 0.25,
    min_overlap_ratio: float = 0.5,
) -> list[dict[str, Any]]:
    """Associate compatible modulation tracks across stereo channels."""
    candidates = []

    for left_index, left_track in enumerate(left_tracks):
        for right_index, right_track in enumerate(right_tracks):
            frequency_difference_hz = abs(
                left_track["median_modulation_hz"]
                - right_track["median_modulation_hz"]
            )

            if frequency_difference_hz > max_frequency_difference_hz:
                continue

            overlap_start = max(
                left_track["start_seconds"],
                right_track["start_seconds"],
            )
            overlap_end = min(
                left_track["end_seconds"],
                right_track["end_seconds"],
            )
            overlap_seconds = max(0.0, overlap_end - overlap_start)
            shorter_duration = min(
                left_track["duration_seconds"],
                right_track["duration_seconds"],
            )
            overlap_ratio = (
                overlap_seconds / shorter_duration
                if shorter_duration > 0
                else 0.0
            )

            if overlap_ratio < min_overlap_ratio:
                continue

            frequency_agreement = max(
                0.0,
                1.0
                - frequency_difference_hz / max_frequency_difference_hz,
            )
            shared_coverage = min(
                left_track["coverage"],
                right_track["coverage"],
            )
            shared_power = min(
                left_track["median_relative_power"],
                right_track["median_relative_power"],
            )
            confidence = (
                overlap_ratio
                * frequency_agreement
                * shared_coverage
                * shared_power
            )

            candidates.append(
                {
                    "type": "stereo_modulation_association",
                    "left_track_index": left_index,
                    "right_track_index": right_index,
                    "start_seconds": round(overlap_start, 3),
                    "end_seconds": round(overlap_end, 3),
                    "left_modulation_hz": left_track[
                        "median_modulation_hz"
                    ],
                    "right_modulation_hz": right_track[
                        "median_modulation_hz"
                    ],
                    "average_modulation_hz": round(
                        (
                            left_track["median_modulation_hz"]
                            + right_track["median_modulation_hz"]
                        )
                        / 2.0,
                        4,
                    ),
                    "frequency_difference_hz": round(
                        frequency_difference_hz,
                        4,
                    ),
                    "overlap_ratio": round(overlap_ratio, 4),
                    "shared_coverage": round(shared_coverage, 4),
                    "confidence": round(confidence, 4),
                }
            )

    selected = []
    used_left = set()
    used_right = set()

    for candidate in sorted(
        candidates,
        key=lambda item: item["confidence"],
        reverse=True,
    ):
        if candidate["left_track_index"] in used_left:
            continue
        if candidate["right_track_index"] in used_right:
            continue

        selected.append(candidate)
        used_left.add(candidate["left_track_index"])
        used_right.add(candidate["right_track_index"])

    return selected


def analyze_modulation_spectrum(
    left_timeline: list[dict[str, Any]],
    right_timeline: list[dict[str, Any]],
    max_frequency_jump_hz: float = 1.0,
    max_stereo_difference_hz: float = 0.25,
    min_track_windows: int = 3,
    min_relative_power: float = 0.05,
    min_modulation_depth: float = 0.02,
) -> dict[str, Any]:
    """Reconstruct persistent, episodic, and drifting modulation evidence."""
    left_tracks = build_modulation_tracks(
        envelope_timeline=left_timeline,
        max_frequency_jump_hz=max_frequency_jump_hz,
        min_track_windows=min_track_windows,
        min_relative_power=min_relative_power,
        min_modulation_depth=min_modulation_depth,
    )
    right_tracks = build_modulation_tracks(
        envelope_timeline=right_timeline,
        max_frequency_jump_hz=max_frequency_jump_hz,
        min_track_windows=min_track_windows,
        min_relative_power=min_relative_power,
        min_modulation_depth=min_modulation_depth,
    )
    stereo_associations = associate_stereo_modulation_tracks(
        left_tracks=left_tracks,
        right_tracks=right_tracks,
        max_frequency_difference_hz=max_stereo_difference_hz,
    )

    if stereo_associations:
        primary = stereo_associations[0]
        left_primary = left_tracks[primary["left_track_index"]]
        right_primary = right_tracks[primary["right_track_index"]]

        if (
            left_primary["classification"] == "modulation_ramp"
            or right_primary["classification"] == "modulation_ramp"
        ):
            classification = "shared_modulation_ramp"
        elif primary["shared_coverage"] >= 0.75:
            classification = "persistent_shared_amplitude_modulation"
        else:
            classification = "episodic_shared_amplitude_modulation"
    elif left_tracks or right_tracks:
        primary = None
        classification = "channel_specific_modulation"
    else:
        primary = None
        classification = "no_significant_modulation"

    return {
        "type": "modulation_spectrum_analysis",
        "classification": classification,
        "left_tracks": left_tracks,
        "right_tracks": right_tracks,
        "stereo_associations": stereo_associations,
        "primary_stereo_modulation": primary,
    }
