"""Target-free perturbation robustness for one independently bounded audio stage."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

import numpy as np
from scipy.signal import resample_poly

from analysis.stage_segmentation import classify_audio_stage


class StageRobustnessError(ValueError):
    """Raised when a stage cannot support the robustness study."""


def _as_channels(audio: np.ndarray) -> np.ndarray:
    array = np.asarray(audio, dtype=float)
    if array.ndim == 1:
        return array[np.newaxis, :]
    if array.ndim != 2 or array.shape[0] not in (1, 2):
        raise StageRobustnessError("audio must be mono or channels-first stereo")
    return array


def _round_trip_resample(
    audio: np.ndarray, sample_rate: int, intermediate_rate: int
) -> np.ndarray:
    converted = resample_poly(audio, intermediate_rate, sample_rate, axis=1)
    restored = resample_poly(converted, sample_rate, intermediate_rate, axis=1)
    if restored.shape[1] < audio.shape[1]:
        restored = np.pad(restored, ((0, 0), (0, audio.shape[1] - restored.shape[1])))
    return restored[:, : audio.shape[1]]


def _variants(audio: np.ndarray, sample_rate: int) -> list[dict[str, Any]]:
    variants = []
    for milliseconds in (-10.0, -5.0, -1.0, -0.25, 0.25, 1.0, 5.0, 10.0):
        samples = int(round(milliseconds * sample_rate / 1000.0))
        variants.append(
            {
                "variant_id": f"circular_shift_{milliseconds:+g}ms",
                "family": "circular_time_shift",
                "parameters": {
                    "milliseconds": milliseconds,
                    "samples": samples,
                },
                "audio": np.roll(audio, samples, axis=1),
            }
        )
    for gain in (0.95, 1.05):
        variants.append(
            {
                "variant_id": f"gain_{gain:.2f}",
                "family": "gain",
                "parameters": {"linear_gain": gain},
                "audio": audio * gain,
            }
        )
    for bits in (16, 20, 24):
        scale = float(2 ** (bits - 1) - 1)
        variants.append(
            {
                "variant_id": f"quantize_{bits}bit",
                "family": "quantization",
                "parameters": {"bits": bits},
                "audio": np.round(audio * scale) / scale,
            }
        )
    signal_rms = float(np.sqrt(np.mean(np.square(audio))))
    for noise_db in (-80.0, -70.0, -60.0, -50.0):
        seed = 20261001 + int(abs(noise_db))
        random = np.random.default_rng(seed)
        noise_rms = signal_rms * 10.0 ** (noise_db / 20.0)
        variants.append(
            {
                "variant_id": f"noise_{noise_db:g}db",
                "family": "additive_noise",
                "parameters": {
                    "noise_db_relative_to_signal_rms": noise_db,
                    "seed": seed,
                },
                "audio": audio + random.normal(0.0, noise_rms, audio.shape),
            }
        )
    for intermediate_rate in (32000, 48000):
        variants.append(
            {
                "variant_id": f"resample_{intermediate_rate}",
                "family": "sample_rate_round_trip",
                "parameters": {
                    "intermediate_sample_rate_hz": intermediate_rate,
                    "restored_sample_rate_hz": sample_rate,
                },
                "audio": _round_trip_resample(audio, sample_rate, intermediate_rate),
            }
        )
    return variants


def _measurement(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "construction_class": result["construction_class"],
        "confidence": result["confidence"],
        "pulse_rate_hz": result["pulse_rate_hz"],
        "duty_cycle_fraction": result["duty_cycle_fraction"],
    }


def analyze_stage_robustness(
    audio: np.ndarray,
    sample_rate: int,
) -> dict[str, Any]:
    """Measure detector variation under fixed, declaration-free perturbations."""
    array = _as_channels(audio)
    if sample_rate <= 0:
        raise StageRobustnessError("sample_rate must be positive")
    if array.shape[1] < sample_rate * 2:
        raise StageRobustnessError("stage must be at least two seconds")

    baseline = _measurement(classify_audio_stage(array, sample_rate))
    measurements = []
    for variant in _variants(array, sample_rate):
        measured = _measurement(classify_audio_stage(variant.pop("audio"), sample_rate))
        measurements.append(
            {
                **variant,
                **measured,
                "confidence_delta_from_baseline": round(
                    measured["confidence"] - baseline["confidence"], 6
                ),
            }
        )

    confidence_values = np.asarray(
        [baseline["confidence"], *(item["confidence"] for item in measurements)],
        dtype=float,
    )
    family_values: dict[str, list[float]] = defaultdict(list)
    for item in measurements:
        family_values[item["family"]].append(item["confidence"])
    family_summary = {
        family: {
            "minimum": round(float(min(values)), 6),
            "maximum": round(float(max(values)), 6),
            "span": round(float(max(values) - min(values)), 6),
        }
        for family, values in sorted(family_values.items())
    }
    baseline_class = baseline["construction_class"]
    stable_count = sum(
        item["construction_class"] == baseline_class for item in measurements
    )
    return {
        "robustness_schema_version": "0.1.0",
        "analysis_type": "target_free_stage_classification_robustness",
        "sample_rate_hz": sample_rate,
        "duration_seconds": round(array.shape[1] / sample_rate, 9),
        "baseline": baseline,
        "variants": measurements,
        "summary": {
            "variant_count": len(measurements),
            "classification_stability_fraction": round(
                stable_count / len(measurements), 6
            ),
            "confidence": {
                "minimum": round(float(np.min(confidence_values)), 6),
                "maximum": round(float(np.max(confidence_values)), 6),
                "median": round(float(np.median(confidence_values)), 6),
                "standard_deviation": round(
                    float(np.std(confidence_values, ddof=1)), 6
                ),
                "span": round(float(np.ptp(confidence_values)), 6),
                "maximum_absolute_delta_from_baseline": round(
                    float(np.max(np.abs(confidence_values - baseline["confidence"]))),
                    6,
                ),
            },
            "confidence_by_perturbation_family": family_summary,
        },
        "configuration": {
            "perturbation_families": sorted(family_values),
            "confidence_threshold_loaded": False,
            "expected_class_loaded": False,
            "expected_rate_loaded": False,
        },
        "limitations": [
            "Perturbations estimate detector sensitivity; they are not independent Generator rerenders.",
            "Circular shifts can introduce one wrap seam even when periodic content is otherwise preserved.",
            "The observed spread applies to this detector, artifact, stage, and perturbation set only.",
            "Robustness does not establish neurological entrainment, efficacy, or safety.",
        ],
    }


def compare_confidence_threshold(
    robustness: dict[str, Any], threshold: float
) -> dict[str, Any]:
    """Compare a persisted robustness distribution with a later threshold."""
    if not 0.0 <= threshold <= 1.0:
        raise StageRobustnessError("confidence threshold must be between zero and one")
    baseline = float(robustness["baseline"]["confidence"])
    values = [
        baseline,
        *(float(item["confidence"]) for item in robustness["variants"]),
    ]
    minimum = min(values)
    maximum = max(values)
    distance = abs(baseline - threshold)
    radius = max(abs(item - baseline) for item in values)
    if minimum <= threshold <= maximum:
        interpretation = "borderline_within_observed_variation"
    elif baseline >= threshold:
        interpretation = "robustly_above_observed_range"
    else:
        interpretation = "robustly_below_observed_range"
    return {
        "comparison_schema_version": "0.1.0",
        "threshold": threshold,
        "baseline_confidence": baseline,
        "baseline_distance_from_threshold": round(distance, 6),
        "observed_robustness_radius": round(radius, 6),
        "observed_confidence_range": {
            "minimum": round(minimum, 6),
            "maximum": round(maximum, 6),
        },
        "observations_below_threshold": sum(item < threshold for item in values),
        "observations_at_or_above_threshold": sum(
            item >= threshold for item in values
        ),
        "interpretation": interpretation,
        "changes_primary_support_state": False,
        "reason": (
            "The post-observation threshold falls inside the empirical detector-variation range."
            if interpretation == "borderline_within_observed_variation"
            else "The post-observation threshold falls outside the empirical detector-variation range."
        ),
    }
