import numpy as np
from analysis.spectrum import analyze_spectrum


def analyze_stereo(y, sr):
    if y.ndim == 1:
        return {
            "is_stereo": False,
            "message": "Mono file. Stereo/binaural analysis not available.",
        }

    left = y[0]
    right = y[1]

    correlation = float(np.corrcoef(left, right)[0, 1])

    left_spectrum = analyze_spectrum(left, sr, top_n=10)
    right_spectrum = analyze_spectrum(right, sr, top_n=10)

    binaural_candidates = []

    for lf, lm in left_spectrum["top_peaks"]:
        for rf, rm in right_spectrum["top_peaks"]:
            diff = abs(lf - rf)

            if 0.5 <= diff <= 40:
                binaural_candidates.append(
                    {
                        "left_hz": round(lf, 3),
                        "right_hz": round(rf, 3),
                        "difference_hz": round(diff, 3),
                        "left_magnitude": round(lm, 4),
                        "right_magnitude": round(rm, 4),
                    }
                )

    binaural_candidates = sorted(binaural_candidates, key=lambda x: x["difference_hz"])

    return {
        "is_stereo": True,
        "left_right_correlation": round(correlation, 4),
        "left_top_peaks": left_spectrum["top_peaks"],
        "right_top_peaks": right_spectrum["top_peaks"],
        "binaural_candidates": binaural_candidates,
    }
