"""Streaming pixel observations for long gated-light videos; no recipe input."""
from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path

import numpy as np
from scipy import ndimage

from analysis.video_regions import probe_video


def frames(path: Path, size: int = 128):
    """Yield one reduced RGB frame at a time, preserving decoded cadence."""
    with tempfile.TemporaryFile() as errors:
        process = subprocess.Popen(
            ["ffmpeg", "-v", "error", "-i", str(path), "-map", "0:v:0",
             "-vf", f"scale={size}:{size}:flags=area", "-fps_mode", "passthrough",
             "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
            stdout=subprocess.PIPE, stderr=errors,
        )
        try:
            frame_bytes = size * size * 3
            while True:
                raw = process.stdout.read(frame_bytes)
                if not raw:
                    break
                if len(raw) != frame_bytes:
                    raise ValueError("partial decoded frame")
                yield np.frombuffer(raw, np.uint8).reshape(size, size, 3)
            if process.wait() != 0:
                errors.seek(0)
                raise ValueError(errors.read().decode(errors="replace"))
        finally:
            process.stdout.close()
            if process.poll() is None:
                process.kill()
                process.wait()


def luminance(frame):
    return np.dot(frame.astype(float) / 255.0, [0.2126, 0.7152, 0.0722])


def active_runs(active):
    changes = np.flatnonzero(np.diff(np.pad(active.astype(np.int8), (1, 1))))
    return changes.reshape(-1, 2)


def trace_measurements(trace, fps, threshold):
    active = trace > threshold
    runs = active_runs(active)
    edges = runs[:, 0]
    windows = []
    length, hop = round(5 * fps), round(fps)
    for start in range(0, max(0, len(active) - length + 1), hop):
        end = start + length
        observed = edges[(edges >= start) & (edges < end)]
        interval = np.diff(observed) / fps
        windows.append({
            "start_seconds": start / fps, "end_seconds": end / fps,
            "rising_edge_count": len(observed),
            "edge_rate_hz": round((len(observed) - 1) / (interval.sum()), 6)
            if len(interval) else None,
            "encoded_duty_fraction": round(float(np.mean(active[start:end])), 6),
        })
    off = active_runs(~active)
    return {
        "threshold": threshold,
        "rising_edge_frames": edges.tolist(),
        "falling_edge_frames": runs[:, 1].tolist(),
        "on_run_frames": (runs[:, 1] - runs[:, 0]).tolist(),
        "total_rising_edges": len(edges),
        "active_fraction": float(np.mean(active)),
        "long_off_intervals": [
            {"start_seconds": start / fps, "end_seconds": end / fps}
            for start, end in off if end - start >= round(0.5 * fps)
        ],
        "windows": windows,
    }


def observe_streaming_video(path: Path, size: int = 128):
    stream = probe_video(path)
    fps = stream["refresh_rate_hz"]
    maximum = np.zeros((size, size), dtype=float)
    count = 0
    for frame in frames(path, size):
        maximum = np.maximum(maximum, luminance(frame))
        count += 1
    if not count:
        raise ValueError("empty video")
    geometry_threshold = max(0.02, float(maximum.max()) * 0.5)
    labels, _ = ndimage.label(maximum > geometry_threshold)
    components = []
    for label in range(1, int(labels.max()) + 1):
        mask = labels == label
        if mask.sum() < size * size * 0.02:
            continue
        y, x = np.nonzero(mask)
        components.append({
            "mask": mask,
            "region_id": ("top" if np.mean(y) < size / 2 else "bottom")
            + "_" + ("left" if np.mean(x) < size / 2 else "right"),
            "bounding_box": [int(x.min()), int(y.min()), int(x.max()+1), int(y.max()+1)],
            "pixel_count": int(mask.sum()),
        })
    components.sort(key=lambda c: (c["bounding_box"][1], c["bounding_box"][0]))
    if not components:
        raise ValueError("no bright spatial components")
    traces = np.empty((count, len(components)), dtype=np.float32)
    for index, frame in enumerate(frames(path, size)):
        gray = luminance(frame)
        for region, component in enumerate(components):
            traces[index, region] = np.median(gray[component["mask"]])
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_frames",
         "-show_entries", "frame=best_effort_timestamp_time", "-of", "json", str(path)],
        capture_output=True, check=True,
    )
    pts = np.asarray([float(f["best_effort_timestamp_time"])
                      for f in json.loads(probe.stdout)["frames"]])
    delta = np.diff(pts)
    regions = []
    for index, component in enumerate(components):
        peak = float(np.max(traces[:, index]))
        thresholds = [max(0.005, peak * fraction) for fraction in (0.10, 0.25, 0.50)]
        measurements = [trace_measurements(traces[:, index], fps, t) for t in thresholds]
        same = all(m["rising_edge_frames"] == measurements[0]["rising_edge_frames"]
                   and m["falling_edge_frames"] == measurements[0]["falling_edge_frames"]
                   for m in measurements)
        regions.append({
            **{k: v for k, v in component.items() if k != "mask"},
            "peak_rgb_luminance": peak,
            "threshold_stable_edges": same,
            "threshold_measurements": measurements,
        })
    active = traces > np.asarray([r["threshold_measurements"][1]["threshold"] for r in regions])
    return {
        "observation_version": "0.1.0", "stream": stream,
        "decoded_frame_count": count, "duration_seconds": count / fps,
        "pts_audit": {
            "frame_count": len(pts), "start_seconds": float(pts[0]),
            "end_frame_start_seconds": float(pts[-1]),
            "max_cadence_error_seconds": float(np.max(np.abs(delta - 1/fps))),
            "non_increasing_timestamp_count": int(np.sum(delta <= 0)),
            "cadence_outlier_count": int(np.sum(np.abs(delta - 1/fps) > 0.000002)),
        },
        "analysis_size": size, "geometry_threshold": geometry_threshold,
        "region_count": len(regions), "regions": regions,
        "all_regions_matched_framewise": bool(np.all(active == active[:, :1])),
        "frames_with_region_disagreement": int(np.sum(np.any(active != active[:, :1], axis=1))),
        "initial_all_black": bool(not active[0].any()),
        "terminal_all_black": bool(not active[-1].any()),
        "ordering_attestation": {"recipe_loaded_during_detection": False,
                                  "targets_loaded_during_detection": False,
                                  "tolerances_loaded_during_detection": False},
        "limitations": [
            "Timing and duty describe decoded frames, not optical device output.",
            "Spatial components use half the observed peak with an absolute 0.02 floor.",
            "Subframe timing, calibrated luminance, and exposure safety are unsupported.",
            "Five-second windows are descriptive and need not align with source segments.",
        ],
    }, traces, pts
