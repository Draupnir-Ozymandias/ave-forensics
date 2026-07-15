import numpy as np

from analysis.stereo import analyze_stereo
from analysis.entrainment import classify_binaural_candidates


def window_audio(y, sr, window_seconds=10, hop_seconds=5):
    total_samples = y.shape[-1]
    window_size = int(window_seconds * sr)
    hop_size = int(hop_seconds * sr)

    windows = []

    for start in range(0, total_samples - window_size + 1, hop_size):
        end = start + window_size

        if y.ndim == 1:
            chunk = y[start:end]
        else:
            chunk = y[:, start:end]

        windows.append(
            {
                "start_seconds": round(start / sr, 3),
                "end_seconds": round(end / sr, 3),
                "audio": chunk,
            }
        )

    return windows


def analyze_time_resolved(y, sr, window_seconds=10, hop_seconds=5):
    windows = window_audio(y, sr, window_seconds, hop_seconds)
    timeline = []

    for w in windows:
        stereo = analyze_stereo(w["audio"], sr)
        candidates = classify_binaural_candidates(stereo.get("binaural_candidates", []))

        top_candidate = candidates[0] if candidates else None

        timeline.append(
            {
                "start_seconds": w["start_seconds"],
                "end_seconds": w["end_seconds"],
                "left_right_correlation": stereo.get("left_right_correlation"),
                "top_candidate": top_candidate,
                "candidates": candidates,
                "candidate_count": len(candidates),
            }
        )

    return timeline
