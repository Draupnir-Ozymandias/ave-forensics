"""Blind stage segmentation for short synthetic AVE audio demonstrations.

Boundaries are derived from adjacent-window feature changes. No declared stage
count, transition time, construction class, target rate, or tolerance is used.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from scipy.signal import hilbert

from analysis.pulse import analyze_pulse_patterns
from analysis.spectrum import analyze_spectrum


class StageSegmentationError(ValueError):
    """Raised when an audio signal cannot support stage reconstruction."""


def _as_channels(audio: np.ndarray) -> np.ndarray:
    array = np.asarray(audio, dtype=float)
    if array.ndim == 1:
        return array[np.newaxis, :]
    if array.ndim != 2 or array.shape[0] not in (1, 2):
        raise StageSegmentationError("audio must be mono or channels-first stereo")
    return array


def _window_features(window: np.ndarray) -> list[float]:
    mean_signal = np.mean(window, axis=0)
    envelope = np.abs(hilbert(mean_signal))
    low, high = np.percentile(envelope, [5, 95])
    normalized = np.clip((envelope - low) / max(high - low, np.finfo(float).eps), 0.0, 1.0)
    channel_rms = float(np.sqrt(np.mean(np.square(window))))
    difference_ratio = 0.0
    if window.shape[0] == 2:
        difference_ratio = float(
            np.sqrt(np.mean(np.square(window[0] - window[1])))
            / max(channel_rms, np.finfo(float).eps)
        )
    return [
        difference_ratio,
        float(np.mean(envelope)),
        float(np.std(envelope)),
        float(np.mean(normalized <= 0.15)),
        float(np.mean(normalized >= 0.85)),
        float(np.mean(np.abs(mean_signal) < 0.01)),
    ]


def _dominant_carrier(signal: np.ndarray, sample_rate: int) -> tuple[float | None, float]:
    spectrum = analyze_spectrum(
        signal,
        sample_rate,
        top_n=4,
        min_frequency=40.0,
        max_frequency=5000.0,
        max_fft_seconds=10.0,
        max_segments=1,
    )
    if not spectrum["top_peaks"]:
        return None, 0.0
    frequency, strength = spectrum["top_peaks"][0]
    return float(frequency), float(strength)


def _classify_stage(segment: np.ndarray, sample_rate: int) -> dict[str, Any]:
    channel_names = ["mono"] if segment.shape[0] == 1 else ["left", "right"]
    carriers = {}
    for index, name in enumerate(channel_names):
        frequency, strength = _dominant_carrier(segment[index], sample_rate)
        carriers[name] = {"frequency_hz": frequency, "strength": strength}

    carrier_difference = None
    if segment.shape[0] == 2:
        left = carriers["left"]["frequency_hz"]
        right = carriers["right"]["frequency_hz"]
        if left is not None and right is not None:
            carrier_difference = abs(right - left)

    pulse = analyze_pulse_patterns(
        segment,
        sample_rate,
        envelope_sample_rate=1000,
        min_rate_hz=0.5,
        max_rate_hz=40.0,
        window_seconds=min(2.0, segment.shape[1] / sample_rate),
        hop_seconds=0.5,
    )
    if carrier_difference is not None and carrier_difference >= 0.5:
        construction_class = "binaural_construction"
        confidence = min(item["strength"] for item in carriers.values())
    elif "isochronic_pulse_candidate" in pulse["classification"]:
        construction_class = "hard_gated_pulse"
        confidence = pulse["confidence"]
    elif pulse["classification"] == "smooth_amplitude_modulation":
        construction_class = "smooth_amplitude_modulation"
        confidence = pulse["confidence"]
    else:
        construction_class = "unclassified_audio_stage"
        confidence = pulse["confidence"]

    primary_name = "left" if "left" in pulse["channels"] else "mono"
    primary = pulse["channels"][primary_name]
    return {
        "construction_class": construction_class,
        "confidence": round(float(confidence), 6),
        "carriers": carriers,
        "interchannel_frequency_difference_hz": carrier_difference,
        "pulse_classification": pulse["classification"],
        "pulse_rate_hz": primary.get("pulse_rate_hz"),
        "duty_cycle_fraction": primary.get("duty_cycle"),
        "pulse_confidence": primary.get("confidence", 0.0),
        "stereo_relationship": pulse["stereo_relationship"]["classification"],
    }


def analyze_audio_stages(
    audio: np.ndarray,
    sample_rate: int,
    *,
    feature_window_seconds: float = 0.5,
    minimum_change_score: float = 0.8,
    minimum_stage_seconds: float = 2.0,
) -> dict[str, Any]:
    array = _as_channels(audio)
    if sample_rate <= 0:
        raise StageSegmentationError("sample_rate must be positive")
    window_samples = int(round(feature_window_seconds * sample_rate))
    if window_samples < 8:
        raise StageSegmentationError("feature window is too short")
    complete_windows = array.shape[1] // window_samples
    if complete_windows < 3:
        raise StageSegmentationError("audio is too short for stage segmentation")
    usable = complete_windows * window_samples
    features = np.asarray(
        [
            _window_features(array[:, start : start + window_samples])
            for start in range(0, usable, window_samples)
        ]
    )
    scale = np.percentile(features, 95, axis=0) - np.percentile(features, 5, axis=0)
    scale = np.maximum(scale, 1e-6)
    change_scores = np.linalg.norm(np.diff(features / scale, axis=0), axis=1)
    candidate_windows = np.flatnonzero(change_scores >= minimum_change_score) + 1
    minimum_windows = max(1, int(round(minimum_stage_seconds / feature_window_seconds)))
    retained = []
    for candidate in sorted(
        (int(item) for item in candidate_windows),
        key=lambda item: float(change_scores[item - 1]),
        reverse=True,
    ):
        if candidate < minimum_windows or complete_windows - candidate < minimum_windows:
            continue
        if any(abs(candidate - existing) < minimum_windows for existing in retained):
            continue
        retained.append(candidate)
    retained.sort()
    boundary_samples = [0, *(item * window_samples for item in retained), array.shape[1]]
    stages = []
    for index, (start, end) in enumerate(zip(boundary_samples, boundary_samples[1:]), start=1):
        classification = _classify_stage(array[:, start:end], sample_rate)
        stages.append(
            {
                "stage_id": f"stage_{index}",
                "start_seconds": round(start / sample_rate, 9),
                "end_seconds": round(end / sample_rate, 9),
                **classification,
            }
        )
    transition_times = [round(item * feature_window_seconds, 9) for item in retained]
    selected_scores = [round(float(change_scores[item - 1]), 6) for item in retained]
    confidence = min(1.0, min(selected_scores) / max(minimum_change_score, 1e-9)) if selected_scores else 0.0
    return {
        "classification": "segmented_audio_stages" if retained else "single_or_unresolved_stage",
        "stage_count": len(stages),
        "transition_times_seconds": transition_times,
        "transition_change_scores": selected_scores,
        "stages": stages,
        "confidence": round(confidence, 6),
        "configuration": {
            "feature_window_seconds": feature_window_seconds,
            "minimum_change_score": minimum_change_score,
            "minimum_stage_seconds": minimum_stage_seconds,
            "feature_names": [
                "interchannel_difference_ratio",
                "mean_envelope",
                "envelope_standard_deviation",
                "low_envelope_fraction",
                "high_envelope_fraction",
                "near_zero_sample_fraction",
            ],
        },
        "feature_windows": [
            {
                "start_seconds": round(index * feature_window_seconds, 9),
                "values": [round(float(value), 9) for value in row],
                "change_score_from_previous": (
                    None if index == 0 else round(float(change_scores[index - 1]), 6)
                ),
            }
            for index, row in enumerate(features)
        ],
        "limitations": [
            "Transition timing is quantized to the blind feature-window grid.",
            "The detector is designed for short synthetic demonstrations with sustained stage changes.",
            "Audio-only input cannot establish audio-to-video clock alignment.",
            "Signal classification does not establish neurological entrainment, efficacy, or safety.",
        ],
    }
