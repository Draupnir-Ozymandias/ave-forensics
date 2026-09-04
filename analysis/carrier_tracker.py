from __future__ import annotations

import statistics
from typing import Any

from analysis.stereo import simple_harmonic_ratio


def _match_peak_to_track(
    track: dict[str, Any],
    peaks: list[dict[str, float]],
    assigned_peak_indices: set[int],
    max_frequency_jump_hz: float,
):
    """
    Find the closest unassigned spectral peak to the last point
    in an existing carrier track.
    """
    last_frequency = track["points"][-1]["frequency_hz"]

    best_index = None
    best_peak = None
    best_distance = None

    for index, peak in enumerate(peaks):
        if index in assigned_peak_indices:
            continue

        distance = abs(peak["frequency_hz"] - last_frequency)

        if distance > max_frequency_jump_hz:
            continue

        if best_distance is None or distance < best_distance:
            best_index = index
            best_peak = peak
            best_distance = distance

    if best_peak is None:
        return None

    return best_index, best_peak, best_distance


def _finalize_track(
    track: dict[str, Any],
    min_track_windows: int,
):
    points = track["points"]

    if len(points) < min_track_windows:
        return None

    frequencies = [point["frequency_hz"] for point in points]

    magnitudes = [point["magnitude"] for point in points]

    average_frequency = statistics.mean(frequencies)
    frequency_std = statistics.pstdev(frequencies)
    average_magnitude = statistics.mean(magnitudes)

    start_seconds = points[0]["start_seconds"]
    end_seconds = points[-1]["end_seconds"]
    duration_seconds = end_seconds - start_seconds

    span_windows = points[-1]["window_index"] - points[0]["window_index"] + 1

    continuity = len(points) / max(span_windows, 1)
    stability = 1.0 / (1.0 + frequency_std)

    return {
        "channel": track["channel"],
        "start_seconds": round(start_seconds, 3),
        "end_seconds": round(end_seconds, 3),
        "duration_seconds": round(duration_seconds, 3),
        "average_frequency_hz": round(
            average_frequency,
            4,
        ),
        "frequency_std_hz": round(
            frequency_std,
            4,
        ),
        "frequency_stability": round(
            stability,
            4,
        ),
        "average_magnitude": round(
            average_magnitude,
            4,
        ),
        "continuity": round(
            continuity,
            4,
        ),
        "window_count": len(points),
        "points": points,
    }


def build_channel_carrier_tracks(
    timeline: list[dict[str, Any]],
    channel: str,
    max_frequency_jump_hz: float = 1.0,
    max_gap_windows: int = 2,
    min_track_windows: int = 6,
):
    """
    Track spectral peaks independently through one channel.

    channel must be either "left" or "right".
    """
    if channel not in {"left", "right"}:
        raise ValueError("channel must be 'left' or 'right'")

    peak_key = f"{channel}_peaks"

    active_tracks = []
    finished_tracks = []

    for item in timeline:
        peaks = item.get(peak_key, [])
        assigned_peak_indices = set()

        for track in active_tracks:
            match = _match_peak_to_track(
                track=track,
                peaks=peaks,
                assigned_peak_indices=assigned_peak_indices,
                max_frequency_jump_hz=max_frequency_jump_hz,
            )

            if match is None:
                track["misses"] += 1
                continue

            peak_index, peak, _ = match
            assigned_peak_indices.add(peak_index)

            track["points"].append(
                {
                    "window_index": item["window_index"],
                    "start_seconds": item["start_seconds"],
                    "end_seconds": item["end_seconds"],
                    "frequency_hz": peak["frequency_hz"],
                    "magnitude": peak["magnitude"],
                }
            )

            track["misses"] = 0

        still_active = []

        for track in active_tracks:
            if track["misses"] > max_gap_windows:
                finished_tracks.append(track)
            else:
                still_active.append(track)

        active_tracks = still_active

        for index, peak in enumerate(peaks):
            if index in assigned_peak_indices:
                continue

            active_tracks.append(
                {
                    "channel": channel,
                    "misses": 0,
                    "points": [
                        {
                            "window_index": item["window_index"],
                            "start_seconds": item["start_seconds"],
                            "end_seconds": item["end_seconds"],
                            "frequency_hz": peak["frequency_hz"],
                            "magnitude": peak["magnitude"],
                        }
                    ],
                }
            )

    finished_tracks.extend(active_tracks)

    finalized = []

    for track in finished_tracks:
        result = _finalize_track(
            track,
            min_track_windows=min_track_windows,
        )

        if result is not None:
            finalized.append(result)

    return sorted(
        finalized,
        key=lambda track: (
            track["continuity"],
            track["duration_seconds"],
            track["average_magnitude"],
        ),
        reverse=True,
    )


