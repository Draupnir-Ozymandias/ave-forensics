from __future__ import annotations

from typing import Any

import numpy as np
from scipy.signal import hilbert

from analysis.envelope import bandpass_filter


def _wrap_phase(phase_radians: float) -> float:
    return float((phase_radians + np.pi) % (2.0 * np.pi) - np.pi)


def _classify_phase_behavior(
    difference_frequency_hz: float,
    raw_phase_locking_value: float,
    detrended_phase_locking_value: float,
) -> str:
    if abs(difference_frequency_hz) < 0.1:
        if raw_phase_locking_value >= 0.9:
            return "phase_locked"
        if detrended_phase_locking_value >= 0.8:
            return "stable_phase_offset"

    if (
        abs(difference_frequency_hz) >= 0.1
        and detrended_phase_locking_value >= 0.8
    ):
        return "stable_phase_rotation"

    if detrended_phase_locking_value >= 0.5:
        return "partially_coherent"

    return "unstable_or_unrelated"


def analyze_phase_relationship(
    left_audio: np.ndarray,
    right_audio: np.ndarray,
    sample_rate: int,
    left_center_frequency_hz: float,
    right_center_frequency_hz: float,
    bandwidth_hz: float = 8.0,
    trim_seconds: float = 0.5,
) -> dict[str, Any]:
    """Measure the phase relationship between two carrier regions.

    Phase difference is defined as right-channel phase minus left-channel
    phase. A positive difference-frequency estimate therefore means the
    right carrier rotates faster than the left carrier.

    The raw phase-locking value describes a stationary phase relationship.
    The detrended value removes a constant phase-rotation rate first, which
    allows a stable detuned pair to remain coherent even though its raw phase
    difference continuously rotates.
    """
    left_audio = np.asarray(left_audio, dtype=np.float64)
    right_audio = np.asarray(right_audio, dtype=np.float64)

    if left_audio.ndim != 1 or right_audio.ndim != 1:
        raise ValueError("phase analysis expects two mono 1-D signals")

    if left_audio.size != right_audio.size:
        raise ValueError("left and right signals must have equal lengths")

    if left_audio.size < 32:
        raise ValueError("audio is too short for reliable phase analysis")

    if sample_rate <= 0:
        raise ValueError("sample_rate must be positive")

    if bandwidth_hz <= 0:
        raise ValueError("bandwidth_hz must be positive")

    if trim_seconds < 0:
        raise ValueError("trim_seconds cannot be negative")

    half_bandwidth = bandwidth_hz / 2.0

    left_filtered = bandpass_filter(
        audio=left_audio,
        sample_rate=sample_rate,
        low_hz=left_center_frequency_hz - half_bandwidth,
        high_hz=left_center_frequency_hz + half_bandwidth,
    )
    right_filtered = bandpass_filter(
        audio=right_audio,
        sample_rate=sample_rate,
        low_hz=right_center_frequency_hz - half_bandwidth,
        high_hz=right_center_frequency_hz + half_bandwidth,
    )

    trim_samples = int(trim_seconds * sample_rate)

    if trim_samples > 0:
        if left_filtered.size - (2 * trim_samples) < 32:
            raise ValueError("trim_seconds removes too much of the signal")
        left_filtered = left_filtered[trim_samples:-trim_samples]
        right_filtered = right_filtered[trim_samples:-trim_samples]

    left_phase = np.unwrap(np.angle(hilbert(left_filtered)))
    right_phase = np.unwrap(np.angle(hilbert(right_filtered)))
    phase_difference = np.unwrap(right_phase - left_phase)

    time_seconds = np.arange(phase_difference.size) / sample_rate
    slope, _ = np.polyfit(time_seconds, phase_difference, 1)

    difference_frequency_hz = float(slope / (2.0 * np.pi))
    detrended_phase = phase_difference - (slope * time_seconds)

    raw_phase_vector = np.mean(np.exp(1j * phase_difference))
    detrended_phase_vector = np.mean(np.exp(1j * detrended_phase))

    raw_phase_locking_value = float(abs(raw_phase_vector))
    detrended_phase_locking_value = float(abs(detrended_phase_vector))
    mean_phase_offset_radians = _wrap_phase(float(np.angle(detrended_phase_vector)))

    expected_difference_hz = (
        right_center_frequency_hz - left_center_frequency_hz
    )

    behavior = _classify_phase_behavior(
        difference_frequency_hz=difference_frequency_hz,
        raw_phase_locking_value=raw_phase_locking_value,
        detrended_phase_locking_value=detrended_phase_locking_value,
    )

    return {
        "type": "phase_relationship_analysis",
        "left_carrier_hz": round(left_center_frequency_hz, 4),
        "right_carrier_hz": round(right_center_frequency_hz, 4),
        "expected_difference_hz": round(expected_difference_hz, 4),
        "estimated_difference_hz": round(difference_frequency_hz, 4),
        "difference_error_hz": round(
            difference_frequency_hz - expected_difference_hz,
            4,
        ),
        "mean_phase_offset_radians": round(mean_phase_offset_radians, 4),
        "mean_phase_offset_degrees": round(
            float(np.degrees(mean_phase_offset_radians)),
            2,
        ),
        "raw_phase_locking_value": round(raw_phase_locking_value, 4),
        "detrended_phase_locking_value": round(
            detrended_phase_locking_value,
            4,
        ),
        "phase_dispersion": round(
            1.0 - detrended_phase_locking_value,
            4,
        ),
        "phase_behavior": behavior,
        "samples_analyzed": int(phase_difference.size),
        "trim_seconds": trim_seconds,
    }


def analyze_phase_over_time(
    left_audio: np.ndarray,
    right_audio: np.ndarray,
    sample_rate: int,
    left_center_frequency_hz: float,
    right_center_frequency_hz: float,
    bandwidth_hz: float = 8.0,
    window_seconds: float = 30.0,
    hop_seconds: float = 15.0,
    trim_seconds: float = 0.5,
) -> list[dict[str, Any]]:
    """Measure a selected carrier pair in overlapping time windows."""
    left_audio = np.asarray(left_audio, dtype=np.float64)
    right_audio = np.asarray(right_audio, dtype=np.float64)

    if left_audio.ndim != 1 or right_audio.ndim != 1:
        raise ValueError("phase timeline expects two mono 1-D signals")

    if left_audio.size != right_audio.size:
        raise ValueError("left and right signals must have equal lengths")

    if window_seconds <= 0 or hop_seconds <= 0:
        raise ValueError("window_seconds and hop_seconds must be positive")

    window_samples = int(window_seconds * sample_rate)
    hop_samples = int(hop_seconds * sample_rate)

    if left_audio.size < window_samples:
        raise ValueError("audio is shorter than the requested phase window")

    timeline = []

    for window_index, start in enumerate(
        range(0, left_audio.size - window_samples + 1, hop_samples)
    ):
        end = start + window_samples
        result = analyze_phase_relationship(
            left_audio=left_audio[start:end],
            right_audio=right_audio[start:end],
            sample_rate=sample_rate,
            left_center_frequency_hz=left_center_frequency_hz,
            right_center_frequency_hz=right_center_frequency_hz,
            bandwidth_hz=bandwidth_hz,
            trim_seconds=trim_seconds,
        )
        result.update(
            {
                "window_index": window_index,
                "start_seconds": round(start / sample_rate, 3),
                "end_seconds": round(end / sample_rate, 3),
            }
        )
        timeline.append(result)

    return timeline
