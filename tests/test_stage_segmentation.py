import numpy as np

from analysis.stage_segmentation import analyze_audio_stages


def staged_signal(sample_rate=4000):
    stage_seconds = 5.0
    samples = int(stage_seconds * sample_rate)
    time = np.arange(samples) / sample_rate
    left_1 = 0.8 * np.sin(2 * np.pi * 440.0 * time)
    right_1 = 0.8 * np.sin(2 * np.pi * 450.0 * time)
    smooth_envelope = 0.5 * (1.0 + np.sin(2 * np.pi * 10.0 * time))
    smooth = 0.8 * smooth_envelope * np.sin(2 * np.pi * 440.0 * time)
    phase = np.mod(time * 10.0, 1.0)
    gated = 0.8 * (phase < 0.25) * np.sin(2 * np.pi * 440.0 * time)
    return np.vstack(
        [
            np.concatenate([left_1, smooth, gated]),
            np.concatenate([right_1, smooth, gated]),
        ]
    )


def test_detects_three_stages_without_declared_boundaries():
    result = analyze_audio_stages(staged_signal(), 4000)

    assert result["classification"] == "segmented_audio_stages"
    assert result["stage_count"] == 3
    assert result["transition_times_seconds"] == [5.0, 10.0]
    assert [stage["construction_class"] for stage in result["stages"]] == [
        "binaural_construction",
        "smooth_amplitude_modulation",
        "hard_gated_pulse",
    ]
    assert result["stages"][0]["interchannel_frequency_difference_hz"] == 10.0
    assert abs(result["stages"][1]["pulse_rate_hz"] - 10.0) < 0.1
    assert abs(result["stages"][2]["duty_cycle_fraction"] - 0.25) < 0.03


def test_constant_construction_remains_one_stage():
    sample_rate = 4000
    time = np.arange(sample_rate * 5) / sample_rate
    signal = 0.5 * np.sin(2 * np.pi * 440.0 * time)

    result = analyze_audio_stages(np.vstack([signal, signal]), sample_rate)

    assert result["classification"] == "single_or_unresolved_stage"
    assert result["stage_count"] == 1
    assert result["transition_times_seconds"] == []
