import statistics


def build_protocol_tracks(
    timeline, max_gap_windows=2, max_freq_jump=1.5, min_track_length=4
):
    """
    Associates candidate detections across adjacent windows into persistent frequency tracks.

    This is not looking for the loudest candidate.
    It is looking for stable protocol-like continuity over time.
    """

    active_tracks = []
    finished_tracks = []

    for window_index, item in enumerate(timeline):
        candidates = item.get("candidates", [])

        assigned = set()

        for track in active_tracks:
            best_match = None
            best_distance = None

            last = track["points"][-1]
            last_freq = last["difference_hz"]

            for idx, c in enumerate(candidates):
                if idx in assigned:
                    continue

                freq = c["difference_hz"]
                distance = abs(freq - last_freq)

                if distance <= max_freq_jump:
                    if best_distance is None or distance < best_distance:
                        best_distance = distance
                        best_match = (idx, c)

            if best_match:
                idx, c = best_match
                assigned.add(idx)

                track["points"].append(
                    {
                        "window_index": window_index,
                        "start_seconds": item["start_seconds"],
                        "end_seconds": item["end_seconds"],
                        "difference_hz": c["difference_hz"],
                        "brainwave_band": c["brainwave_band"],
                        "confidence": c["confidence"],
                        "left_hz": c["left_hz"],
                        "right_hz": c["right_hz"],
                    }
                )

                track["misses"] = 0
            else:
                track["misses"] += 1

        still_active = []

        for track in active_tracks:
            if track["misses"] > max_gap_windows:
                finished_tracks.append(track)
            else:
                still_active.append(track)

        active_tracks = still_active

        for idx, c in enumerate(candidates):
            if idx in assigned:
                continue

            active_tracks.append(
                {
                    "points": [
                        {
                            "window_index": window_index,
                            "start_seconds": item["start_seconds"],
                            "end_seconds": item["end_seconds"],
                            "difference_hz": c["difference_hz"],
                            "brainwave_band": c["brainwave_band"],
                            "confidence": c["confidence"],
                            "left_hz": c["left_hz"],
                            "right_hz": c["right_hz"],
                        }
                    ],
                    "misses": 0,
                }
            )

    finished_tracks.extend(active_tracks)

    scored_tracks = []

    for track in finished_tracks:
        points = track["points"]

        if len(points) < min_track_length:
            continue

        freqs = [p["difference_hz"] for p in points]
        confidences = [p["confidence"] for p in points]
        bands = [p["brainwave_band"] for p in points]

        avg_freq = statistics.mean(freqs)
        avg_conf = statistics.mean(confidences)
        stability = 1 / (1 + statistics.pstdev(freqs))
        duration = points[-1]["end_seconds"] - points[0]["start_seconds"]

        dominant_band = max(set(bands), key=bands.count)

        band_weights = {
            "delta": 1.25,
            "theta": 1.4,
            "alpha": 1.35,
            "beta": 0.85,
            "gamma": 0.35,
        }

        band_weight = band_weights.get(dominant_band, 0.5)

        duration_weight = min(len(points), 30) / 30

        score = avg_conf * stability * duration_weight * band_weight    

        scored_tracks.append(
            {
                "start_seconds": points[0]["start_seconds"],
                "end_seconds": points[-1]["end_seconds"],
                "duration_seconds": round(duration, 3),
                "average_difference_hz": round(avg_freq, 3),
                "frequency_stability": round(stability, 4),
                "average_confidence": round(avg_conf, 4),
                "brainwave_band": dominant_band,
                "window_count": len(points),
                "score": round(score, 4),
                "points": points,
            }
        )

    scored_tracks = sorted(scored_tracks, key=lambda x: x["score"], reverse=True)

    return scored_tracks
