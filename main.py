from core.audio_loader import load_audio
from core.metadata import describe_audio
from analysis.spectrum import analyze_spectrum
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
)
from reports.evidence_export import export_evidence_json

def main():
    audio_path = "/Users/eric/Projects/media/ave_forensics/samples/brainfm/meditate/unguided/Altered_State_Unguided_Meditation_Session_4_1.2_Nrmlzd2 1_15mins_VBR5.mp3"
    y, sr = load_audio(audio_path)
    metadata = describe_audio(y, sr)
    spectrum = analyze_spectrum(y, sr)
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

    with open("ave_report.md", "w") as f:
        f.write(report)

    print("\nReport written to ave_report.md")

    timeline = analyze_time_resolved(y, sr, window_seconds=10, hop_seconds=5)

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

    export_timeline_csv(timeline, "ave_timeline.csv")
    print("\nTimeline written to ave_timeline.csv")

    plot_timeline("ave_timeline.csv", "ave_timeline.png")
    print("Timeline plot written to ave_timeline.png")

    tracks = build_protocol_tracks(timeline)

    carrier_tracks = build_carrier_tracks(
        timeline,
        max_frequency_jump_hz=1.0,
        max_gap_windows=2,
        min_track_windows=6,
    )

    carrier_pairs = associate_carrier_pairs(
        carrier_tracks,
        min_overlap_ratio=0.75,
        max_pair_difference_hz=40.0,
        min_difference_hz=0.0,
        min_duration_seconds=30.0,
        min_amplitude_balance=0.25,
    )

    selected_carrier_pairs = select_best_carrier_pairs(carrier_pairs)
    evidence_provenance = {
        "input_path": audio_path,
        "analysis_parameters": {
            "timeline_window_seconds": 10,
            "timeline_hop_seconds": 5,
        },
    }
    evidence_objects = [
        carrier_pair_to_evidence(pair, evidence_provenance)
        for pair in selected_carrier_pairs
    ]

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

    if selected_carrier_pairs:
        strongest_pair = selected_carrier_pairs[0]

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
            bandwidth_hz=8.0,
            envelope_sample_rate=200,
            min_modulation_hz=0.1,
            max_modulation_hz=40.0,
        )

        right_envelope_result = analyze_carrier_envelope(
            audio=right_audio,
            sample_rate=sr,
            center_frequency_hz=carrier_center_hz,
            bandwidth_hz=8.0,
            envelope_sample_rate=200,
            min_modulation_hz=0.1,
            max_modulation_hz=40.0,
        )

        left_envelope_timeline = analyze_envelope_over_time(
            audio=left_audio,
            sample_rate=sr,
            center_frequency_hz=carrier_center_hz,
            bandwidth_hz=8.0,
            window_seconds=30.0,
            hop_seconds=15.0,
            envelope_sample_rate=200,
            min_modulation_hz=0.1,
            max_modulation_hz=10.0,
        )

        right_envelope_timeline = analyze_envelope_over_time(
            audio=right_audio,
            sample_rate=sr,
            center_frequency_hz=carrier_center_hz,
            bandwidth_hz=8.0,
            window_seconds=30.0,
            hop_seconds=15.0,
            envelope_sample_rate=200,
            min_modulation_hz=0.1,
            max_modulation_hz=10.0,
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

        modulation_result = analyze_modulation_spectrum(
            left_timeline=left_envelope_timeline,
            right_timeline=right_envelope_timeline,
        )

        print_modulation_spectrum_summary(modulation_result)
        evidence_objects.append(
            modulation_spectrum_to_evidence(
                modulation_result,
                evidence_provenance,
            )
        )

        phase_timeline = analyze_phase_over_time(
            left_audio=left_audio,
            right_audio=right_audio,
            sample_rate=sr,
            left_center_frequency_hz=strongest_pair["left_carrier_hz"],
            right_center_frequency_hz=strongest_pair["right_carrier_hz"],
            bandwidth_hz=8.0,
            window_seconds=30.0,
            hop_seconds=15.0,
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
        print("No persistent carrier pair was available for envelope analysis.")

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

    raw_hypotheses = generate_protocol_hypotheses(tracks, min_score=0.005)
    hypotheses = deduplicate_hypotheses(raw_hypotheses)       
    evidence_objects.extend(
        protocol_hypothesis_to_evidence(
            hypothesis,
            evidence_provenance,
        )
        for hypothesis in hypotheses
    )

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

    export_tracks_csv(tracks)
    export_hypotheses_csv(hypotheses)
    export_evidence_json(
        evidence_objects,
        run_metadata={
            "input_path": audio_path,
            "sample_rate": sr,
            "duration_seconds": metadata["duration_seconds"],
        },
    )

    print("\nProtocol tracks written to ave_protocol_tracks.csv")
    print("Protocol hypotheses written to ave_protocol_hypotheses.csv")
    print(f"Canonical evidence written to ave_evidence.json ({len(evidence_objects)} objects)")

    protocol_summary = generate_protocol_summary(hypotheses)

    with open("ave_protocol_summary.md", "w") as f:
        f.write(protocol_summary)

    print("Protocol summary written to ave_protocol_summary.md")


if __name__ == "__main__":
    main()
