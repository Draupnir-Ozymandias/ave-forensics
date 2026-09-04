from __future__ import annotations

from collections import Counter
from statistics import median
from typing import Any

from evidence.schema import create_evidence_object, measurement


def carrier_pair_to_evidence(
    pair: dict[str, Any],
    provenance: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return create_evidence_object(
        evidence_level="association",
        evidence_type="persistent_carrier_pair",
        source_module="analysis.carrier_tracker",
        summary=(
            f"{pair['pair_type']} association between "
            f"{pair['left_carrier_hz']:.3f} Hz and "
            f"{pair['right_carrier_hz']:.3f} Hz carriers"
        ),
        channels=["left", "right"],
        time_range_seconds={
            "start": pair["start_seconds"],
            "end": pair["end_seconds"],
        },
        measurements=[
            measurement("left_carrier_frequency", pair["left_carrier_hz"], "Hz"),
            measurement("right_carrier_frequency", pair["right_carrier_hz"], "Hz"),
            measurement("carrier_difference", pair["difference_hz"], "Hz"),
            measurement("duration", pair["duration_seconds"], "seconds"),
            measurement("overlap_ratio", pair["overlap_ratio"], "ratio"),
            measurement("amplitude_balance", pair["amplitude_balance"], "ratio"),
        ],
        context={"pair_type": pair["pair_type"]},
        confidence={
            "score": pair["confidence"],
            "method": "carrier_pair_composite_score",
        },
        provenance=provenance,
        limitations=["Association does not by itself establish a binaural beat."],
    )


def envelope_analysis_to_evidence(
    result: dict[str, Any],
    channel: str,
    provenance: dict[str, Any] | None = None,
    time_range_seconds: dict[str, float] | None = None,
) -> dict[str, Any]:
    dominant = result.get("dominant_modulation")
    measurements = [
        measurement("carrier_center_frequency", result["carrier_center_hz"], "Hz"),
        measurement("modulation_depth", result["modulation_depth"], "ratio"),
    ]
    if dominant is not None:
        measurements.extend(
            [
                measurement("dominant_modulation_frequency", dominant["modulation_hz"], "Hz"),
                measurement("dominant_modulation_relative_power", dominant["relative_power"], "ratio"),
            ]
        )

    return create_evidence_object(
        evidence_level="detection" if dominant else "measurement",
        evidence_type="carrier_envelope_analysis",
        source_module="analysis.envelope",
        summary=f"Amplitude-envelope analysis for the {channel} carrier region",
        channels=[channel],
        time_range_seconds=time_range_seconds,
        measurements=measurements,
        context={
            "band_low_hz": result["band_low_hz"],
            "band_high_hz": result["band_high_hz"],
        },
        provenance=provenance,
        limitations=["Envelope structure does not establish physiological response."],
    )


def phase_timeline_to_evidence(
    timeline: list[dict[str, Any]],
    provenance: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not timeline:
        raise ValueError("phase timeline cannot be empty")
    behaviors = Counter(item["phase_behavior"] for item in timeline)
    behavior, count = behaviors.most_common(1)[0]
    coverage = count / len(timeline)

    return create_evidence_object(
        evidence_level="association",
        evidence_type="time_resolved_phase_relationship",
        source_module="analysis.phase",
        summary=f"Dominant stereo phase behavior: {behavior}",
        channels=["left", "right"],
        time_range_seconds={
            "start": timeline[0]["start_seconds"],
            "end": timeline[-1]["end_seconds"],
        },
        measurements=[
            measurement("dominant_phase_behavior", behavior, "classification"),
            measurement("behavior_window_coverage", coverage, "ratio"),
            measurement("median_phase_derived_difference", median(item["estimated_difference_hz"] for item in timeline), "Hz"),
            measurement("median_detrended_phase_locking", median(item["detrended_phase_locking_value"] for item in timeline), "ratio"),
            measurement("window_count", len(timeline), "count"),
        ],
        confidence={"score": coverage, "method": "dominant_window_coverage"},
        provenance=provenance,
        limitations=["Phase association describes signal structure, not listener response."],
    )


def modulation_spectrum_to_evidence(
    result: dict[str, Any],
    provenance: dict[str, Any] | None = None,
    time_range_seconds: dict[str, float] | None = None,
) -> dict[str, Any]:
    primary = result.get("primary_stereo_modulation")
    measurements = [
        measurement("classification", result["classification"], "classification"),
        measurement("left_track_count", len(result["left_tracks"]), "count"),
        measurement("right_track_count", len(result["right_tracks"]), "count"),
    ]
    confidence = None
    if primary is not None:
        measurements.extend(
            [
                measurement("primary_shared_modulation", primary["average_modulation_hz"], "Hz"),
                measurement("shared_window_coverage", primary["shared_coverage"], "ratio"),
                measurement("stereo_frequency_difference", primary["frequency_difference_hz"], "Hz"),
            ]
        )
        confidence = {"score": primary["confidence"], "method": "stereo_modulation_association_score"}

    return create_evidence_object(
        evidence_level="reconstruction",
        evidence_type="modulation_spectrum_reconstruction",
        source_module="analysis.modulation_spectrum",
        summary=result["classification"].replace("_", " "),
        channels=["left", "right"],
        time_range_seconds=time_range_seconds,
        measurements=measurements,
        confidence=confidence,
        provenance=provenance,
        limitations=["Reconstruction infers engineering structure, not intentionality or efficacy."],
    )


def protocol_hypothesis_to_evidence(
    hypothesis: dict[str, Any],
    provenance: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return create_evidence_object(
        evidence_level="hypothesis",
        evidence_type="protocol_intent_hypothesis",
        source_module="analysis.protocol_hypothesis",
        summary=hypothesis["intent"],
        measurements=[
            measurement("average_difference_frequency", hypothesis["average_difference_hz"], "Hz"),
            measurement("duration", hypothesis["duration_seconds"], "seconds"),
            measurement("brainwave_band", hypothesis["brainwave_band"], "classification"),
            measurement(
                "hypothesis_score",
                hypothesis["hypothesis_score"],
                "ranking_score",
            ),
        ],
        confidence={
            "score": hypothesis["average_confidence"],
            "method": "persistent_track_average_confidence",
        },
        provenance=provenance,
        limitations=["Hypothesis is not evidence of physiological or clinical effect."],
    )


def speech_context_to_evidence(
    result: dict[str, Any],
    provenance: dict[str, Any] | None = None,
    supporting_evidence_ids: list[str] | None = None,
) -> dict[str, Any]:
    entrainment = result["window_analyses"]["entrainment"]
    active = entrainment["speech_active"]
    sparse = entrainment["speech_sparse"]
    measurements = [
        measurement(
            "buffered_speech_coverage",
            result["regions"]["speech_active"]["coverage_ratio"],
            "ratio",
        ),
        measurement("speech_active_window_count", active["window_count"], "count"),
        measurement("speech_sparse_window_count", sparse["window_count"], "count"),
        measurement(
            "direct_comparison_available",
            result["comparison"]["direct_comparison_available"],
            "boolean",
        ),
    ]
    for name, value in (
        ("speech_active_candidate_rate", active["candidate_window_rate"]),
        ("speech_sparse_candidate_rate", sparse["candidate_window_rate"]),
        (
            "candidate_rate_difference_active_minus_sparse",
            result["comparison"]["candidate_rate_difference_active_minus_sparse"],
        ),
        ("speech_active_median_difference", active["median_difference_hz"]),
        ("speech_sparse_median_difference", sparse["median_difference_hz"]),
        (
            "speech_active_persistent_difference",
            result["comparison"]["active_persistent_difference_hz"],
        ),
        (
            "speech_sparse_persistent_difference",
            result["comparison"]["sparse_persistent_difference_hz"],
        ),
        (
            "speech_active_persistent_score",
            result["comparison"]["active_persistent_score"],
        ),
        (
            "speech_sparse_persistent_score",
            result["comparison"]["sparse_persistent_score"],
        ),
    ):
        if value is not None:
            unit = (
                "Hz"
                if "difference" in name and "rate_difference" not in name
                else "ranking_score"
                if "persistent_score" in name
                else "ratio"
            )
            measurements.append(measurement(name, value, unit))

    phase = result["window_analyses"].get("phase")
    if phase:
        for name, value in (
            (
                "speech_active_median_phase_locking",
                phase["speech_active"]["median_detrended_phase_locking"],
            ),
            (
                "speech_sparse_median_phase_locking",
                phase["speech_sparse"]["median_detrended_phase_locking"],
            ),
        ):
            if value is not None:
                measurements.append(measurement(name, value, "ratio"))

    return create_evidence_object(
        evidence_level="association",
        evidence_type="speech_context_comparison",
        source_module="analysis.speech_context",
        summary="Signal-window comparison across speech-active and speech-sparse regions",
        channels=["left", "right"],
        time_range_seconds={
            "start": 0.0,
            "end": result["recording"]["duration_seconds"],
        },
        measurements=measurements,
        context={
            "classification_configuration": result["configuration"],
            "transcript_binding": result["transcript_binding"],
            "entrainment_band_counts": {
                "speech_active": active["brainwave_band_counts"],
                "speech_sparse": sparse["brainwave_band_counts"],
            },
            "persistent_context": {
                "speech_active_band": result["comparison"][
                    "active_persistent_band"
                ],
                "speech_sparse_band": result["comparison"][
                    "sparse_persistent_band"
                ],
            },
        },
        provenance=provenance,
        supporting_evidence_ids=supporting_evidence_ids,
        limitations=result["limitations"],
    )
