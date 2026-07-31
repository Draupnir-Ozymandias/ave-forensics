import numpy as np

from analysis.spectrum import analyze_spectrum
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


def _format_peaks(peaks):
    """
    Convert spectrum tuples into explicit evidence-like dictionaries.
    """
    return [
        {
            "frequency_hz": round(float(freq), 4),
            "magnitude": round(float(magnitude), 4),
        }
        for freq, magnitude in peaks
    ]


def analyze_time_resolved(
    y,
    sr,
    window_seconds=10,
    hop_seconds=5,
    peaks_per_channel=15,
):
    windows = window_audio(
        y,
        sr,
        window_seconds=window_seconds,
        hop_seconds=hop_seconds,
    )

    timeline = []

    for window_index, w in enumerate(windows):
        chunk = w["audio"]

        if chunk.ndim == 1:
            left_audio = chunk
            right_audio = None
        else:
            left_audio = chunk[0]
            right_audio = chunk[1]

        left_spectrum = analyze_spectrum(
            left_audio,
            sr,
            top_n=peaks_per_channel,
        )

        if right_audio is not None:
            right_spectrum = analyze_spectrum(
                right_audio,
                sr,
                top_n=peaks_per_channel,
            )
        else:
            right_spectrum = {
                "top_peaks": [],
            }

        stereo = analyze_stereo(chunk, sr)

        candidates = classify_binaural_candidates(stereo.get("binaural_candidates", []))

        top_candidate = candidates[0] if candidates else None

        timeline.append(
            {
                "window_index": window_index,
                "start_seconds": w["start_seconds"],
                "end_seconds": w["end_seconds"],
                "left_right_correlation": stereo.get("left_right_correlation"),
                "left_peaks": _format_peaks(left_spectrum["top_peaks"]),
                "right_peaks": _format_peaks(right_spectrum["top_peaks"]),
                "top_candidate": top_candidate,
                "candidates": candidates,
                "candidate_count": len(candidates),
            }
        )

    return timeline
