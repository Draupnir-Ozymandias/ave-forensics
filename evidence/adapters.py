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
        ],
        confidence={"score": hypothesis["hypothesis_score"], "method": "protocol_hypothesis_score"},
        provenance=provenance,
        limitations=["Hypothesis is not evidence of physiological or clinical effect."],
    )
