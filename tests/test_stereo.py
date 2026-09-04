import numpy as np

from analysis.entrainment import classify_binaural_candidates
from analysis.stereo import simple_harmonic_ratio


def test_detects_simple_integer_harmonics():
    assert simple_harmonic_ratio(29.1, 58.2) == 2
    assert simple_harmonic_ratio(100.0, 300.0) == 3
    assert simple_harmonic_ratio(100.0, 102.0) is None


def test_harmonic_candidate_is_penalized():
    base = {
        "left_hz": 29.1,
        "right_hz": 58.2,
        "difference_hz": 29.1,
        "left_magnitude": 1.0,
        "right_magnitude": 1.0,
    }
    harmonic = classify_binaural_candidates(
        [{**base, "spectral_relationship": "harmonic_2_to_1"}]
    )[0]
    ordinary = classify_binaural_candidates(
        [{**base, "spectral_relationship": "non_harmonic"}]
    )[0]

    assert np.isclose(harmonic["confidence"], ordinary["confidence"] * 0.1)
