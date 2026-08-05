import numpy as np
from scipy.signal import find_peaks


def _segment_starts(total_samples, segment_samples, max_segments):
    if total_samples <= segment_samples:
        return [0]

    return np.linspace(
        0,
        total_samples - segment_samples,
        num=max_segments,
        dtype=np.int64,
    ).tolist()


def analyze_spectrum(
    y,
    sr,
    top_n=10,
    min_frequency=1.0,
    max_frequency=5000.0,
    max_fft_seconds=60.0,
    max_segments=8,
):
    """
    FFT peak detection with duplicate-bin cleanup.
    If stereo, averages channels for initial global spectrum.
    """
    if max_fft_seconds <= 0:
        raise ValueError("max_fft_seconds must be positive")
    if max_segments <= 0:
        raise ValueError("max_segments must be positive")

    total_samples = y.shape[-1]
    segment_samples = min(total_samples, int(max_fft_seconds * sr))
    if segment_samples == 0:
        raise ValueError("cannot analyze an empty audio signal")

    starts = _segment_starts(total_samples, segment_samples, max_segments)
    window = np.hanning(segment_samples)
    magnitude = None

    for start in starts:
        chunk = y[..., start : start + segment_samples]
        y_mono = np.mean(chunk, axis=0) if chunk.ndim > 1 else chunk
        segment_magnitude = np.abs(np.fft.rfft(y_mono * window))
        if magnitude is None:
            magnitude = segment_magnitude
        else:
            magnitude += segment_magnitude

    magnitude /= len(starts)
    peak_magnitude = np.max(magnitude)
    if peak_magnitude > 0:
        magnitude /= peak_magnitude

    xf = np.fft.rfftfreq(segment_samples, 1 / sr)

    freq_mask = (xf >= min_frequency) & (xf <= max_frequency)
    xf_range = xf[freq_mask]
    mag_range = magnitude[freq_mask]

    frequency_resolution = sr / segment_samples
    minimum_peak_distance_bins = max(1, round(0.1 / frequency_resolution))
    peaks, _ = find_peaks(
        mag_range,
        distance=minimum_peak_distance_bins,
        prominence=0.01,
    )

    peak_data = [(float(xf_range[i]), float(mag_range[i])) for i in peaks]
    peak_data = sorted(peak_data, key=lambda x: x[1], reverse=True)

    return {
        "frequencies": xf,
        "magnitude": magnitude,
        "top_peaks": peak_data[:top_n],
    }
