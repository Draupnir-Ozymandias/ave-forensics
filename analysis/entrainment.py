def classify_brainwave_band(freq):
    if freq < 0.5:
        return "sub-delta / below typical entrainment range"
    if 0.5 <= freq < 4:
        return "delta"
    if 4 <= freq < 8:
        return "theta"
    if 8 <= freq < 13:
        return "alpha"
    if 13 <= freq < 30:
        return "beta"
    if 30 <= freq <= 100:
        return "gamma"
    return "above typical brainwave entrainment range"


def score_candidate(candidate):
    left_mag = candidate["left_magnitude"]
    right_mag = candidate["right_magnitude"]
    diff = candidate["difference_hz"]

    strength = (left_mag + right_mag) / 2
    balance = 1 - abs(left_mag - right_mag)

    if 0.5 <= diff <= 40:
        band_score = 1.0
    else:
        band_score = 0.25

    confidence = strength * balance * band_score
    return round(confidence, 4)


def classify_binaural_candidates(candidates):
    classified = []

    for c in candidates:
        item = dict(c)
        item["brainwave_band"] = classify_brainwave_band(c["difference_hz"])
        item["confidence"] = score_candidate(c)
        classified.append(item)

    classified = sorted(classified, key=lambda x: x["confidence"], reverse=True)

    return classified