def build_carrier_tracks(
    timeline: list[dict[str, Any]],
    max_frequency_jump_hz: float = 1.0,
    max_gap_windows: int = 2,
    min_track_windows: int = 6,
):
    """
    Build independent persistent carrier tracks for both channels.
    """
    left_tracks = build_channel_carrier_tracks(
        timeline=timeline,
        channel="left",
        max_frequency_jump_hz=max_frequency_jump_hz,
        max_gap_windows=max_gap_windows,
        min_track_windows=min_track_windows,
    )

    right_tracks = build_channel_carrier_tracks(
        timeline=timeline,
        channel="right",
        max_frequency_jump_hz=max_frequency_jump_hz,
        max_gap_windows=max_gap_windows,
        min_track_windows=min_track_windows,
    )

    return {
        "left_tracks": left_tracks,
        "right_tracks": right_tracks,
    }


def _time_overlap_seconds(
    left_track: dict[str, Any],
    right_track: dict[str, Any],
) -> float:
    """
    Return the number of seconds during which two carrier tracks overlap.
    """
    overlap_start = max(
        left_track["start_seconds"],
        right_track["start_seconds"],
    )

    overlap_end = min(
        left_track["end_seconds"],
        right_track["end_seconds"],
    )

    return max(0.0, overlap_end - overlap_start)


def _overlap_ratio(
    left_track: dict[str, Any],
    right_track: dict[str, Any],
) -> float:
    """
    Measure overlap relative to the shorter carrier track.
    """
    overlap = _time_overlap_seconds(left_track, right_track)

    shorter_duration = min(
        left_track["duration_seconds"],
        right_track["duration_seconds"],
    )

    if shorter_duration <= 0:
        return 0.0

    return overlap / shorter_duration


def _amplitude_balance(
    left_track: dict[str, Any],
    right_track: dict[str, Any],
) -> float:
    """
    Return a 0-1 balance score.

    1.0 means the average magnitudes are equal.
    Values near zero indicate severe imbalance.
    """
    left_magnitude = left_track["average_magnitude"]
    right_magnitude = right_track["average_magnitude"]

    larger = max(left_magnitude, right_magnitude)

    if larger <= 0:
        return 0.0

    return min(left_magnitude, right_magnitude) / larger


def _pair_confidence(
    left_track: dict[str, Any],
    right_track: dict[str, Any],
    overlap_ratio: float,
    amplitude_balance: float,
    difference_hz: float,
    max_pair_difference_hz: float,
) -> float:
    """
    Score the quality of a cross-channel carrier association.

    This estimates confidence that the two persistent tracks form
    a meaningful cross-channel relationship. It does not infer a
    physiological effect.
    """
    continuity = (left_track["continuity"] + right_track["continuity"]) / 2

    stability = (
        left_track["frequency_stability"] + right_track["frequency_stability"]
    ) / 2

    magnitude_strength = min(
        1.0,
        (left_track["average_magnitude"] + right_track["average_magnitude"]) / 2,
    )

    difference_score = max(
        0.0,
        1.0 - (difference_hz / max_pair_difference_hz),
    )

    confidence = (
        overlap_ratio
        * continuity
        * stability
        * amplitude_balance
        * magnitude_strength
        * difference_score
    )

    return round(confidence, 4)


def classify_carrier_pair(
    difference_hz: float,
    left_frequency_hz: float | None = None,
    right_frequency_hz: float | None = None,
) -> str:
    if (
        left_frequency_hz is not None
        and right_frequency_hz is not None
        and simple_harmonic_ratio(left_frequency_hz, right_frequency_hz) is not None
    ):
        return "harmonic_relationship"
    if difference_hz < 0.1:
        return "shared_carrier"

    if difference_hz < 0.5:
        return "slight_detuning"

    if difference_hz <= 40.0:
        return "beat_candidate"

    return "wide_interval"


