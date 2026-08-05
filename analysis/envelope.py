from __future__ import annotations

from typing import Any

import numpy as np
from scipy.signal import (
    butter,
    find_peaks,
    hilbert,
    resample_poly,
    sosfiltfilt,
    welch,
)


def select_envelope_carrier_pair(
    carrier_pairs: list[dict[str, Any]],
    minimum_center_hz: float = 20.0,
) -> dict[str, Any] | None:
    """Return the strongest pair suitable for acoustic envelope analysis."""
    for pair in carrier_pairs:
        center_hz = (
            float(pair["left_carrier_hz"])
            + float(pair["right_carrier_hz"])
        ) / 2.0
        if center_hz >= minimum_center_hz:
            return pair
    return None


def _validate_band(
    low_hz: float,
    high_hz: float,
    sample_rate: int,
) -> None:
    nyquist = sample_rate / 2.0

    if low_hz <= 0:
        raise ValueError("low_hz must be greater than zero")

    if high_hz <= low_hz:
        raise ValueError("high_hz must be greater than low_hz")

    if high_hz >= nyquist:
        raise ValueError(
            f"high_hz must be below Nyquist frequency " f"({nyquist:.1f} Hz)"
        )


def bandpass_filter(
    audio: np.ndarray,
    sample_rate: int,
    low_hz: float,
    high_hz: float,
    order: int = 4,
) -> np.ndarray:
    """
    Isolate a frequency region using a zero-phase Butterworth
    band-pass filter.

    Parameters
    ----------
    audio:
        One-dimensional real-valued audio signal.
    sample_rate:
        Audio sample rate in Hz.
    low_hz, high_hz:
        Band-pass limits.
    order:
        Butterworth filter order before forward/reverse filtering.
    """
    audio = np.asarray(audio, dtype=np.float64)

    if audio.ndim != 1:
        raise ValueError("bandpass_filter expects mono 1-D audio")

    if audio.size < 32:
        raise ValueError("audio is too short for reliable filtering")

    _validate_band(
        low_hz=low_hz,
        high_hz=high_hz,
        sample_rate=sample_rate,
    )

    sos = butter(
        order,
        [low_hz, high_hz],
        btype="bandpass",
        fs=sample_rate,
        output="sos",
    )

    return sosfiltfilt(sos, audio)


def extract_amplitude_envelope(
    filtered_audio: np.ndarray,
) -> np.ndarray:
    """
    Extract the instantaneous amplitude envelope using the
    magnitude of the analytic signal.
    """
    filtered_audio = np.asarray(
        filtered_audio,
        dtype=np.float64,
    )

    if filtered_audio.ndim != 1:
        raise ValueError("extract_amplitude_envelope expects 1-D audio")

    analytic_signal = hilbert(filtered_audio)
    envelope = np.abs(analytic_signal)

    return envelope


def downsample_envelope(
    envelope: np.ndarray,
    original_sample_rate: int,
    target_sample_rate: int = 200,
) -> tuple[np.ndarray, int]:
    """
    Reduce the envelope sampling rate.

    The audio carrier may require 44.1 kHz, but an envelope limited
    to tens of hertz does not. Downsampling greatly reduces memory
    and later analysis cost.
    """
    if target_sample_rate <= 0:
        raise ValueError("target_sample_rate must be greater than zero")

    if target_sample_rate >= original_sample_rate:
        return envelope.copy(), original_sample_rate

    gcd = np.gcd(original_sample_rate, target_sample_rate)
    up = target_sample_rate // gcd
    down = original_sample_rate // gcd

    reduced = resample_poly(
        envelope,
        up=up,
        down=down,
    )

    return reduced, target_sample_rate


def estimate_modulation_depth(
    envelope: np.ndarray,
) -> float:
    """
    Estimate modulation depth robustly using the 5th and 95th
    percentiles rather than raw extrema.

    depth = (high - low) / (high + low)
    """
    envelope = np.asarray(envelope, dtype=np.float64)

    if envelope.size == 0:
        return 0.0

    low = float(np.percentile(envelope, 5))
    high = float(np.percentile(envelope, 95))

    denominator = high + low

    if denominator <= 0:
        return 0.0

    depth = (high - low) / denominator

    return round(float(np.clip(depth, 0.0, 1.0)), 4)


