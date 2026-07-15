import numpy as np


def describe_audio(y, sr):
    channels = 1 if y.ndim == 1 else y.shape[0]
    samples = y.shape[-1]
    duration = samples / sr

    peak = float(np.max(np.abs(y)))
    rms = float(np.sqrt(np.mean(y**2)))

    return {
        "sample_rate": sr,
        "channels": channels,
        "samples": samples,
        "duration_seconds": round(duration, 3),
        "peak_amplitude": round(peak, 6),
        "rms_level": round(rms, 6),
    }
