from analysis.speech_context import (
    build_speech_context_analysis,
    classify_windows,
    complement_intervals,
    merge_intervals,
)
from evidence.adapters import speech_context_to_evidence
from evidence.schema import validate_evidence_object
from tests.test_transcript_metadata import import_sidecar


def test_merges_padded_intervals_and_builds_complement():
    merged = merge_intervals(
        [(2.0, 3.0), (3.5, 4.0), (8.0, 9.0)],
        duration_seconds=10.0,
        padding_seconds=0.5,
    )
    assert merged == [(1.5, 4.5), (7.5, 9.5)]
    assert complement_intervals(merged, 10.0) == [
        (0.0, 1.5),
        (4.5, 7.5),
        (9.5, 10.0),
    ]


def test_classifies_active_mixed_and_sparse_windows():
    timeline = [
        {"start_seconds": 0.0, "end_seconds": 10.0},
        {"start_seconds": 10.0, "end_seconds": 20.0},
        {"start_seconds": 20.0, "end_seconds": 30.0},
    ]
    classified = classify_windows(timeline, [(0.0, 8.0), (15.0, 18.0)])
    assert [item["speech_context"] for item in classified] == [
        "speech_active",
        "mixed",
        "speech_sparse",
    ]
    assert [item["speech_overlap_ratio"] for item in classified] == [0.8, 0.3, 0.0]


def test_builds_text_free_signal_comparison(tmp_path):
    _, _, sidecar = import_sidecar(tmp_path)
    timeline = [
        {
            "start_seconds": 1.0,
            "end_seconds": 2.0,
            "top_candidate": {
                "difference_hz": 4.0,
                "confidence": 0.8,
                "brainwave_band": "theta",
            },
        },
        {"start_seconds": 7.0, "end_seconds": 8.0, "top_candidate": None},
    ]

    result = build_speech_context_analysis(
        transcript_sidecar=sidecar,
        duration_seconds=10.0,
        entrainment_timeline=timeline,
        padding_seconds=0.0,
    )

    active = result["window_analyses"]["entrainment"]["speech_active"]
    sparse = result["window_analyses"]["entrainment"]["speech_sparse"]
    assert active["candidate_window_rate"] == 1.0
    assert sparse["candidate_window_rate"] == 0.0
    assert result["comparison"]["candidate_rate_difference_active_minus_sparse"] == 1.0
    assert result["comparison"]["direct_comparison_available"] is True
    assert result["transcript_binding"]["contains_verbatim_text"] is False
    serialized = str(result).lower()
    assert "private source words" not in serialized
    assert "private-job-name" not in serialized

    evidence = speech_context_to_evidence(result)
    validate_evidence_object(evidence)
    assert evidence["evidence_type"] == "speech_context_comparison"
    measurements = {item["name"]: item["value"] for item in evidence["measurements"]}
    assert measurements["speech_active_candidate_rate"] == 1.0
    assert measurements["speech_sparse_candidate_rate"] == 0.0