def analyze_envelope_spectrum(
    envelope: np.ndarray,
    envelope_sample_rate: int,
    min_modulation_hz: float = 0.1,
    max_modulation_hz: float = 40.0,
    top_n: int = 10,
) -> dict[str, Any]:
    """
    Produce a basic low-frequency spectrum of the amplitude
    envelope.

    This is an initial measurement layer. A fuller Modulation
    Spectrum module will later expand this into time-resolved
    modulation tracking.
    """
    envelope = np.asarray(envelope, dtype=np.float64)

    if envelope.ndim != 1:
        raise ValueError("analyze_envelope_spectrum expects 1-D data")

    if envelope.size < 16:
        return {
            "frequencies_hz": np.array([]),
            "power": np.array([]),
            "peaks": [],
        }

    centered = envelope - np.mean(envelope)

    segment_length = min(
        centered.size,
        max(256, envelope_sample_rate * 8),
    )

    frequencies, power = welch(
        centered,
        fs=envelope_sample_rate,
        nperseg=segment_length,
        detrend="constant",
        scaling="spectrum",
    )

    mask = (frequencies >= min_modulation_hz) & (frequencies <= max_modulation_hz)

    band_frequencies = frequencies[mask]
    band_power = power[mask]

    if band_power.size == 0 or np.max(band_power) <= 0:
        return {
            "frequencies_hz": band_frequencies,
            "power": band_power,
            "peaks": [],
        }

    normalized_power = band_power / np.max(band_power)

    peak_indices, properties = find_peaks(
        normalized_power,
        prominence=0.01,
    )

    peaks = []

    for peak_index in peak_indices:
        peaks.append(
            {
                "modulation_hz": round(
                    float(band_frequencies[peak_index]),
                    4,
                ),
                "relative_power": round(
                    float(normalized_power[peak_index]),
                    4,
                ),
            }
        )

    peaks.sort(
        key=lambda item: item["relative_power"],
        reverse=True,
    )

    return {
        "frequencies_hz": band_frequencies,
        "power": normalized_power,
        "peaks": peaks[:top_n],
    }


def analyze_carrier_envelope(
    audio: np.ndarray,
    sample_rate: int,
    center_frequency_hz: float,
    bandwidth_hz: float = 8.0,
    envelope_sample_rate: int = 200,
    min_modulation_hz: float = 0.1,
    max_modulation_hz: float = 40.0,
) -> dict[str, Any]:
    """
    Analyze amplitude modulation surrounding one carrier region.
    """
    if bandwidth_hz <= 0:
        raise ValueError("bandwidth_hz must be positive")

    half_bandwidth = bandwidth_hz / 2.0
    low_hz = center_frequency_hz - half_bandwidth
    high_hz = center_frequency_hz + half_bandwidth

    filtered = bandpass_filter(
        audio=audio,
        sample_rate=sample_rate,
        low_hz=low_hz,
        high_hz=high_hz,
    )

    full_rate_envelope = extract_amplitude_envelope(filtered)

    reduced_envelope, reduced_sample_rate = downsample_envelope(
        envelope=full_rate_envelope,
        original_sample_rate=sample_rate,
        target_sample_rate=envelope_sample_rate,
    )

    modulation_depth = estimate_modulation_depth(reduced_envelope)

    spectrum = analyze_envelope_spectrum(
        envelope=reduced_envelope,
        envelope_sample_rate=reduced_sample_rate,
        min_modulation_hz=min_modulation_hz,
        max_modulation_hz=max_modulation_hz,
    )

    dominant = spectrum["peaks"][0] if spectrum["peaks"] else None

    return {
        "type": "carrier_envelope_analysis",
        "carrier_center_hz": round(
            center_frequency_hz,
            4,
        ),
        "band_low_hz": round(low_hz, 4),
        "band_high_hz": round(high_hz, 4),
        "bandwidth_hz": round(bandwidth_hz, 4),
        "envelope_sample_rate": reduced_sample_rate,
        "modulation_depth": modulation_depth,
        "dominant_modulation": dominant,
        "modulation_peaks": spectrum["peaks"],
        "envelope": reduced_envelope,
        "modulation_frequencies_hz": spectrum["frequencies_hz"],
        "modulation_power": spectrum["power"],
    }


def analyze_envelope_over_time(
    audio: np.ndarray,
    sample_rate: int,
    center_frequency_hz: float,
    bandwidth_hz: float = 8.0,
    window_seconds: float = 30.0,
    hop_seconds: float = 15.0,
    envelope_sample_rate: int = 200,
    min_modulation_hz: float = 0.1,
    max_modulation_hz: float = 40.0,
) -> list[dict[str, Any]]:
    """
    Analyze the amplitude envelope of one carrier region in
    overlapping time windows.
    """
    if window_seconds <= 0:
        raise ValueError("window_seconds must be positive")

    if hop_seconds <= 0:
        raise ValueError("hop_seconds must be positive")

    window_samples = int(window_seconds * sample_rate)
    hop_samples = int(hop_seconds * sample_rate)

    if audio.size < window_samples:
        raise ValueError("audio is shorter than the requested envelope window")

    timeline = []

    for window_index, start in enumerate(
        range(
            0,
            audio.size - window_samples + 1,
            hop_samples,
        )
    ):
        end = start + window_samples
        chunk = audio[start:end]

        result = analyze_carrier_envelope(
            audio=chunk,
            sample_rate=sample_rate,
            center_frequency_hz=center_frequency_hz,
            bandwidth_hz=bandwidth_hz,
            envelope_sample_rate=envelope_sample_rate,
            min_modulation_hz=min_modulation_hz,
            max_modulation_hz=max_modulation_hz,
        )

        timeline.append(
            {
                "window_index": window_index,
                "start_seconds": round(start / sample_rate, 3),
                "end_seconds": round(end / sample_rate, 3),
                "carrier_center_hz": result["carrier_center_hz"],
                "modulation_depth": result["modulation_depth"],
                "dominant_modulation": result["dominant_modulation"],
                "modulation_peaks": result["modulation_peaks"],
            }
        )

    return timeline