def associate_carrier_pairs(
    carrier_tracks: dict[str, list[dict[str, Any]]],
    min_overlap_ratio: float = 0.75,
    max_pair_difference_hz: float = 40.0,
    min_difference_hz: float = 0.0,
    min_duration_seconds: float = 30.0,
    min_amplitude_balance: float = 0.25,
):
    """
    Associate independently tracked left/right carriers.

    A possible carrier pair must:

    - overlap substantially in time;
    - persist for a minimum duration;
    - remain within the allowed frequency-difference range;
    - have reasonably balanced average magnitudes.

    The output is cross-channel carrier-pair evidence, not yet a
    binaural-beat conclusion.
    """
    left_tracks = carrier_tracks.get("left_tracks", [])
    right_tracks = carrier_tracks.get("right_tracks", [])

    pairs = []

    for left_index, left_track in enumerate(left_tracks):
        for right_index, right_track in enumerate(right_tracks):
            overlap_seconds = _time_overlap_seconds(
                left_track,
                right_track,
            )

            if overlap_seconds < min_duration_seconds:
                continue

            overlap_ratio = _overlap_ratio(
                left_track,
                right_track,
            )

            if overlap_ratio < min_overlap_ratio:
                continue

            difference_hz = abs(
                left_track["average_frequency_hz"] - right_track["average_frequency_hz"]
            )

            if difference_hz < min_difference_hz:
                continue

            if difference_hz > max_pair_difference_hz:
                continue

            amplitude_balance = _amplitude_balance(
                left_track,
                right_track,
            )

            if amplitude_balance < min_amplitude_balance:
                continue

            overlap_start = max(
                left_track["start_seconds"],
                right_track["start_seconds"],
            )

            overlap_end = min(
                left_track["end_seconds"],
                right_track["end_seconds"],
            )

            confidence = _pair_confidence(
                left_track=left_track,
                right_track=right_track,
                overlap_ratio=overlap_ratio,
                amplitude_balance=amplitude_balance,
                difference_hz=difference_hz,
                max_pair_difference_hz=max_pair_difference_hz,
            )

            pairs.append(
                {
                    "type": "persistent_carrier_pair",
                    "left_track_index": left_index,
                    "right_track_index": right_index,
                    "start_seconds": round(overlap_start, 3),
                    "end_seconds": round(overlap_end, 3),
                    "duration_seconds": round(
                        overlap_seconds,
                        3,
                    ),
                    "left_carrier_hz": left_track["average_frequency_hz"],
                    "right_carrier_hz": right_track["average_frequency_hz"],
                    "difference_hz": round(
                        difference_hz,
                        4,
                    ),
                    "pair_type": classify_carrier_pair(
                        difference_hz,
                        left_track["average_frequency_hz"],
                        right_track["average_frequency_hz"],
                    ),
                    "harmonic_ratio": simple_harmonic_ratio(
                        left_track["average_frequency_hz"],
                        right_track["average_frequency_hz"],
                    ),
                    "left_frequency_stability": left_track["frequency_stability"],
                    "right_frequency_stability": right_track["frequency_stability"],
                    "left_continuity": left_track["continuity"],
                    "right_continuity": right_track["continuity"],
                    "left_average_magnitude": left_track["average_magnitude"],
                    "right_average_magnitude": right_track["average_magnitude"],
                    "amplitude_balance": round(
                        amplitude_balance,
                        4,
                    ),
                    "overlap_ratio": round(
                        overlap_ratio,
                        4,
                    ),
                    "confidence": confidence,
                }
            )

    return sorted(
        pairs,
        key=lambda pair: (
            pair["confidence"],
            pair["duration_seconds"],
            pair["amplitude_balance"],
        ),
        reverse=True,
    )


def select_best_carrier_pairs(
    pairs: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Select a non-conflicting set of carrier-pair associations.

    Each left carrier track and each right carrier track may appear
    in at most one selected pair.

    Raw pair evidence remains unchanged; this function produces a
    cleaner reconstruction layer.
    """
    selected = []
    used_left_tracks = set()
    used_right_tracks = set()

    ranked_pairs = sorted(
        pairs,
        key=lambda pair: (
            pair["confidence"],
            pair["duration_seconds"],
            pair["overlap_ratio"],
            pair["amplitude_balance"],
        ),
        reverse=True,
    )

    for pair in ranked_pairs:
        left_index = pair["left_track_index"]
        right_index = pair["right_track_index"]

        if left_index in used_left_tracks:
            continue

        if right_index in used_right_tracks:
            continue

        selected.append(pair)
        used_left_tracks.add(left_index)
        used_right_tracks.add(right_index)

    return selected
