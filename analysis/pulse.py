"""Broadband pulse-train and isochronic-pattern analysis.

This module describes amplitude timing in the recording itself.  It does not
infer therapeutic intent or physiological response.
"""

from __future__ import annotations

from collections import Counter
from statistics import median
from typing import Any

import numpy as np


def _rms_envelope(audio: np.ndarray, sample_rate: int, target_rate: int) -> tuple[np.ndarray, float]:
    samples_per_frame = max(1, int(round(sample_rate / target_rate)))
    usable = (audio.size // samples_per_frame) * samples_per_frame
    if usable == 0:
        return np.array([], dtype=float), sample_rate / samples_per_frame
    source = np.asarray(audio[:usable])
    frame_count = usable // samples_per_frame
    envelope = np.empty(frame_count, dtype=float)
    chunk_frames = 10_000
    for frame_start in range(0, frame_count, chunk_frames):
        frame_end = min(frame_count, frame_start + chunk_frames)
        sample_start = frame_start * samples_per_frame
        sample_end = frame_end * samples_per_frame
        frames = source[sample_start:sample_end].reshape(-1, samples_per_frame)
        envelope[frame_start:frame_end] = np.sqrt(
            np.mean(np.square(frames, dtype=np.float64), axis=1)
        )
    return envelope, sample_rate / samples_per_frame


def _rising_edges(active: np.ndarray, minimum_distance: int) -> np.ndarray:
    edges = np.flatnonzero(np.diff(active.astype(np.int8), prepend=0) == 1)
    if edges.size < 2 or minimum_distance <= 1:
        return edges
    retained = [int(edges[0])]
    for edge in edges[1:]:
        if int(edge) - retained[-1] >= minimum_distance:
            retained.append(int(edge))
    return np.asarray(retained, dtype=int)


def _harmonic_fraction(signal: np.ndarray, rate: float, pulse_rate_hz: float) -> float:
    if signal.size < 8 or pulse_rate_hz <= 0:
        return 0.0
    centered = signal - np.mean(signal)
    windowed = centered * np.hanning(centered.size)
    power = np.abs(np.fft.rfft(windowed)) ** 2
    frequencies = np.fft.rfftfreq(centered.size, d=1.0 / rate)
    bin_width = rate / centered.size

    def local_power(frequency: float) -> float:
        tolerance = max(bin_width * 1.5, pulse_rate_hz * 0.03)
        mask = np.abs(frequencies - frequency) <= tolerance
        return float(np.sum(power[mask]))

    fundamental = local_power(pulse_rate_hz)
    harmonic = sum(
        local_power(pulse_rate_hz * order)
        for order in range(2, 7)
        if pulse_rate_hz * order <= rate / 2
    )
    denominator = fundamental + harmonic
    return harmonic / denominator if denominator > 0 else 0.0


def _channel_analysis(
    envelope: np.ndarray,
    envelope_rate: float,
    *,
    min_rate_hz: float,
    max_rate_hz: float,
    minimum_pulse_count: int,
    maximum_interval_cv: float,
    hard_state_separation: float,
    minimum_low_state_fraction: float,
    minimum_relative_dynamic_range: float,
) -> tuple[dict[str, Any], np.ndarray]:
    if envelope.size < 4:
        return {
            "classification": "insufficient_data",
            "pulse_rate_hz": None,
            "pulse_count": 0,
            "interval_cv": None,
            "onset_regularity": 0.0,
            "duty_cycle": None,
            "state_separation": None,
            "low_state_fraction": None,
            "harmonic_fraction": None,
            "relative_dynamic_range": None,
            "confidence": 0.0,
        }, np.array([], dtype=int)

    low, high = np.percentile(envelope, [5, 95])
    relative_dynamic_range = float((high - low) / max(high, np.finfo(float).eps))
    if high <= low or relative_dynamic_range < minimum_relative_dynamic_range:
        return {
            "classification": "no_periodic_pulse",
            "pulse_rate_hz": None,
            "pulse_count": 0,
            "interval_cv": None,
            "onset_regularity": 0.0,
            "duty_cycle": None,
            "state_separation": None,
            "low_state_fraction": None,
            "harmonic_fraction": None,
            "relative_dynamic_range": round(relative_dynamic_range, 6),
            "confidence": round(1.0 - relative_dynamic_range / minimum_relative_dynamic_range, 6),
        }, np.array([], dtype=int)

    normalized = np.clip((envelope - low) / (high - low), 0.0, 1.0)
    active = normalized >= 0.5
    minimum_distance = max(1, int(envelope_rate / max_rate_hz * 0.65))
    onsets = _rising_edges(active, minimum_distance)
    intervals = np.diff(onsets) / envelope_rate
    valid = intervals[(intervals >= 1.0 / max_rate_hz) & (intervals <= 1.0 / min_rate_hz)]

    duty_cycle = float(np.mean(active))
    low_fraction = float(np.mean(normalized <= 0.15))
    high_fraction = float(np.mean(normalized >= 0.85))
    state_separation = low_fraction + high_fraction

    if valid.size < minimum_pulse_count - 1:
        result = {
            "classification": "irregular_transients" if onsets.size else "no_periodic_pulse",
            "pulse_rate_hz": None,
            "pulse_count": int(onsets.size),
            "interval_cv": None,
            "onset_regularity": 0.0,
            "duty_cycle": round(duty_cycle, 6),
            "state_separation": round(state_separation, 6),
            "low_state_fraction": round(low_fraction, 6),
            "harmonic_fraction": None,
            "relative_dynamic_range": round(relative_dynamic_range, 6),
            "confidence": 0.25 if onsets.size else 0.5,
        }
        return result, onsets

    mean_interval = float(np.mean(valid))
    pulse_rate_hz = 1.0 / mean_interval
    interval_cv = float(np.std(valid) / max(np.mean(valid), np.finfo(float).eps))
    regularity = max(0.0, min(1.0, 1.0 - interval_cv / maximum_interval_cv))
    harmonic_fraction = _harmonic_fraction(normalized, envelope_rate, pulse_rate_hz)

    if interval_cv > maximum_interval_cv:
        classification = "irregular_transients"
        confidence = min(1.0, 0.5 + interval_cv)
    elif state_separation >= hard_state_separation and low_fraction >= minimum_low_state_fraction:
        classification = "hard_gated_pulse_train"
        confidence = 0.45 * regularity + 0.35 * state_separation + 0.20 * min(1.0, relative_dynamic_range)
    elif state_separation < hard_state_separation * 0.82:
        classification = "smooth_amplitude_modulation"
        confidence = 0.65 * regularity + 0.35 * (1.0 - min(1.0, state_separation))
    else:
        classification = "rhythmic_amplitude_pulsation"
        confidence = 0.60 * regularity + 0.25 * state_separation + 0.15 * harmonic_fraction

    return {
        "classification": classification,
        "pulse_rate_hz": round(pulse_rate_hz, 6),
        "pulse_count": int(onsets.size),
        "interval_cv": round(interval_cv, 6),
        "onset_regularity": round(regularity, 6),
        "duty_cycle": round(duty_cycle, 6),
        "state_separation": round(state_separation, 6),
        "low_state_fraction": round(low_fraction, 6),
        "harmonic_fraction": round(harmonic_fraction, 6),
        "relative_dynamic_range": round(relative_dynamic_range, 6),
        "confidence": round(max(0.0, min(1.0, confidence)), 6),
    }, onsets


def _stereo_relationship(
    left: dict[str, Any],
    right: dict[str, Any],
    left_onsets: np.ndarray,
    right_onsets: np.ndarray,
    envelope_rate: float,
) -> dict[str, Any]:
    left_rate, right_rate = left.get("pulse_rate_hz"), right.get("pulse_rate_hz")
    if left_rate is None or right_rate is None or not left_onsets.size or not right_onsets.size:
        return {"classification": "not_available", "median_offset_fraction": None}
    average_rate = (left_rate + right_rate) / 2.0
    if abs(left_rate - right_rate) > max(0.15, average_rate * 0.08):
        return {"classification": "different_rates", "median_offset_fraction": None}
    period_samples = envelope_rate / average_rate
    offsets = []
    for onset in left_onsets:
        delta = np.abs(right_onsets - onset)
        nearest = float(np.min(delta))
        phase_offset = nearest % period_samples
        wrapped = min(phase_offset, period_samples - phase_offset)
        offsets.append(wrapped / period_samples)
    offset_fraction = float(median(offsets))
    if offset_fraction <= 0.10:
        classification = "synchronized"
    elif offset_fraction >= 0.35:
        classification = "alternating"
    else:
        classification = "phase_offset"
    return {
        "classification": classification,
        "median_offset_fraction": round(offset_fraction, 6),
    }


def _overall_classification(channels: dict[str, dict[str, Any]], relationship: str) -> str:
    classes = [item["classification"] for item in channels.values()]
    hard_count = classes.count("hard_gated_pulse_train")
    if hard_count == 2 and relationship == "synchronized":
        return "synchronized_isochronic_pulse_candidate"
    if hard_count == 2 and relationship == "alternating":
        return "alternating_isochronic_pulse_candidate"
    if hard_count == 2:
        return "stereo_offset_isochronic_pulse_candidate"
    if hard_count:
        return "channel_specific_isochronic_pulse_candidate"
    if "rhythmic_amplitude_pulsation" in classes:
        return "periodic_amplitude_pulsation"
    if "smooth_amplitude_modulation" in classes:
        return "smooth_amplitude_modulation"
    if "irregular_transients" in classes:
        return "irregular_transients"
    if "insufficient_data" in classes:
        return "insufficient_data"
    return "no_periodic_pulse"


def analyze_pulse_patterns(
    audio: np.ndarray,
    sample_rate: int,
    *,
    envelope_sample_rate: int = 200,
    min_rate_hz: float = 0.5,
    max_rate_hz: float = 40.0,
    minimum_pulse_count: int = 5,
    maximum_interval_cv: float = 0.20,
    hard_state_separation: float = 0.72,
    minimum_low_state_fraction: float = 0.12,
    minimum_relative_dynamic_range: float = 0.12,
    window_seconds: float = 20.0,
    hop_seconds: float = 10.0,
) -> dict[str, Any]:
    """Measure broadband amplitude pulses and stereo timing relationships."""
    array = np.asarray(audio)
    channel_audio = {"mono": array} if array.ndim == 1 else {
        "left": array[0],
        "right": array[1],
    }
    envelopes: dict[str, np.ndarray] = {}
    channel_results: dict[str, dict[str, Any]] = {}
    onset_map: dict[str, np.ndarray] = {}
    actual_rate = float(envelope_sample_rate)
    options = {
        "min_rate_hz": min_rate_hz,
        "max_rate_hz": max_rate_hz,
        "minimum_pulse_count": minimum_pulse_count,
        "maximum_interval_cv": maximum_interval_cv,
        "hard_state_separation": hard_state_separation,
        "minimum_low_state_fraction": minimum_low_state_fraction,
        "minimum_relative_dynamic_range": minimum_relative_dynamic_range,
    }
    for name, signal in channel_audio.items():
        envelope, actual_rate = _rms_envelope(signal, sample_rate, envelope_sample_rate)
        envelopes[name] = envelope
        channel_results[name], onset_map[name] = _channel_analysis(envelope, actual_rate, **options)

    if "left" in channel_results:
        stereo = _stereo_relationship(
            channel_results["left"], channel_results["right"],
            onset_map["left"], onset_map["right"], actual_rate,
        )
    else:
        stereo = {"classification": "mono", "median_offset_fraction": None}

    window_length = max(1, int(round(window_seconds * actual_rate)))
    hop_length = max(1, int(round(hop_seconds * actual_rate)))
    shortest = min((item.size for item in envelopes.values()), default=0)
    timeline = []
    if shortest >= window_length:
        for start in range(0, shortest - window_length + 1, hop_length):
            window_channels = {}
            window_onsets = {}
            for name, envelope in envelopes.items():
                window_channels[name], window_onsets[name] = _channel_analysis(
                    envelope[start:start + window_length], actual_rate, **options
                )
            if "left" in window_channels:
                relation = _stereo_relationship(
                    window_channels["left"], window_channels["right"],
                    window_onsets["left"], window_onsets["right"], actual_rate,
                )
            else:
                relation = {"classification": "mono", "median_offset_fraction": None}
            timeline.append({
                "start_seconds": round(start / actual_rate, 3),
                "end_seconds": round((start + window_length) / actual_rate, 3),
                "classification": _overall_classification(window_channels, relation["classification"]),
                "channels": window_channels,
                "stereo_relationship": relation,
            })

    classifications = [item["classification"] for item in timeline]
    transitions = sum(a != b for a, b in zip(classifications, classifications[1:]))
    overall = _overall_classification(channel_results, stereo["classification"])
    confidences = [item["confidence"] for item in channel_results.values()]
    return {
        "classification": overall,
        "confidence": round(float(np.mean(confidences)), 6) if confidences else 0.0,
        "duration_seconds": round(array.shape[-1] / sample_rate, 6),
        "envelope_sample_rate_hz": round(actual_rate, 6),
        "channels": channel_results,
        "stereo_relationship": stereo,
        "timeline": timeline,
        "timeline_summary": {
            "window_count": len(timeline),
            "transition_count": transitions,
            "classification_counts": dict(sorted(Counter(classifications).items())),
        },
        "interpretation_limit": "Signal-pattern classification does not establish intent, efficacy, or physiological response.",
    }
