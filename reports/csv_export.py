import csv


def export_timeline_csv(timeline, output_path="ave_timeline.csv"):
    fields = [
        "start_seconds",
        "end_seconds",
        "left_right_correlation",
        "candidate_count",
        "left_hz",
        "right_hz",
        "difference_hz",
        "brainwave_band",
        "confidence",
    ]

    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()

        for item in timeline:
            c = item.get("top_candidate")

            row = {
                "start_seconds": item["start_seconds"],
                "end_seconds": item["end_seconds"],
                "left_right_correlation": item.get("left_right_correlation"),
                "candidate_count": item.get("candidate_count", 0),
                "left_hz": "",
                "right_hz": "",
                "difference_hz": "",
                "brainwave_band": "",
                "confidence": "",
            }

            if c:
                row.update(
                    {
                        "left_hz": c["left_hz"],
                        "right_hz": c["right_hz"],
                        "difference_hz": c["difference_hz"],
                        "brainwave_band": c["brainwave_band"],
                        "confidence": c["confidence"],
                    }
                )

            writer.writerow(row)
