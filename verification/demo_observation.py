"""Blind observation of AVE demo detector inputs.

This module consumes only the target-free verification request. Declaration
targets and tolerances are deliberately absent from every detector call.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np

from analysis.config import ANALYSIS_CONFIGURATION
from analysis.envelope import analyze_carrier_envelope
from analysis.modulation_ramp import analyze_modulation_ramp
from analysis.pulse import analyze_pulse_patterns
from analysis.spectrum import analyze_spectrum
from analysis.stage_segmentation import analyze_audio_stages
from analysis.video_regions import analyze_video_regions
from core.audio_loader import load_audio
from core.hashing import sha256_file
from evidence.adapters import modulation_ramp_to_evidence, pulse_analysis_to_evidence
from evidence.schema import create_evidence_object, measurement
from provenance.run import build_run_provenance


OBSERVATION_SCHEMA_VERSION = "0.1.0"
SUPPORTED_REQUEST_VERSION = "1.1.0"


class DemoObservationError(ValueError):
    """Raised when a blind verification request cannot be observed safely."""


def _scope(
    *,
    channels: list[str],
    duration_seconds: float | None,
    modality: str = "audio",
    regions: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "modality": modality,
        "channels": channels,
        "regions": regions or [],
        "time_range_seconds": (
            {"start": 0.0, "end": duration_seconds}
            if duration_seconds is not None
            else None
        ),
    }


def _metric(
    evidence_type: str,
    metric: str,
    unit: str,
    observed: dict[str, Any],
    scope: dict[str, Any],
    *,
    coverage: float,
    confidence: float,
    evidence_ids: list[str],
    limitations: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "evidence_type": evidence_type,
        "metric": metric,
        "unit": unit,
        "scope": scope,
        "observed": observed,
        "coverage_fraction": round(float(coverage), 6),
        "confidence": round(float(confidence), 6),
        "evidence_ids": evidence_ids,
        "limitations": limitations or [],
    }


def _validate_request(request: dict[str, Any]) -> None:
    required = {
        "request_version",
        "demo_id",
        "demo_version",
        "declaration_id",
        "detector_input",
        "comparison_after_observation",
        "requested_observation_metrics",
    }
    missing = required - request.keys()
    if missing:
        raise DemoObservationError(
            f"verification request missing: {', '.join(sorted(missing))}"
        )
    if request["request_version"] != SUPPORTED_REQUEST_VERSION:
        raise DemoObservationError("unsupported verification request version")
    detector_input = request["detector_input"]
    if detector_input.get("expected_values_present") is not False:
        raise DemoObservationError("detector input contains expected values")
    if detector_input.get("expected_tolerances_present") is not False:
        raise DemoObservationError("detector input contains expected tolerances")
    if detector_input.get("target_schedules_present") not in (None, False):
        raise DemoObservationError("detector input contains target schedules")
    if request.get("generator_declared_values_in_detector_input") is not False:
        raise DemoObservationError("generator declarations are present in detector input")
    if request["comparison_after_observation"].get(
        "do_not_load_before_evidence_is_persisted"
    ) is not True:
        raise DemoObservationError("request does not enforce observation-first ordering")


def _dominant_channel_carrier(
    signal: np.ndarray, sample_rate: int
) -> tuple[float, float]:
    spectrum = analyze_spectrum(
        signal,
        sample_rate,
        top_n=8,
        min_frequency=40.0,
        max_frequency=5000.0,
        max_fft_seconds=60.0,
        max_segments=8,
    )
    if not spectrum["top_peaks"]:
        raise DemoObservationError("no acoustic carrier candidate was observed")
    frequency, magnitude = spectrum["top_peaks"][0]
    return float(frequency), float(magnitude)


def _observe_video(
    *,
    request: dict[str, Any],
    request_path: Path,
    input_path: Path,
    actual_hash: str,
    requested_metrics: set[str],
    provenance: dict[str, Any],
    evidence_provenance: dict[str, Any],
    detector_configuration: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    result = analyze_video_regions(
        input_path,
        analysis_size=detector_configuration["video_regions"]["analysis_size"],
    )
    duration_seconds = result["duration_seconds"]
    video_scope = _scope(
        channels=[], duration_seconds=duration_seconds, modality="video"
    )
    region_ids = [item["region_id"] for item in result["regions"]]
    region_scope = _scope(
        channels=[],
        duration_seconds=duration_seconds,
        modality="video",
        regions=region_ids,
    )
    light_scope = _scope(
        channels=[],
        duration_seconds=duration_seconds,
        modality="light",
        regions=region_ids,
    )
    stream_evidence = create_evidence_object(
        evidence_level="measurement",
        evidence_type="video_stream_identity",
        source_module="analysis.video_regions",
        summary="Blind rendered-video stream identity and timing observation",
        channels=[],
        time_range_seconds={"start": 0.0, "end": duration_seconds},
        measurements=[
            measurement("input_sha256", actual_hash, "sha256"),
            measurement("duration_seconds", duration_seconds, "seconds"),
            measurement("frame_count", result["frame_count"], "count"),
            measurement("refresh_rate_hz", result["refresh_rate_hz"], "Hz"),
            measurement("width", result["stream"]["width"], "pixels"),
            measurement("height", result["stream"]["height"], "pixels"),
        ],
        context={"stream": result["stream"]},
        confidence={"score": 1.0, "method": "decoded_stream_measurement"},
        provenance=evidence_provenance,
        limitations=[
            "Encoded frame cadence is not a measurement of physical display refresh.",
            "Video timing does not establish efficacy or exposure safety.",
        ],
    )
    region_evidence = create_evidence_object(
        evidence_level="reconstruction",
        evidence_type="visual_region_schedule",
        source_module="analysis.video_regions",
        summary=result["classification"].replace("_", " "),
        channels=[],
        time_range_seconds={"start": 0.0, "end": duration_seconds},
        measurements=[
            measurement("region_count", result["region_count"], "count"),
            measurement(
                "independent_region_schedules",
                result["independent_region_schedules"],
                "boolean",
            ),
            measurement(
                "explicit_off_intervals",
                {
                    item["region_id"]: item["explicit_off_intervals"]
                    for item in result["regions"]
                },
                "seconds",
            ),
        ],
        context={
            "regions": result["regions"],
            "analysis_resolution": result["analysis_resolution"],
            "on_threshold": result["on_threshold"],
            "minimum_region_pixels": result["minimum_region_pixels"],
            "spatial_coverage_fraction": result["spatial_coverage_fraction"],
        },
        confidence={
            "score": result["confidence"],
            "method": "connected_pixel_timing_signatures",
        },
        provenance=evidence_provenance,
        limitations=result["limitations"],
    )
    evidence = [stream_evidence, region_evidence]
    metrics = [
        _metric(
            "media_identity",
            "duration_seconds",
            "s",
            {"kind": "scalar", "value": duration_seconds},
            video_scope,
            coverage=1.0,
            confidence=1.0,
            evidence_ids=[stream_evidence["evidence_id"]],
        ),
        _metric(
            "media_identity",
            "frame_count",
            "frames",
            {"kind": "scalar", "value": result["frame_count"]},
            region_scope,
            coverage=1.0,
            confidence=1.0,
            evidence_ids=[stream_evidence["evidence_id"]],
        ),
        _metric(
            "media_identity",
            "refresh_rate_hz",
            "Hz",
            {"kind": "scalar", "value": result["refresh_rate_hz"]},
            region_scope,
            coverage=1.0,
            confidence=1.0,
            evidence_ids=[stream_evidence["evidence_id"]],
            limitations=["Encoded cadence is not physical display refresh."],
        ),
        _metric(
            "resolved_light_plan",
            "duration_seconds",
            "s",
            {"kind": "scalar", "value": duration_seconds},
            light_scope,
            coverage=result["spatial_coverage_fraction"],
            confidence=result["confidence"],
            evidence_ids=[stream_evidence["evidence_id"], region_evidence["evidence_id"]],
            limitations=result["limitations"],
        ),
        _metric(
            "resolved_light_plan",
            "region_count",
            "count",
            {"kind": "scalar", "value": result["region_count"]},
            light_scope,
            coverage=result["spatial_coverage_fraction"],
            confidence=result["confidence"],
            evidence_ids=[region_evidence["evidence_id"]],
            limitations=result["limitations"],
        ),
        _metric(
            "resolved_light_plan",
            "independent_region_schedules",
            "boolean",
            {"kind": "boolean", "value": result["independent_region_schedules"]},
            light_scope,
            coverage=result["spatial_coverage_fraction"],
            confidence=result["confidence"],
            evidence_ids=[region_evidence["evidence_id"]],
            limitations=result["limitations"],
        ),
        _metric(
            "resolved_light_plan",
            "explicit_off_intervals",
            "boolean",
            {
                "kind": "boolean",
                "value": bool(result["regions"])
                and all(item["explicit_off_intervals"] for item in result["regions"]),
            },
            light_scope,
            coverage=result["spatial_coverage_fraction"],
            confidence=result["confidence"],
            evidence_ids=[region_evidence["evidence_id"]],
            limitations=result["limitations"],
        ),
    ]
    observed_metric_names = {item["metric"] for item in metrics}
    not_evaluated = []
    for metric_name in sorted(requested_metrics - observed_metric_names):
        reason = (
            "Generator recipe identity is not observable from rendered video pixels."
            if metric_name == "source_recipe_sha256"
            else "No compatible independent visual observation was produced."
        )
        not_evaluated.append({"metric": metric_name, "reason": reason})
    observation = {
        "observation_schema_version": OBSERVATION_SCHEMA_VERSION,
        "demo_id": request["demo_id"],
        "demo_version": request["demo_version"],
        "declaration_id": request["declaration_id"],
        "verification_request_sha256": sha256_file(request_path),
        "expected_declaration_sha256": request["comparison_after_observation"][
            "declaration_sha256"
        ],
        "artifact": {"path": str(input_path), "sha256": actual_hash},
        "ordering_attestation": {
            "declaration_loaded_during_detection": False,
            "targets_loaded_during_detection": False,
            "tolerances_loaded_during_detection": False,
        },
        "run_provenance": provenance,
        "metrics": metrics,
        "not_evaluated": not_evaluated,
        "evidence_ids": [item["evidence_id"] for item in evidence],
        "limitations": result["limitations"],
    }
    return observation, evidence


def observe_demo_request(
    request_path: Path,
    *,
    project_root: Path,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    request_path = request_path.resolve()
    request = json.loads(request_path.read_text())
    _validate_request(request)
    package_root = request_path.parent
    input_path = (package_root / request["detector_input"]["path"]).resolve()
    actual_hash = sha256_file(input_path)
    expected_hash = request["detector_input"]["sha256"]
    if actual_hash != expected_hash:
        raise DemoObservationError("detector input SHA-256 does not match request")

    requested_metrics = set(request["requested_observation_metrics"])
    detector_configuration = {
        "configuration_schema_version": "demo-observation-0.4.0",
        "request_version": request["request_version"],
        "requested_metrics": sorted(requested_metrics),
        "carrier_detection": {
            "min_frequency_hz": 40.0,
            "max_frequency_hz": 5000.0,
            "selection": "strongest_per_channel_without_declared_target",
        },
        "pulse": {
            **ANALYSIS_CONFIGURATION["pulse"],
            "envelope_sample_rate": 1000,
            "window_seconds": 2.0,
            "hop_seconds": 0.5,
        },
        "modulation_ramp": {
            **ANALYSIS_CONFIGURATION["modulation_ramp"],
            "envelope_sample_rate": 200,
            "min_rate_hz": 1.0,
            "max_rate_hz": 40.0,
            "window_seconds": 2.0,
            "hop_seconds": 0.5,
            "carrier_bandwidth_hz": 100.0,
        },
        "video_regions": {
            "analysis_size": 64,
            "absolute_on_threshold": 0.02,
            "relative_on_threshold": 0.05,
            "minimum_region_fraction": 0.02,
            "method": "connected_pixel_timing_signatures",
        },
        "stage_segmentation": {
            "feature_window_seconds": 0.5,
            "minimum_change_score": 0.8,
            "minimum_stage_seconds": 2.0,
            "method": "adjacent_window_feature_change",
        },
    }
    provenance = build_run_provenance(
        input_path=input_path,
        project_root=project_root,
        analysis_configuration=detector_configuration,
    )
    evidence_provenance = {
        "run_id": provenance["run_id"],
        "input_sha256": actual_hash,
        "recording_id": None,
        "analysis_configuration_version": detector_configuration[
            "configuration_schema_version"
        ],
    }

    media_type = request["detector_input"].get("media_type", "")
    if media_type.startswith("video/"):
        return _observe_video(
            request=request,
            request_path=request_path,
            input_path=input_path,
            actual_hash=actual_hash,
            requested_metrics=requested_metrics,
            provenance=provenance,
            evidence_provenance=evidence_provenance,
            detector_configuration=detector_configuration,
        )
    if media_type and not media_type.startswith("audio/"):
        raise DemoObservationError(f"unsupported detector input media type: {media_type}")

    audio, sample_rate = load_audio(str(input_path))
    array = np.asarray(audio, dtype=float)
    channels = ["mono"] if array.ndim == 1 else ["left", "right"]
    duration_seconds = float(array.shape[-1] / sample_rate)
    sample_peak = float(np.max(np.abs(array)))
    evidence = []
    metrics = []

    identity_evidence = create_evidence_object(
        evidence_level="measurement",
        evidence_type="media_identity",
        source_module="verification.demo_observation",
        summary="Blind detector-input media identity and level observation",
        channels=channels,
        time_range_seconds={"start": 0.0, "end": duration_seconds},
        measurements=[
            measurement("input_sha256", actual_hash, "sha256"),
            measurement("duration_seconds", duration_seconds, "seconds"),
            measurement("sample_rate", sample_rate, "Hz"),
            measurement("channel_count", len(channels), "count"),
            measurement("sample_peak_linear", sample_peak, "linear"),
        ],
        confidence={"score": 1.0, "method": "direct_file_measurement"},
        provenance=evidence_provenance,
        limitations=[
            "Digital amplitude is not calibrated sound pressure level.",
            "Media identity and timing do not establish efficacy or exposure safety.",
        ],
    )
    evidence.append(identity_evidence)
    audio_scope = _scope(channels=channels, duration_seconds=duration_seconds)
    metrics.extend(
        [
            _metric(
                "media_identity",
                "duration_seconds",
                "s",
                {"kind": "scalar", "value": duration_seconds},
                audio_scope,
                coverage=1.0,
                confidence=1.0,
                evidence_ids=[identity_evidence["evidence_id"]],
            ),
            _metric(
                "media_identity",
                "sample_peak_linear",
                "linear",
                {"kind": "scalar", "value": sample_peak},
                audio_scope,
                coverage=1.0,
                confidence=1.0,
                evidence_ids=[identity_evidence["evidence_id"]],
                limitations=["Digital peak is not calibrated SPL."],
            ),
        ]
    )

    carrier_results = {}
    for index, channel in enumerate(channels):
        signal = array if array.ndim == 1 else array[index]
        try:
            frequency, magnitude = _dominant_channel_carrier(signal, sample_rate)
        except DemoObservationError:
            continue
        carrier_results[channel] = (frequency, magnitude)
        carrier_evidence = create_evidence_object(
            evidence_level="detection",
            evidence_type="persistent_carrier",
            source_module="verification.demo_observation",
            summary=f"Dominant full-duration {channel} carrier candidate",
            channels=[channel],
            time_range_seconds={"start": 0.0, "end": duration_seconds},
            measurements=[
                measurement("carrier_frequency_hz", frequency, "Hz"),
                measurement("normalized_spectral_magnitude", magnitude, "ratio"),
            ],
            confidence={"score": min(1.0, magnitude), "method": "dominant_fft_peak"},
            provenance=evidence_provenance,
            limitations=[
                "Dominant spectral persistence does not establish entrainment intent."
            ],
        )
        evidence.append(carrier_evidence)
        metrics.append(
            _metric(
                "persistent_carrier",
                "carrier_frequency_hz",
                "Hz",
                {"kind": "scalar", "value": frequency},
                _scope(channels=[channel], duration_seconds=duration_seconds),
                coverage=1.0,
                confidence=min(1.0, magnitude),
                evidence_ids=[carrier_evidence["evidence_id"]],
            )
        )

    if "left" in carrier_results and "right" in carrier_results:
        left_hz, left_strength = carrier_results["left"]
        right_hz, right_strength = carrier_results["right"]
        difference = abs(right_hz - left_hz)
        routing = "shared_carrier" if difference < 0.1 else "separate_stereo_carriers"
        identical_stereo = bool(np.array_equal(array[0], array[1]))
        normalized_routing = (
            "identical_stereo"
            if identical_stereo
            else "separate_left_right_carriers"
            if difference >= 0.1
            else "shared_nonidentical_stereo"
        )
        relation_evidence = create_evidence_object(
            evidence_level="association",
            evidence_type="interchannel_carrier_relationship",
            source_module="verification.demo_observation",
            summary=f"{routing.replace('_', ' ')} with {difference:.6f} Hz difference",
            channels=["left", "right"],
            time_range_seconds={"start": 0.0, "end": duration_seconds},
            measurements=[
                measurement("left_carrier_frequency_hz", left_hz, "Hz"),
                measurement("right_carrier_frequency_hz", right_hz, "Hz"),
                measurement("interchannel_frequency_difference_hz", difference, "Hz"),
                measurement("channel_routing_class", normalized_routing, "classification"),
            ],
            confidence={
                "score": min(left_strength, right_strength),
                "method": "minimum_channel_peak_strength",
            },
            provenance=evidence_provenance,
            limitations=[
                "Interchannel carrier structure does not establish listener perception or neural response."
            ],
        )
        evidence.append(relation_evidence)
        relation_scope = _scope(
            channels=["left", "right"], duration_seconds=duration_seconds
        )
        metrics.extend(
            [
                _metric(
                    "binaural_candidate",
                    "interchannel_frequency_difference_hz",
                    "Hz",
                    {"kind": "scalar", "value": difference},
                    relation_scope,
                    coverage=1.0,
                    confidence=min(left_strength, right_strength),
                    evidence_ids=[relation_evidence["evidence_id"]],
                ),
                _metric(
                    "channel_routing",
                    "channel_routing_class",
                    "category",
                    {"kind": "category", "value": normalized_routing},
                    relation_scope,
                    coverage=1.0,
                    confidence=min(left_strength, right_strength),
                    evidence_ids=[relation_evidence["evidence_id"]],
                ),
            ]
        )

    pulse_requested = bool(
        requested_metrics
        & {
            "amplitude_shape_class",
            "duty_cycle_fraction",
            "explicit_off_state",
            "pulse_rate_hz",
            "stereo_relationship",
        }
    )
    if pulse_requested and sample_peak > 0:
        pulse_options = detector_configuration["pulse"]
        pulse_result = analyze_pulse_patterns(array, sample_rate, **pulse_options)
        pulse_evidence = pulse_analysis_to_evidence(pulse_result, evidence_provenance)
        evidence.append(pulse_evidence)
        timeline = pulse_result["timeline"]
        timeline_counts = Counter(item["classification"] for item in timeline)
        modal_shape, modal_count = (
            timeline_counts.most_common(1)[0]
            if timeline_counts
            else (pulse_result["classification"], 1)
        )
        shape_coverage = modal_count / max(len(timeline), 1)
        normalized_shape = (
            "hard_gated_pulse"
            if "isochronic_pulse_candidate" in modal_shape
            else modal_shape
        )
        primary_name = "left" if "left" in pulse_result["channels"] else "mono"
        primary = pulse_result["channels"][primary_name]
        pulse_scope = _scope(channels=channels, duration_seconds=duration_seconds)
        metrics.extend(
            [
                _metric(
                    "broadband_pulse_pattern",
                    "amplitude_shape_class",
                    "category",
                    {"kind": "category", "value": normalized_shape},
                    pulse_scope,
                    coverage=shape_coverage,
                    confidence=pulse_result["confidence"],
                    evidence_ids=[pulse_evidence["evidence_id"]],
                ),
                _metric(
                    "channel_routing",
                    "stereo_relationship",
                    "category",
                    {
                        "kind": "category",
                        "value": (
                            "identical_stereo"
                            if array.ndim == 2 and np.array_equal(array[0], array[1])
                            else pulse_result["stereo_relationship"]["classification"]
                        ),
                    },
                    pulse_scope,
                    coverage=shape_coverage,
                    confidence=pulse_result["confidence"],
                    evidence_ids=[pulse_evidence["evidence_id"]],
                ),
            ]
        )
        if primary.get("pulse_rate_hz") is not None:
            metrics.append(
                _metric(
                    "broadband_pulse_pattern",
                    "pulse_rate_hz",
                    "Hz",
                    {"kind": "scalar", "value": primary["pulse_rate_hz"]},
                    pulse_scope,
                    coverage=shape_coverage,
                    confidence=primary["confidence"],
                    evidence_ids=[pulse_evidence["evidence_id"]],
                )
            )
        if primary.get("duty_cycle") is not None:
            metrics.append(
                _metric(
                    "broadband_pulse_pattern",
                    "duty_cycle_fraction",
                    "fraction",
                    {"kind": "scalar", "value": primary["duty_cycle"]},
                    pulse_scope,
                    coverage=shape_coverage,
                    confidence=primary["confidence"],
                    evidence_ids=[pulse_evidence["evidence_id"]],
                )
            )
            metrics.append(
                _metric(
                    "broadband_pulse_pattern",
                    "explicit_off_state",
                    "boolean",
                    {
                        "kind": "boolean",
                        "value": bool(primary.get("low_state_fraction", 0.0) >= 0.12),
                    },
                    pulse_scope,
                    coverage=shape_coverage,
                    confidence=primary["confidence"],
                    evidence_ids=[pulse_evidence["evidence_id"]],
                )
            )

    ramp_requested = "modulation_rate_hz" in requested_metrics
    shared_carrier = None
    if carrier_results:
        frequencies = [item[0] for item in carrier_results.values()]
        if max(frequencies) - min(frequencies) < 0.5:
            shared_carrier = float(np.mean(frequencies))
    if ramp_requested and shared_carrier is not None and sample_peak > 0:
        ramp_options = dict(detector_configuration["modulation_ramp"])
        carrier_bandwidth = ramp_options.pop("carrier_bandwidth_hz")
        mean_signal = array if array.ndim == 1 else np.mean(array[:2], axis=0)
        ramp_result = analyze_modulation_ramp(
            mean_signal,
            sample_rate,
            carrier_center_hz=shared_carrier,
            carrier_bandwidth_hz=carrier_bandwidth,
            **ramp_options,
        )
        ramp_evidence = modulation_ramp_to_evidence(
            ramp_result, evidence_provenance, channel="mean"
        )
        evidence.append(ramp_evidence)
        if ramp_result["fit"] is not None:
            fit = ramp_result["fit"]
            metrics.append(
                _metric(
                    "continuous_modulation_ramp",
                    "modulation_rate_hz",
                    "Hz",
                    {
                        "kind": "linear_curve",
                        "start": {
                            "time_seconds": 0.0,
                            "value": fit["fitted_scope_start_rate_hz"],
                        },
                        "end": {
                            "time_seconds": duration_seconds,
                            "value": fit["fitted_scope_end_rate_hz"],
                        },
                        "residual_rmse": fit["residual_rmse_hz"],
                        "point_observations": [
                            {
                                "time_seconds": item["center_seconds"],
                                "value": item["rate_hz"],
                            }
                            for item in ramp_result["windows"]
                            if item["supported"]
                        ],
                    },
                    _scope(channels=channels, duration_seconds=duration_seconds),
                    coverage=ramp_result["coverage"],
                    confidence=ramp_result["confidence"],
                    evidence_ids=[ramp_evidence["evidence_id"]],
                    limitations=ramp_result["limitations"],
                )
            )

    if (
        "modulation_depth_fraction" in requested_metrics
        and shared_carrier is not None
        and sample_peak > 0
    ):
        mean_signal = array if array.ndim == 1 else np.mean(array[:2], axis=0)
        envelope_result = analyze_carrier_envelope(
            mean_signal,
            sample_rate,
            center_frequency_hz=shared_carrier,
            bandwidth_hz=100.0,
            envelope_sample_rate=200,
            min_modulation_hz=1.0,
            max_modulation_hz=40.0,
        )
        depth = envelope_result["modulation_depth"]
        depth_evidence = create_evidence_object(
            evidence_level="measurement",
            evidence_type="carrier_envelope",
            source_module="analysis.envelope",
            summary="Blind full-duration carrier-envelope depth measurement",
            channels=channels,
            time_range_seconds={"start": 0.0, "end": duration_seconds},
            measurements=[measurement("modulation_depth_fraction", depth, "ratio")],
            confidence={"score": 0.9, "method": "robust_envelope_percentiles"},
            provenance=evidence_provenance,
            limitations=[
                "Depth uses robust fifth and ninety-fifth percentiles rather than raw extrema."
            ],
        )
        evidence.append(depth_evidence)
        metrics.append(
            _metric(
                "carrier_envelope",
                "modulation_depth_fraction",
                "fraction",
                {"kind": "scalar", "value": depth},
                _scope(channels=channels, duration_seconds=duration_seconds),
                coverage=1.0,
                confidence=0.9,
                evidence_ids=[depth_evidence["evidence_id"]],
                limitations=depth_evidence["limitations"],
            )
        )

    stage_requested = bool(
        requested_metrics
        & {
            "construction_class",
            "stage_count",
            "transition_time_seconds",
        }
    )
    if stage_requested:
        stage_options = detector_configuration["stage_segmentation"]
        stage_result = analyze_audio_stages(
            array,
            sample_rate,
            feature_window_seconds=stage_options["feature_window_seconds"],
            minimum_change_score=stage_options["minimum_change_score"],
            minimum_stage_seconds=stage_options["minimum_stage_seconds"],
        )
        stage_evidence = create_evidence_object(
            evidence_level="reconstruction",
            evidence_type="audio_stage_segmentation",
            source_module="analysis.stage_segmentation",
            summary=stage_result["classification"].replace("_", " "),
            channels=channels,
            time_range_seconds={"start": 0.0, "end": duration_seconds},
            measurements=[
                measurement("stage_count", stage_result["stage_count"], "count"),
                measurement(
                    "transition_times_seconds",
                    stage_result["transition_times_seconds"],
                    "seconds",
                ),
                measurement(
                    "construction_classes",
                    [item["construction_class"] for item in stage_result["stages"]],
                    "classification",
                ),
            ],
            context={
                "stages": stage_result["stages"],
                "transition_change_scores": stage_result["transition_change_scores"],
                "configuration": stage_result["configuration"],
                "feature_windows": stage_result["feature_windows"],
            },
            confidence={
                "score": stage_result["confidence"],
                "method": "adjacent_window_feature_change",
            },
            provenance=evidence_provenance,
            limitations=stage_result["limitations"],
        )
        evidence.append(stage_evidence)
        metrics.append(
            _metric(
                "stage_timeline",
                "stage_count",
                "count",
                {"kind": "scalar", "value": stage_result["stage_count"]},
                audio_scope,
                coverage=1.0,
                confidence=stage_result["confidence"],
                evidence_ids=[stage_evidence["evidence_id"]],
                limitations=stage_result["limitations"],
            )
        )
        for index, stage in enumerate(stage_result["stages"]):
            stage_scope = _scope(
                channels=channels,
                duration_seconds=None,
            )
            stage_scope["time_range_seconds"] = {
                "start": stage["start_seconds"],
                "end": stage["end_seconds"],
            }
            metrics.append(
                _metric(
                    "stage_classification",
                    "construction_class",
                    "category",
                    {"kind": "category", "value": stage["construction_class"]},
                    stage_scope,
                    coverage=1.0,
                    confidence=stage["confidence"],
                    evidence_ids=[stage_evidence["evidence_id"]],
                    limitations=stage_result["limitations"],
                )
            )
            if index < len(stage_result["transition_times_seconds"]):
                metrics.append(
                    _metric(
                        "stage_timeline",
                        "transition_time_seconds",
                        "s",
                        {
                            "kind": "scalar",
                            "value": stage_result["transition_times_seconds"][index],
                        },
                        audio_scope,
                        coverage=1.0,
                        confidence=stage_result["confidence"],
                        evidence_ids=[stage_evidence["evidence_id"]],
                        limitations=stage_result["limitations"],
                    )
                )
            if stage["interchannel_frequency_difference_hz"] is not None:
                metrics.append(
                    _metric(
                        "binaural_candidate",
                        "interchannel_frequency_difference_hz",
                        "Hz",
                        {
                            "kind": "scalar",
                            "value": stage["interchannel_frequency_difference_hz"],
                        },
                        stage_scope,
                        coverage=1.0,
                        confidence=min(
                            item["strength"] for item in stage["carriers"].values()
                        ),
                        evidence_ids=[stage_evidence["evidence_id"]],
                    )
                )
            if (
                stage["construction_class"] == "smooth_amplitude_modulation"
                and stage["pulse_rate_hz"] is not None
            ):
                metrics.append(
                    _metric(
                        "carrier_envelope",
                        "modulation_rate_hz",
                        "Hz",
                        {"kind": "scalar", "value": stage["pulse_rate_hz"]},
                        stage_scope,
                        coverage=1.0,
                        confidence=stage["pulse_confidence"],
                        evidence_ids=[stage_evidence["evidence_id"]],
                    )
                )
            if stage["construction_class"] == "hard_gated_pulse":
                if stage["pulse_rate_hz"] is not None:
                    metrics.append(
                        _metric(
                            "broadband_pulse_pattern",
                            "pulse_rate_hz",
                            "Hz",
                            {"kind": "scalar", "value": stage["pulse_rate_hz"]},
                            stage_scope,
                            coverage=1.0,
                            confidence=stage["pulse_confidence"],
                            evidence_ids=[stage_evidence["evidence_id"]],
                        )
                    )
                if stage["duty_cycle_fraction"] is not None:
                    metrics.append(
                        _metric(
                            "broadband_pulse_pattern",
                            "duty_cycle_fraction",
                            "fraction",
                            {"kind": "scalar", "value": stage["duty_cycle_fraction"]},
                            stage_scope,
                            coverage=1.0,
                            confidence=stage["pulse_confidence"],
                            evidence_ids=[stage_evidence["evidence_id"]],
                        )
                    )

    observed_metric_names = {item["metric"] for item in metrics}
    not_evaluated = []
    for metric_name in sorted(requested_metrics - observed_metric_names):
        if metric_name in {
            "explicit_off_intervals",
            "frame_count",
            "independent_region_schedules",
            "refresh_rate_hz",
            "region_count",
            "source_recipe_sha256",
        }:
            reason = "No independent light/video detector is implemented for the supplied audio-only detector input."
        elif metric_name == "clock_alignment":
            reason = "Audio-only detector input cannot establish audio-to-video clock alignment."
        else:
            reason = "No compatible independent observation was produced."
        not_evaluated.append({"metric": metric_name, "reason": reason})

    observation = {
        "observation_schema_version": OBSERVATION_SCHEMA_VERSION,
        "demo_id": request["demo_id"],
        "demo_version": request["demo_version"],
        "declaration_id": request["declaration_id"],
        "verification_request_sha256": sha256_file(request_path),
        "expected_declaration_sha256": request["comparison_after_observation"][
            "declaration_sha256"
        ],
        "artifact": {
            "path": str(input_path),
            "sha256": actual_hash,
        },
        "ordering_attestation": {
            "declaration_loaded_during_detection": False,
            "targets_loaded_during_detection": False,
            "tolerances_loaded_during_detection": False,
        },
        "run_provenance": provenance,
        "metrics": metrics,
        "not_evaluated": not_evaluated,
        "evidence_ids": [item["evidence_id"] for item in evidence],
        "limitations": [
            "Observations describe engineering properties, not neurological entrainment, efficacy, or exposure safety.",
            "Dominant-carrier selection is blind to declarations but remains vulnerable to stronger unrelated spectral components.",
        ],
    }
    return observation, evidence
