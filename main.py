import argparse
import json
from pathlib import Path

from core.audio_loader import load_audio
from core.metadata import describe_audio
from analysis.spectrum import analyze_spectrum
from analysis.config import ANALYSIS_CONFIGURATION
from analysis.stereo import analyze_stereo
from analysis.entrainment import classify_binaural_candidates
from reports import protocol_summary
from reports.markdown_report import generate_markdown_report
from analysis.time_resolved import analyze_time_resolved
from reports.csv_export import export_timeline_csv
from reports.plots import plot_timeline
from analysis.protocol_tracker import build_protocol_tracks
from analysis.protocol_hypothesis import generate_protocol_hypotheses
from reports.protocol_export import export_tracks_csv, export_hypotheses_csv
from analysis.protocol_hypothesis import (
    generate_protocol_hypotheses,
    deduplicate_hypotheses,
)
from reports.protocol_summary import generate_protocol_summary
from analysis.carrier_tracker import (
    build_carrier_tracks,
    associate_carrier_pairs,
    select_best_carrier_pairs,
)
from analysis.envelope import (
    analyze_carrier_envelope,
    analyze_envelope_over_time,
    select_envelope_carrier_pair,
)
from reports.envelope_console import (
    print_envelope_timeline,
    print_global_envelope_results,
)
from analysis.phase import analyze_phase_over_time
from reports.phase_console import print_phase_timeline
from analysis.modulation_spectrum import analyze_modulation_spectrum
from reports.modulation_console import print_modulation_spectrum_summary
from evidence.adapters import (
    carrier_pair_to_evidence,
    envelope_analysis_to_evidence,
    modulation_spectrum_to_evidence,
    phase_timeline_to_evidence,
    protocol_hypothesis_to_evidence,
    speech_context_to_evidence,
)
from reports.evidence_export import export_evidence_json
from provenance.run import build_run_provenance

DEFAULT_AUDIO_PATH = "/Users/eric/Projects/media/ave_forensics/samples/brainfm/meditate/unguided/Altered_State_Unguided_Meditation_Session_4_1.2_Nrmlzd2 1_15mins_VBR5.mp3"


