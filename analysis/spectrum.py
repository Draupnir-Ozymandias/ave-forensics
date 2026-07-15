import numpy as np
from scipy.signal import find_peaks


def analyze_spectrum(y, sr, top_n=10, min_frequency=1.0, max_frequency=5000.0):
    """
    FFT peak detection with duplicate-bin cleanup.
    If stereo, averages channels for initial global spectrum.
    """
    if y.ndim > 1:
        y_mono = np.mean(y, axis=0)
    else:
        y_mono = y

    window = np.hanning(len(y_mono))
    yf = np.fft.rfft(y_mono * window)
    xf = np.fft.rfftfreq(len(y_mono), 1 / sr)

    magnitude = np.abs(yf)
    magnitude = magnitude / np.max(magnitude)

    freq_mask = (xf >= min_frequency) & (xf <= max_frequency)
    xf_range = xf[freq_mask]
    mag_range = magnitude[freq_mask]

    peaks, _ = find_peaks(
        mag_range,
        distance=200,
        prominence=0.01,
    )

    peak_data = [(float(xf_range[i]), float(mag_range[i])) for i in peaks]
    peak_data = sorted(peak_data, key=lambda x: x[1], reverse=True)

    return {
        "frequencies": xf,
        "magnitude": magnitude,
        "top_peaks": peak_data[:top_n],
    }
