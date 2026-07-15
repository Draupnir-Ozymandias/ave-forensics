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


def main():
    audio_path = "samples/Celestial_Wanderings_Unguided_Meditation_60mins_VBR5.mp3"

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

    print("\nProtocol tracks written to ave_protocol_tracks.csv")
    print("Protocol hypotheses written to ave_protocol_hypotheses.csv")

    protocol_summary = generate_protocol_summary(hypotheses)

    with open("ave_protocol_summary.md", "w") as f:
        f.write(protocol_summary)

    print("Protocol summary written to ave_protocol_summary.md")


if __name__ == "__main__":
    main()
