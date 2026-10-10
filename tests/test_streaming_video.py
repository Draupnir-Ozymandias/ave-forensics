import numpy as np
import json
from pathlib import Path
from types import SimpleNamespace

from analysis.streaming_video import active_runs, trace_measurements
from analysis.streaming_video import observe_streaming_video


def test_on_runs_preserve_initial_and_terminal_edges():
    active = np.array([True, True, False, True, False, False])
    assert active_runs(active).tolist() == [[0, 2], [3, 4]]


def test_trace_recovers_known_gated_frequency_and_duty():
    fps = 120
    frame = np.arange(1200)
    trace = ((frame % 12) < 3).astype(float)
    measured = trace_measurements(trace, fps, 0.5)
    assert measured["total_rising_edges"] == 100
    assert measured["active_fraction"] == 0.25
    assert all(w["edge_rate_hz"] == 10 for w in measured["windows"])
    assert all(w["encoded_duty_fraction"] == 0.25 for w in measured["windows"])


def test_streaming_discovers_four_separated_matched_regions(monkeypatch):
    image = np.zeros((32, 32, 3), dtype=np.uint8)
    for rows in (slice(1, 14), slice(18, 31)):
        for columns in (slice(1, 14), slice(18, 31)):
            image[rows, columns] = 64
    sequence = [np.zeros_like(image), image, np.zeros_like(image), image]
    monkeypatch.setattr("analysis.streaming_video.frames", lambda path, size: iter(sequence))
    monkeypatch.setattr("analysis.streaming_video.probe_video",
                        lambda path: {"refresh_rate_hz": 120.0})
    monkeypatch.setattr("analysis.streaming_video.subprocess.run", lambda *a, **kw:
                        SimpleNamespace(stdout=json.dumps({"frames": [
                            {"best_effort_timestamp_time": str(i / 120)} for i in range(4)
                        ]}).encode()))
    result, traces, pts = observe_streaming_video(Path("unused.mp4"), size=32)
    assert result["region_count"] == 4
    assert result["all_regions_matched_framewise"]
    assert result["pts_audit"]["cadence_outlier_count"] == 0
    assert traces.shape == (4, 4)
    assert len(pts) == 4
    assert all(r["threshold_stable_edges"] for r in result["regions"])
