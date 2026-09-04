from analysis.carrier_tracker import (
    associate_carrier_pairs,
    build_carrier_tracks,
    classify_carrier_pair,
    select_best_carrier_pairs,
)

def make_peak(freq: float, magnitude: float = 1.0) -> dict[str, float]:
    return {
        "frequency_hz": freq,
        "magnitude": magnitude,
    }


def test_tracks_stable_left_and_right_carriers():
    timeline = []

    for index in range(10):
        timeline.append(
            {
                "window_index": index,
                "start_seconds": index * 5.0,
                "end_seconds": index * 5.0 + 10.0,
                "left_peaks": [
                    make_peak(348.0 + index * 0.01, 0.80),
                ],
                "right_peaks": [
                    make_peak(350.0 + index * 0.01, 0.75),
                ],
            }
        )

    result = build_carrier_tracks(
        timeline,
        max_frequency_jump_hz=0.5,
        max_gap_windows=1,
        min_track_windows=5,
    )

    assert len(result["left_tracks"]) == 1
    assert len(result["right_tracks"]) == 1

    left = result["left_tracks"][0]
    right = result["right_tracks"][0]

    assert abs(left["average_frequency_hz"] - 348.045) < 0.1
    assert abs(right["average_frequency_hz"] - 350.045) < 0.1

    assert left["window_count"] == 10
    assert right["window_count"] == 10

    assert left["continuity"] == 1.0
    assert right["continuity"] == 1.0


def test_associates_persistent_cross_channel_pair():
    timeline = []

    for index in range(12):
        timeline.append(
            {
                "window_index": index,
                "start_seconds": index * 5.0,
                "end_seconds": index * 5.0 + 10.0,
                "left_peaks": [
                    make_peak(348.0 + index * 0.01, 0.80),
                ],
                "right_peaks": [
                    make_peak(350.0 + index * 0.01, 0.76),
                ],
            }
        )

    tracks = build_carrier_tracks(
        timeline,
        max_frequency_jump_hz=0.5,
        max_gap_windows=1,
        min_track_windows=5,
    )

    pairs = associate_carrier_pairs(
        tracks,
        min_overlap_ratio=0.9,
        max_pair_difference_hz=10.0,
        min_duration_seconds=30.0,
        min_amplitude_balance=0.5,
    )

    assert len(pairs) == 1

    pair = pairs[0]

    assert abs(pair["left_carrier_hz"] - 348.055) < 0.1
    assert abs(pair["right_carrier_hz"] - 350.055) < 0.1
    assert abs(pair["difference_hz"] - 2.0) < 0.1

    assert pair["duration_seconds"] >= 60.0
    assert pair["overlap_ratio"] == 1.0
    assert pair["amplitude_balance"] > 0.9
    assert pair["confidence"] > 0


def test_selects_non_conflicting_best_pairs():
    pairs = [
        {
            "left_track_index": 0,
            "right_track_index": 0,
            "confidence": 0.90,
            "duration_seconds": 100.0,
            "overlap_ratio": 1.0,
            "amplitude_balance": 0.95,
        },
        {
            "left_track_index": 0,
            "right_track_index": 1,
            "confidence": 0.70,
            "duration_seconds": 100.0,
            "overlap_ratio": 1.0,
            "amplitude_balance": 0.95,
        },
        {
            "left_track_index": 1,
            "right_track_index": 1,
            "confidence": 0.80,
            "duration_seconds": 100.0,
            "overlap_ratio": 1.0,
            "amplitude_balance": 0.95,
        },
    ]

    selected = select_best_carrier_pairs(pairs)

    assert len(selected) == 2
    assert selected[0]["left_track_index"] == 0
    assert selected[0]["right_track_index"] == 0
    assert selected[1]["left_track_index"] == 1
    assert selected[1]["right_track_index"] == 1


def test_classifies_obvious_octave_as_harmonic_relationship():
    assert classify_carrier_pair(29.1, 29.1, 58.2) == "harmonic_relationship"
    assert classify_carrier_pair(2.0, 100.0, 102.0) == "beat_candidate"
