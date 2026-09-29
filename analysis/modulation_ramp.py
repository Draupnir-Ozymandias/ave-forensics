"""Time-resolved continuous amplitude-modulation ramp analysis.

The detector observes a carrier-band envelope without accepting an expected
curve. Producer declarations belong in a later comparison step, not here.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from analysis.envelope import bandpass_filter, downsample_envelope, extract_amplitude_envelope


ANALYSIS_SCHEMA_VERSION = "1.0.0"


def _quadratic_peak_frequency(
    frequencies: np.ndarray, power: np.ndarray, index: int
) -> float:
    """Refine one FFT-bin peak with a three-point log-power parabola."""
    if index <= 0 or index >= power.size - 1:
        return float(frequencies[index])
    values = np.log(np.maximum(power[index - 1:index + 2], np.finfo(float).tiny))
    denominator = values[0] - 2.0 * values[1] + values[2]
    if abs(denominator) <= np.finfo(float).eps:
        return float(frequencies[index])
    offset = 0.5 * (values[0] - values[2]) / denominator
    offset = float(np.clip(offset, -0.5, 0.5))
    return float(frequencies[index] + offset * (frequencies[1] - frequencies[0]))


def _window_measurement(
    envelope: np.ndarray,
    envelope_rate: float,
    *,
    start_sample: int,
    min_rate_hz: float,
    max_rate_hz: float,
    minimum_spectral_snr_db: float,
    minimum_peak_concentration: float,
    minimum_relative_variation: float,
    time_offset_seconds: float,
) -> dict[str, Any]:
    mean_level = float(np.mean(envelope))
    relative_variation = float(
        np.std(envelope) / max(abs(mean_level), np.finfo(float).eps)
    )
    centered = envelope - mean_level
    windowed = centered * np.hanning(centered.size)
    power = np.abs(np.fft.rfft(windowed)) ** 2
    frequencies = np.fft.rfftfreq(windowed.size, d=1.0 / envelope_rate)
    mask = (frequencies >= min_rate_hz) & (frequencies <= max_rate_hz)
    band_frequencies = frequencies[mask]
    band_power = power[mask]

    start_seconds = time_offset_seconds + start_sample / envelope_rate
    end_seconds = time_offset_seconds + (start_sample + envelope.size) / envelope_rate
    base = {
        "start_seconds": round(start_seconds, 6),
        "end_seconds": round(end_seconds, 6),
        "center_seconds": round((start_seconds + end_seconds) / 2.0, 6),
        "rate_hz": None,
        "spectral_snr_db": None,
        "peak_concentration": None,
        "relative_envelope_variation": round(relative_variation, 6),
        "confidence": 0.0,
        "supported": False,
        "failure_reason": None,
    }
    if band_power.size < 3 or not np.any(band_power > 0):
        base["failure_reason"] = "no_modulation_band_energy"
        return base

    peak_index = int(np.argmax(band_power))
    peak_power = float(band_power[peak_index])
    excluded = np.ones(band_power.size, dtype=bool)
    excluded[max(0, peak_index - 1):min(band_power.size, peak_index + 2)] = False
    noise_values = band_power[excluded]
    noise_floor = float(np.median(noise_values)) if noise_values.size else 0.0
    spectral_snr_db = 10.0 * np.log10(
        max(peak_power, np.finfo(float).tiny)
        / max(noise_floor, np.finfo(float).tiny)
    )
    local_start = max(0, peak_index - 1)
    local_end = min(band_power.size, peak_index + 2)
    peak_concentration = float(
        np.sum(band_power[local_start:local_end])
        / max(np.sum(band_power), np.finfo(float).tiny)
    )
    rate_hz = _quadratic_peak_frequency(band_frequencies, band_power, peak_index)

    snr_score = float(
        np.clip((spectral_snr_db - minimum_spectral_snr_db) / 18.0, 0.0, 1.0)
    )
    concentration_score = float(
        np.clip(
            peak_concentration / max(minimum_peak_concentration * 2.0, 0.01),
            0.0,
            1.0,
        )
    )
    variation_score = float(
        np.clip(
            relative_variation / max(minimum_relative_variation * 4.0, 0.01),
            0.0,
            1.0,
        )
    )
    confidence = 0.45 * snr_score + 0.35 * concentration_score + 0.20 * variation_score

    reasons = []
    if relative_variation < minimum_relative_variation:
        reasons.append("insufficient_envelope_variation")
    if spectral_snr_db < minimum_spectral_snr_db:
        reasons.append("insufficient_spectral_snr")
    if peak_concentration < minimum_peak_concentration:
        reasons.append("diffuse_modulation_spectrum")

    base.update(
        {
            "rate_hz": round(rate_hz, 6) if not reasons else None,
            "spectral_snr_db": round(float(spectral_snr_db), 6),
            "peak_concentration": round(peak_concentration, 6),
            "confidence": round(confidence, 6),
            "supported": not reasons,
            "failure_reason": ";".join(reasons) if reasons else None,
        }
    )
    return base


def analyze_modulation_ramp(
    audio: np.ndarray,
    sample_rate: int,
    *,
    carrier_center_hz: float,
    carrier_bandwidth_hz: float,
    envelope_sample_rate: int = 1000,
    min_rate_hz: float = 1.0,
    max_rate_hz: float = 360.0,
    window_seconds: float = 2.0,
    hop_seconds: float = 0.5,
    minimum_spectral_snr_db: float = 8.0,
    minimum_peak_concentration: float = 0.12,
    minimum_relative_variation: float = 0.01,
    minimum_coverage: float = 0.5,
    minimum_contiguous_coverage: float = 0.5,
    minimum_fit_r_squared: float = 0.85,
    minimum_ramp_slope_hz_per_second: float = 0.05,
    time_offset_seconds: float = 0.0,
) -> dict[str, Any]:
    """Observe a stable modulation or continuous modulation ramp around a carrier."""
    signal = np.asarray(audio, dtype=np.float64)
    if signal.ndim != 1:
        raise ValueError("analyze_modulation_ramp expects mono 1-D audio")
    if signal.size < 32:
        raise ValueError("audio is too short for modulation-ramp analysis")
    if sample_rate <= 0:
        raise ValueError("sample_rate must be positive")
    if carrier_center_hz <= 0 or carrier_bandwidth_hz <= 0:
        raise ValueError("carrier center and bandwidth must be positive")
    if min_rate_hz <= 0 or max_rate_hz <= min_rate_hz:
        raise ValueError("modulation-rate bounds are invalid")
    if envelope_sample_rate <= 2.0 * max_rate_hz:
        raise ValueError("envelope_sample_rate must exceed twice max_rate_hz")
    if window_seconds <= 0 or hop_seconds <= 0:
        raise ValueError("window_seconds and hop_seconds must be positive")
    if not 0.0 <= minimum_coverage <= 1.0:
        raise ValueError("minimum_coverage must be within 0-1")
    if not 0.0 <= minimum_contiguous_coverage <= 1.0:
        raise ValueError("minimum_contiguous_coverage must be within 0-1")
    if not 0.0 <= minimum_fit_r_squared <= 1.0:
        raise ValueError("minimum_fit_r_squared must be within 0-1")
    if time_offset_seconds < 0:
        raise ValueError("time_offset_seconds must be non-negative")

    half_bandwidth = carrier_bandwidth_hz / 2.0
    band_low_hz = carrier_center_hz - half_bandwidth
    band_high_hz = carrier_center_hz + half_bandwidth
    filtered = bandpass_filter(signal, sample_rate, band_low_hz, band_high_hz)
    envelope = extract_amplitude_envelope(filtered)
    envelope, actual_envelope_rate = downsample_envelope(
        envelope, sample_rate, envelope_sample_rate
    )
    actual_envelope_rate = float(actual_envelope_rate)
    window_samples = int(round(window_seconds * actual_envelope_rate))
    hop_samples = int(round(hop_seconds * actual_envelope_rate))
    if window_samples < 16 or envelope.size < window_samples:
        raise ValueError("audio is shorter than one modulation-ramp window")

    windows = []
    for start in range(0, envelope.size - window_samples + 1, hop_samples):
        windows.append(
            _window_measurement(
                envelope[start:start + window_samples],
                actual_envelope_rate,
                start_sample=start,
                min_rate_hz=min_rate_hz,
                max_rate_hz=max_rate_hz,
                minimum_spectral_snr_db=minimum_spectral_snr_db,
                minimum_peak_concentration=minimum_peak_concentration,
                minimum_relative_variation=minimum_relative_variation,
                time_offset_seconds=time_offset_seconds,
            )
        )

    supported = [item for item in windows if item["supported"]]
    coverage = len(supported) / len(windows) if windows else 0.0
    longest_run = current_run = 0
    for item in windows:
        current_run = current_run + 1 if item["supported"] else 0
        longest_run = max(longest_run, current_run)
    contiguous_coverage = longest_run / len(windows) if windows else 0.0
    fit = None
    fit_diagnostics = None
    fit_rejection_reason = None
    classification = "insufficient_support"
    confidence = 0.0
    unsupported_intervals = [
        {
            "start_seconds": item["start_seconds"],
            "end_seconds": item["end_seconds"],
            "reason": item["failure_reason"],
        }
        for item in windows
        if not item["supported"]
    ]

    if len(supported) >= 3 and coverage >= minimum_coverage:
        times = np.asarray([item["center_seconds"] for item in supported], dtype=float)
        rates = np.asarray([item["rate_hz"] for item in supported], dtype=float)
        slope, intercept = np.polyfit(times, rates, 1)
        fitted = intercept + slope * times
        residuals = rates - fitted
        residual_rmse = float(np.sqrt(np.mean(residuals ** 2)))
        total_variation = float(np.sum((rates - np.mean(rates)) ** 2))
        fit_r_squared = (
            float(1.0 - np.sum(residuals ** 2) / total_variation)
            if total_variation > np.finfo(float).eps
            else 1.0
        )
        first_time = float(times[0])
        last_time = float(times[-1])
        direction = (
            "increasing"
            if slope >= minimum_ramp_slope_hz_per_second
            else "decreasing"
            if slope <= -minimum_ramp_slope_hz_per_second
            else "stable"
        )
        stable_rate_limit_hz = max(0.25, 0.75 / window_seconds)
        stable_rate_standard_deviation_hz = float(np.std(rates))
        rate_span = max(float(np.ptp(rates)), 1.0 / window_seconds)
        fit_score = float(np.clip(1.0 - residual_rmse / rate_span, 0.0, 1.0))
        mean_window_confidence = float(
            np.mean([item["confidence"] for item in supported])
        )
        fit_diagnostics = {
            "direction": direction,
            "slope_hz_per_second": round(float(slope), 6),
            "first_supported_center_seconds": round(first_time, 6),
            "last_supported_center_seconds": round(last_time, 6),
            "fitted_start_rate_hz": round(float(intercept + slope * first_time), 6),
            "fitted_end_rate_hz": round(float(intercept + slope * last_time), 6),
            "fitted_scope_start_rate_hz": round(
                float(intercept + slope * time_offset_seconds), 6
            ),
            "fitted_scope_end_rate_hz": round(
                float(
                    intercept
                    + slope * (time_offset_seconds + signal.size / sample_rate)
                ),
                6,
            ),
            "residual_rmse_hz": round(residual_rmse, 6),
            "r_squared": round(fit_r_squared, 6),
            "rate_standard_deviation_hz": round(
                stable_rate_standard_deviation_hz, 6
            ),
        }
        rejection_reasons = []
        if contiguous_coverage < minimum_contiguous_coverage:
            rejection_reasons.append("insufficient_contiguous_coverage")
        if direction == "stable":
            if stable_rate_standard_deviation_hz > stable_rate_limit_hz:
                rejection_reasons.append("unstable_ridge_with_near_zero_slope")
        elif fit_r_squared < minimum_fit_r_squared:
            rejection_reasons.append("poor_linear_fit")
        if rejection_reasons:
            fit_rejection_reason = ";".join(rejection_reasons)
        else:
            fit = fit_diagnostics
            classification = (
                "continuous_modulation_ramp"
                if direction != "stable"
                else "stable_modulation"
            )
            confidence = coverage * (
                0.65 * mean_window_confidence + 0.35 * fit_score
            )

    return {
        "analysis_schema_version": ANALYSIS_SCHEMA_VERSION,
        "analysis_type": "continuous_modulation_ramp_analysis",
        "classification": classification,
        "confidence": round(float(np.clip(confidence, 0.0, 1.0)), 6),
        "duration_seconds": round(signal.size / sample_rate, 6),
        "source_time_range_seconds": {
            "start": round(time_offset_seconds, 6),
            "end": round(time_offset_seconds + signal.size / sample_rate, 6),
        },
        "channel": "unspecified",
        "carrier_band": {
            "center_hz": round(carrier_center_hz, 6),
            "low_hz": round(band_low_hz, 6),
            "high_hz": round(band_high_hz, 6),
        },
        "configuration": {
            "envelope_sample_rate_hz": actual_envelope_rate,
            "min_rate_hz": min_rate_hz,
            "max_rate_hz": max_rate_hz,
            "window_seconds": window_seconds,
            "hop_seconds": hop_seconds,
            "minimum_spectral_snr_db": minimum_spectral_snr_db,
            "minimum_peak_concentration": minimum_peak_concentration,
            "minimum_relative_variation": minimum_relative_variation,
            "minimum_coverage": minimum_coverage,
            "minimum_contiguous_coverage": minimum_contiguous_coverage,
            "minimum_fit_r_squared": minimum_fit_r_squared,
            "minimum_ramp_slope_hz_per_second": minimum_ramp_slope_hz_per_second,
            "time_offset_seconds": time_offset_seconds,
        },
        "window_count": len(windows),
        "supported_window_count": len(supported),
        "coverage": round(coverage, 6),
        "contiguous_coverage": round(contiguous_coverage, 6),
        "fit": fit,
        "fit_diagnostics": fit_diagnostics,
        "fit_rejection_reason": fit_rejection_reason,
        "windows": windows,
        "unsupported_intervals": unsupported_intervals,
        "limitations": [
            "The detector observes one selected carrier band; overlapping carriers or sidebands may confound the envelope.",
            "A continuous rate ridge does not distinguish a smooth envelope from gated pulses; waveform shape requires separate pulse analysis.",
            "Scope-boundary rates are linear-fit estimates beyond the first and last window centers.",
            "Unsupported windows are not interpolated into the fitted result.",
            "Signal reconstruction does not establish intent, safety, brain response, or efficacy.",
        ],
    }
