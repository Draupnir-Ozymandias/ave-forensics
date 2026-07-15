def classify_protocol_intent(freq):
    if 0.5 <= freq < 4:
        return "delta relaxation / sleep-depth candidate"
    if 4 <= freq < 8:
        return "theta meditative / hypnagogic candidate"
    if 8 <= freq < 13:
        return "alpha relaxation / inward-focus candidate"
    if 13 <= freq < 30:
        return "beta focus / cognitive activation candidate"
    if 30 <= freq <= 40:
        return "low-gamma binding / high-cognition candidate"
    return "outside typical entrainment interpretation range"


def score_hypothesis(track):
    freq = track["average_difference_hz"]
    duration = track["duration_seconds"]
    stability = track["frequency_stability"]
    confidence = track["average_confidence"]

    duration_score = min(duration / 300, 1.0)

    if 0.5 <= freq <= 40:
        range_score = 1.0
    else:
        range_score = 0.25

    if 0.5 <= freq < 4:
        plausibility = 1.25
    elif 4 <= freq < 8:
        plausibility = 1.4
    elif 8 <= freq < 13:
        plausibility = 1.35
    elif 13 <= freq < 30:
        plausibility = 0.75
    elif 30 <= freq <= 40:
        plausibility = 0.35
    else:
        plausibility = 0.1

    return round(
        confidence * stability * duration_score * range_score * plausibility,
        4,
    )


def generate_protocol_hypotheses(tracks, min_score=0.005):
    hypotheses = []

    for track in tracks:
        score = score_hypothesis(track)

        if score < min_score:
            continue

        freq = track["average_difference_hz"]

        hypotheses.append(
            {
                "intent": classify_protocol_intent(freq),
                "average_difference_hz": freq,
                "brainwave_band": track["brainwave_band"],
                "duration_seconds": track["duration_seconds"],
                "average_confidence": track["average_confidence"],
                "frequency_stability": track["frequency_stability"],
                "hypothesis_score": score,
                "evidence_type": "persistent_frequency_track",
            }
        )

    return sorted(
        hypotheses,
        key=lambda x: x["hypothesis_score"],
        reverse=True,
    )


def deduplicate_hypotheses(hypotheses, tolerance_hz=0.35):
    deduped = []

    for h in hypotheses:
        matched = False

        for existing in deduped:
            same_band = h["brainwave_band"] == existing["brainwave_band"]
            close_freq = (
                abs(h["average_difference_hz"] - existing["average_difference_hz"])
                <= tolerance_hz
            )

            if same_band and close_freq:
                matched = True

                if h["hypothesis_score"] > existing["hypothesis_score"]:
                    existing.update(h)

                break

        if not matched:
            deduped.append(h)

    return sorted(
        deduped,
        key=lambda x: x["hypothesis_score"],
        reverse=True,
    )
