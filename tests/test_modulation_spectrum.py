import numpy as np
from scipy.signal import chirp

from analysis.envelope import analyze_envelope_over_time
from analysis.modulation_spectrum import analyze_modulation_spectrum


SAMPLE_RATE = 2000
CARRIER_HZ = 100.0


def generate_am_signal(
    duration_seconds: float,
    modulation_components: list[tuple[float, float]],
) -> np.ndarray:
    time = np.arange(int(SAMPLE_RATE * duration_seconds)) / SAMPLE_RATE
    envelope = np.ones_like(time)

    for modulation_hz, depth in modulation_components:
        envelope += depth * np.sin(2.0 * np.pi * modulation_hz * time)

    return envelope * np.sin(2.0 * np.pi * CARRIER_HZ * time)


def generate_modulation_ramp(
    duration_seconds: float,
    start_hz: float,
    end_hz: float,
    depth: float = 0.6,
) -> np.ndarray:
    time = np.arange(int(SAMPLE_RATE * duration_seconds)) / SAMPLE_RATE
    modulator = chirp(
        time,
        f0=start_hz,
        f1=end_hz,
        t1=duration_seconds,
        method="linear",
        phi=-90.0,
    )
    envelope = 1.0 + depth * modulator
    return envelope * np.sin(2.0 * np.pi * CARRIER_HZ * time)


def envelope_timeline(audio: np.ndarray) -> list[dict]:
    return analyze_envelope_over_time(
        audio=audio,
        sample_rate=SAMPLE_RATE,
        center_frequency_hz=CARRIER_HZ,
        bandwidth_hz=20.0,
        window_seconds=6.0,
        hop_seconds=3.0,
        envelope_sample_rate=200,
        min_modulation_hz=0.5,
        max_modulation_hz=10.0,
    )


def test_reconstructs_persistent_three_hz_modulation():
    audio = generate_am_signal(24.0, [(3.0, 0.6)])
    timeline = envelope_timeline(audio)

    result = analyze_modulation_spectrum(timeline, timeline)

    primary = result["primary_stereo_modulation"]
    assert primary is not None
    assert abs(primary["average_modulation_hz"] - 3.0) < 0.2
    assert primary["shared_coverage"] == 1.0
    assert result["classification"] == "persistent_shared_amplitude_modulation"


def test_preserves_multiple_modulation_components():
    audio = generate_am_signal(24.0, [(3.0, 0.5), (7.0, 0.3)])
    timeline = envelope_timeline(audio)

    result = analyze_modulation_spectrum(timeline, timeline)
    frequencies = [
        track["average_modulation_hz"]
        for track in result["left_tracks"]
    ]

    assert any(abs(frequency - 3.0) < 0.2 for frequency in frequencies)
    assert any(abs(frequency - 7.0) < 0.2 for frequency in frequencies)


def test_reconstructs_modulation_ramp():
    audio = generate_modulation_ramp(30.0, 2.0, 6.0)
    timeline = envelope_timeline(audio)

    result = analyze_modulation_spectrum(
        timeline,
        timeline,
        max_frequency_jump_hz=1.5,
    )

    assert result["classification"] == "shared_modulation_ramp"
    assert result["left_tracks"][0]["classification"] == "modulation_ramp"
    assert result["left_tracks"][0]["frequency_span_hz"] >= 2.0
    assert result["left_tracks"][0]["drift_hz_per_second"] > 0.05


def test_rejects_unmodulated_carrier():
    audio = generate_am_signal(24.0, [])
    timeline = envelope_timeline(audio)

    result = analyze_modulation_spectrum(timeline, timeline)

    assert result["classification"] == "no_significant_modulation"
    assert result["left_tracks"] == []
    assert result["right_tracks"] == []


def test_distinguishes_channel_specific_modulation():
    left_timeline = envelope_timeline(
        generate_am_signal(24.0, [(3.0, 0.6)])
    )
    right_timeline = envelope_timeline(
        generate_am_signal(24.0, [(5.0, 0.6)])
    )

    result = analyze_modulation_spectrum(
        left_timeline,
        right_timeline,
    )

    assert result["classification"] == "channel_specific_modulation"
    assert result["stereo_associations"] == []
