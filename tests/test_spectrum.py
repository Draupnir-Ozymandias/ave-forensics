import numpy as np

from analysis.spectrum import analyze_spectrum


def test_long_signal_uses_bounded_representative_fft(monkeypatch):
    sample_rate = 100
    audio = np.zeros((2, sample_rate * 100), dtype=np.float32)
    observed_lengths = []
    real_rfft = np.fft.rfft

    def recording_rfft(values):
        observed_lengths.append(len(values))
        return real_rfft(values)

    monkeypatch.setattr(np.fft, "rfft", recording_rfft)
    result = analyze_spectrum(
        audio,
        sample_rate,
        max_fft_seconds=10,
        max_segments=4,
    )

    assert observed_lengths == [1000, 1000, 1000, 1000]
    assert len(result["frequencies"]) == 501


def test_spectrum_rejects_empty_audio():
    with np.testing.assert_raises(ValueError):
        analyze_spectrum(np.array([]), 100)
