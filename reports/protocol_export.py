import csv


def export_tracks_csv(tracks, output_path="ave_protocol_tracks.csv"):
    fields = [
        "start_seconds",
        "end_seconds",
        "duration_seconds",
        "average_difference_hz",
        "brainwave_band",
        "average_confidence",
        "frequency_stability",
        "window_count",
        "score",
    ]

    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()

        for t in tracks:
            writer.writerow({key: t.get(key, "") for key in fields})


def export_hypotheses_csv(hypotheses, output_path="ave_protocol_hypotheses.csv"):
    fields = [
        "intent",
        "average_difference_hz",
        "brainwave_band",
        "duration_seconds",
        "average_confidence",
        "frequency_stability",
        "hypothesis_score",
        "evidence_type",
    ]

    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()

        for h in hypotheses:
            writer.writerow({key: h.get(key, "") for key in fields})