def main(audio_path: str = DEFAULT_AUDIO_PATH, output_dir: str = "."):
    project_root = Path(__file__).resolve().parent
    input_path = Path(audio_path).resolve()
    analysis_config = ANALYSIS_CONFIGURATION
    run_provenance = build_run_provenance(
        input_path=input_path,
        project_root=project_root,
        analysis_configuration=analysis_config,
    )
    audio_path = str(input_path)
    output_directory = Path(output_dir)
    output_directory.mkdir(parents=True, exist_ok=True)

    def output_path(filename: str) -> str:
        return str(output_directory / filename)

    y, sr = load_audio(audio_path)
    metadata = describe_audio(y, sr)
    spectrum_config = analysis_config["global_spectrum"]
    spectrum = analyze_spectrum(
        y,
        sr,
        top_n=spectrum_config["top_n"],
        min_frequency=spectrum_config["min_frequency_hz"],
        max_frequency=spectrum_config["max_frequency_hz"],
        max_fft_seconds=spectrum_config["max_fft_seconds"],
        max_segments=spectrum_config["max_segments"],
    )
    stereo = analyze_stereo(y, sr)

    print("=== AVE FORENSICS LABORATORY ===")
    print(metadata)

    print("\nTop frequency peaks:")
    for freq, mag in spectrum["top_peaks"]:
        print(f"{freq:.2f} Hz | magnitude: {mag:.4f}")

    print("\nStereo analysis:")
    print(f"Left/right correlation: {stereo['left_right_correlation']}")

    classified_candidates = classify_binaural_candidates(stereo["binaural_candidates"])

    print("\nClassified entrainment candidates:")
    for candidate in classified_candidates[:20]:
        print(candidate)

    report = generate_markdown_report(metadata, spectrum, stereo, classified_candidates)

    with open(output_path("ave_report.md"), "w") as f:
        f.write(report)

    print("\nReport written to ave_report.md")

    timeline_config = analysis_config["timeline"]
    timeline = analyze_time_resolved(
        y,
        sr,
        window_seconds=timeline_config["window_seconds"],
        hop_seconds=timeline_config["hop_seconds"],
        peaks_per_channel=timeline_config["peaks_per_channel"],
    )

    print("\nTime-resolved entrainment timeline:")
    printed = 0

    for item in timeline:
        c = item["top_candidate"]

        if c is None:
            continue

        print(
            f"{item['start_seconds']:>7.2f}s - {item['end_seconds']:>7.2f}s | "
            f"{c['difference_hz']} Hz "
            f"({c['brainwave_band']}) | "
            f"confidence {c['confidence']}"
        )

        printed += 1

        if printed >= 20:
            break

    print(f"\nDetected candidate windows: {printed} shown")
    print(f"Total windows analyzed: {len(timeline)}")

    export_timeline_csv(timeline, output_path("ave_timeline.csv"))
    print("\nTimeline written to ave_timeline.csv")

    plot_timeline(
        output_path("ave_timeline.csv"),
        output_path("ave_timeline.png"),
    )
    print("Timeline plot written to ave_timeline.png")

    tracks = build_protocol_tracks(timeline)

    carrier_tracking_config = analysis_config["carrier_tracking"]
    carrier_tracks = build_carrier_tracks(
        timeline,
        max_frequency_jump_hz=carrier_tracking_config["max_frequency_jump_hz"],
        max_gap_windows=carrier_tracking_config["max_gap_windows"],
        min_track_windows=carrier_tracking_config["min_track_windows"],
    )

    carrier_pairing_config = analysis_config["carrier_pairing"]
    carrier_pairs = associate_carrier_pairs(
        carrier_tracks,
        min_overlap_ratio=carrier_pairing_config["min_overlap_ratio"],
        max_pair_difference_hz=carrier_pairing_config["max_pair_difference_hz"],
        min_difference_hz=carrier_pairing_config["min_difference_hz"],
        min_duration_seconds=carrier_pairing_config["min_duration_seconds"],
        min_amplitude_balance=carrier_pairing_config["min_amplitude_balance"],
    )

    selected_carrier_pairs = select_best_carrier_pairs(carrier_pairs)
    evidence_provenance = {
        "run_id": run_provenance["run_id"],
        "input_sha256": run_provenance["input"]["sha256"],
        "recording_id": (
            run_provenance["recording_manifest"]["recording_id"]
            if run_provenance["recording_manifest"]
            else None
        ),
        "analysis_configuration_version": analysis_config[
            "configuration_schema_version"
        ],
    }
    evidence_objects = [
        carrier_pair_to_evidence(pair, evidence_provenance)
        for pair in selected_carrier_pairs
    ]

    left_envelope_timeline = None
    right_envelope_timeline = None
    phase_timeline = None

    print("\nBest non-conflicting carrier-pair associations:")

    for pair in selected_carrier_pairs[:25]:
        print(
            f"{pair['start_seconds']:>7.2f}s - "
            f"{pair['end_seconds']:>7.2f}s | "
            f"L {pair['left_carrier_hz']:.3f} Hz ↔ "
            f"R {pair['right_carrier_hz']:.3f} Hz | "
            f"Δ {pair['difference_hz']:.3f} Hz | "
            f"{pair['pair_type']} | "
            f"duration {pair['duration_seconds']:.1f}s | "
            f"confidence {pair['confidence']:.4f}"
        )

    envelope_config = analysis_config["envelope"]
    envelope_carrier_pair = select_envelope_carrier_pair(
        selected_carrier_pairs,
        minimum_center_hz=envelope_config["minimum_carrier_center_hz"],
    )

    if envelope_carrier_pair:
        strongest_pair = envelope_carrier_pair

        carrier_center_hz = (
            strongest_pair["left_carrier_hz"]
            + strongest_pair["right_carrier_hz"]
        ) / 2.0

        left_audio = y[0] if y.ndim > 1 else y
        right_audio = y[1] if y.ndim > 1 else y

        left_envelope_result = analyze_carrier_envelope(
            audio=left_audio,
            sample_rate=sr,
            center_frequency_hz=carrier_center_hz,
            bandwidth_hz=envelope_config["bandwidth_hz"],
            envelope_sample_rate=envelope_config["sample_rate"],
            min_modulation_hz=envelope_config["global_min_modulation_hz"],
            max_modulation_hz=envelope_config["global_max_modulation_hz"],
        )

        right_envelope_result = analyze_carrier_envelope(
            audio=right_audio,
            sample_rate=sr,
            center_frequency_hz=carrier_center_hz,
            bandwidth_hz=envelope_config["bandwidth_hz"],
            envelope_sample_rate=envelope_config["sample_rate"],
            min_modulation_hz=envelope_config["global_min_modulation_hz"],
            max_modulation_hz=envelope_config["global_max_modulation_hz"],
        )

        left_envelope_timeline = analyze_envelope_over_time(
            audio=left_audio,
            sample_rate=sr,
            center_frequency_hz=carrier_center_hz,
            bandwidth_hz=envelope_config["bandwidth_hz"],
            window_seconds=envelope_config["window_seconds"],
            hop_seconds=envelope_config["hop_seconds"],
            envelope_sample_rate=envelope_config["sample_rate"],
            min_modulation_hz=envelope_config["timeline_min_modulation_hz"],
            max_modulation_hz=envelope_config["timeline_max_modulation_hz"],
        )

        right_envelope_timeline = analyze_envelope_over_time(
            audio=right_audio,
            sample_rate=sr,
            center_frequency_hz=carrier_center_hz,
            bandwidth_hz=envelope_config["bandwidth_hz"],
            window_seconds=envelope_config["window_seconds"],
            hop_seconds=envelope_config["hop_seconds"],
            envelope_sample_rate=envelope_config["sample_rate"],
            min_modulation_hz=envelope_config["timeline_min_modulation_hz"],
            max_modulation_hz=envelope_config["timeline_max_modulation_hz"],
        )

        print_global_envelope_results(
            carrier_center_hz=carrier_center_hz,
            left_result=left_envelope_result,
            right_result=right_envelope_result,
        )
        evidence_objects.extend(
            [
                envelope_analysis_to_evidence(
                    left_envelope_result,
                    "left",
                    evidence_provenance,
                ),
                envelope_analysis_to_evidence(
                    right_envelope_result,
                    "right",
                    evidence_provenance,
                ),
            ]
        )

        print_envelope_timeline(
            left_timeline=left_envelope_timeline,
            right_timeline=right_envelope_timeline,
            limit=20,
        )

        modulation_config = analysis_config["modulation_spectrum"]
        modulation_result = analyze_modulation_spectrum(
            left_timeline=left_envelope_timeline,
            right_timeline=right_envelope_timeline,
            max_frequency_jump_hz=modulation_config["max_frequency_jump_hz"],
            max_stereo_difference_hz=modulation_config[
                "max_stereo_difference_hz"
            ],
            min_track_windows=modulation_config["min_track_windows"],
            min_relative_power=modulation_config["min_relative_power"],
            min_modulation_depth=modulation_config["min_modulation_depth"],
        )

        print_modulation_spectrum_summary(modulation_result)
        evidence_objects.append(
            modulation_spectrum_to_evidence(
                modulation_result,
                evidence_provenance,
            )
        )

        phase_config = analysis_config["phase"]
        phase_timeline = analyze_phase_over_time(
            left_audio=left_audio,
            right_audio=right_audio,
            sample_rate=sr,
            left_center_frequency_hz=strongest_pair["left_carrier_hz"],
            right_center_frequency_hz=strongest_pair["right_carrier_hz"],
            bandwidth_hz=phase_config["bandwidth_hz"],
            window_seconds=phase_config["window_seconds"],
            hop_seconds=phase_config["hop_seconds"],
            trim_seconds=phase_config["trim_seconds"],
        )

        print_phase_timeline(phase_timeline, limit=20)
        evidence_objects.append(
            phase_timeline_to_evidence(
                phase_timeline,
                evidence_provenance,
            )
        )
    else:
        print("\nCarrier-envelope analysis:")
        print("No suitable acoustic carrier pair was available for envelope analysis.")

    print("\nPersistent left-channel carriers:")
    for track in carrier_tracks["left_tracks"][:15]:
        print(
            f"{track['start_seconds']:>7.2f}s - "
            f"{track['end_seconds']:>7.2f}s | "
            f"{track['average_frequency_hz']:.3f} Hz | "
            f"duration {track['duration_seconds']:.1f}s | "
            f"stability {track['frequency_stability']:.4f} | "
            f"continuity {track['continuity']:.4f} | "
            f"magnitude {track['average_magnitude']:.4f}"
        )

    print("\nPersistent right-channel carriers:")
    for track in carrier_tracks["right_tracks"][:15]:
        print(
            f"{track['start_seconds']:>7.2f}s - "
            f"{track['end_seconds']:>7.2f}s | "
            f"{track['average_frequency_hz']:.3f} Hz | "
            f"duration {track['duration_seconds']:.1f}s | "
            f"stability {track['frequency_stability']:.4f} | "
            f"continuity {track['continuity']:.4f} | "
            f"magnitude {track['average_magnitude']:.4f}"
        )

    print("\nPersistent cross-channel carrier pairs:")

    for pair in carrier_pairs[:25]:
        print(
            f"{pair['start_seconds']:>7.2f}s - "
            f"{pair['end_seconds']:>7.2f}s | "
            f"L {pair['left_carrier_hz']:.3f} Hz ↔ "
            f"R {pair['right_carrier_hz']:.3f} Hz | "
            f"Δ {pair['difference_hz']:.3f} Hz | "
            f"{pair['pair_type']} | "
            f"duration {pair['duration_seconds']:.1f}s | "
            f"overlap {pair['overlap_ratio']:.3f} | "
            f"balance {pair['amplitude_balance']:.3f} | "
            f"confidence {pair['confidence']:.4f}"
        )

    from analysis.protocol_hypothesis import score_hypothesis

    print("\nHypothesis score diagnostic:")
    for t in tracks[:25]:
        s = score_hypothesis(t)
        print(
            f"{t['average_difference_hz']} Hz | " f"{t['brainwave_band']} | " f"score {s}"
        )

    print("\nProtocol tracks:")
    for t in tracks[:25]:
        print(
            f"{t['start_seconds']:>7.2f}s - {t['end_seconds']:>7.2f}s | "
            f"{t['average_difference_hz']} Hz "
            f"({t['brainwave_band']}) | "
            f"duration {t['duration_seconds']}s | "
            f"confidence {t['average_confidence']} | "
            f"stability {t['frequency_stability']} | "
            f"score {t['score']}"
        )

    hypothesis_config = analysis_config["hypothesis"]
    raw_hypotheses = generate_protocol_hypotheses(
        tracks,
        min_score=hypothesis_config["minimum_score"],
    )
    hypotheses = deduplicate_hypotheses(
        raw_hypotheses,
        tolerance_hz=hypothesis_config["deduplication_tolerance_hz"],
    )
    evidence_objects.extend(
        protocol_hypothesis_to_evidence(
            hypothesis,
            evidence_provenance,
        )
        for hypothesis in hypotheses
    )

    from analysis.speech_context import build_speech_context_analysis
    from transcripts.sidecar import (
        TranscriptSidecarError,
        transcript_sidecar_path_for,
        validate_transcript_sidecar,
    )

    transcript_path = transcript_sidecar_path_for(input_path)
    if transcript_path.exists():
        try:
            transcript_sidecar = json.loads(transcript_path.read_text())
            validate_transcript_sidecar(transcript_sidecar)
            if transcript_sidecar["recording"]["sha256"] != run_provenance["input"]["sha256"]:
                raise TranscriptSidecarError(
                    "transcript sidecar SHA-256 does not match analysis input"
                )
            speech_config = analysis_config["speech_context"]
            speech_context = build_speech_context_analysis(
                transcript_sidecar=transcript_sidecar,
                duration_seconds=metadata["duration_seconds"],
                entrainment_timeline=timeline,
                left_envelope_timeline=left_envelope_timeline,
                right_envelope_timeline=right_envelope_timeline,
                phase_timeline=phase_timeline,
                padding_seconds=speech_config["padding_seconds"],
                active_minimum_overlap=speech_config["active_minimum_overlap"],
                sparse_maximum_overlap=speech_config["sparse_maximum_overlap"],
            )
            supporting_ids = [
                item["evidence_id"]
                for item in evidence_objects
                if item["evidence_type"]
                in {
                    "carrier_envelope_analysis",
                    "time_resolved_phase_relationship",
                }
            ]
            evidence_objects.append(
                speech_context_to_evidence(
                    speech_context,
                    evidence_provenance,
                    supporting_evidence_ids=supporting_ids,
                )
            )
            with open(output_path("ave_speech_context.json"), "w") as output_file:
                json.dump(speech_context, output_file, indent=2, sort_keys=True)
                output_file.write("\n")
            active = speech_context["window_analyses"]["entrainment"]["speech_active"]
            sparse = speech_context["window_analyses"]["entrainment"]["speech_sparse"]
            print("\nSpeech-aware signal comparison:")
            print(
                f"  speech-active windows: {active['window_count']} "
                f"(candidate rate {active['candidate_window_rate']})"
            )
            print(
                f"  speech-sparse windows: {sparse['window_count']} "
                f"(candidate rate {sparse['candidate_window_rate']})"
            )
            print("Speech context written to ave_speech_context.json")
        except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as error:
            print(f"\nSpeech-aware signal comparison skipped: {error}")
    else:
        print("\nSpeech-aware signal comparison: no transcript sidecar available")

    print("\nGenerated protocol hypotheses:")
    for h in hypotheses[:25]:
        print(
            f"{h['intent']} | "
            f"{h['average_difference_hz']} Hz "
            f"({h['brainwave_band']}) | "
            f"duration {h['duration_seconds']}s | "
            f"confidence {h['average_confidence']} | "
            f"stability {h['frequency_stability']} | "
            f"score {h['hypothesis_score']}"
        )

    export_tracks_csv(tracks, output_path("ave_protocol_tracks.csv"))
    export_hypotheses_csv(
        hypotheses,
        output_path("ave_protocol_hypotheses.csv"),
    )
    export_evidence_json(
        evidence_objects,
        output_path("ave_evidence.json"),
        run_metadata={
            "input_path": run_provenance["input"]["relative_path"],
            "sample_rate": sr,
            "duration_seconds": metadata["duration_seconds"],
        },
        run_provenance=run_provenance,
    )

    print("\nProtocol tracks written to ave_protocol_tracks.csv")
    print("Protocol hypotheses written to ave_protocol_hypotheses.csv")
    print(f"Canonical evidence written to ave_evidence.json ({len(evidence_objects)} objects)")

    protocol_summary = generate_protocol_summary(hypotheses)

    with open(output_path("ave_protocol_summary.md"), "w") as f:
        f.write(protocol_summary)

    print("Protocol summary written to ave_protocol_summary.md")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Analyze one recording with AVE Forensics Laboratory."
    )
    parser.add_argument(
        "audio_path",
        nargs="?",
        default=DEFAULT_AUDIO_PATH,
        help="Audio recording to analyze.",
    )
    parser.add_argument(
        "--output-dir",
        default=".",
        help="Directory for generated analysis artifacts.",
    )
    arguments = parser.parse_args()
    main(arguments.audio_path, arguments.output_dir)
