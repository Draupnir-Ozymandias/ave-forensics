"""Blind encoded audio/video clock comparison for analysis artifacts."""

from __future__ import annotations

import json
import subprocess
from fractions import Fraction
from pathlib import Path
from typing import Any

import numpy as np
from scipy import ndimage


class MultimodalClockError(ValueError):
    """Raised when an encoded AV artifact cannot support clock comparison."""


def _run(command: list[str]) -> bytes:
    try:
        completed = subprocess.run(command, capture_output=True, check=False)
    except OSError as error:
        raise MultimodalClockError(f"media tool unavailable: {command[0]}") from error
    if completed.returncode != 0:
        detail = completed.stderr.decode("utf-8", errors="replace").strip()
        raise MultimodalClockError(detail or f"{command[0]} failed")
    return completed.stdout


def _rate(value: str) -> float:
    try:
        result = float(Fraction(value))
    except (ValueError, ZeroDivisionError) as error:
        raise MultimodalClockError(f"invalid media rate: {value}") from error
    if result <= 0:
        raise MultimodalClockError("media rate must be positive")
    return result


def probe_multimodal(path: Path) -> dict[str, Any]:
    payload = json.loads(
        _run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "stream=index,codec_type,codec_name,width,height,avg_frame_rate,sample_rate,channels,start_time,duration,nb_frames",
                "-show_entries",
                "format=start_time,duration,size",
                "-of",
                "json",
                str(path),
            ]
        ).decode("utf-8")
    )
    video = next((item for item in payload["streams"] if item["codec_type"] == "video"), None)
    audio = next((item for item in payload["streams"] if item["codec_type"] == "audio"), None)
    if video is None or audio is None:
        raise MultimodalClockError("one video and one audio stream are required")
    return {
        "video": {
            "codec": video.get("codec_name"),
            "width": int(video["width"]),
            "height": int(video["height"]),
            "frame_rate_hz": _rate(video["avg_frame_rate"]),
            "start_seconds": float(video.get("start_time", 0.0)),
            "duration_seconds": float(video["duration"]),
            "frame_count": int(video["nb_frames"]) if video.get("nb_frames") else None,
        },
        "audio": {
            "codec": audio.get("codec_name"),
            "sample_rate_hz": int(audio["sample_rate"]),
            "channels": int(audio["channels"]),
            "start_seconds": float(audio.get("start_time", 0.0)),
            "duration_seconds": float(audio["duration"]),
        },
        "container": {
            "start_seconds": float(payload["format"].get("start_time", 0.0)),
            "duration_seconds": float(payload["format"]["duration"]),
            "size_bytes": int(payload["format"]["size"]),
        },
    }


def _decode_video_activity(path: Path, *, width: int, height: int) -> np.ndarray:
    raw = _run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-i",
            str(path),
            "-map",
            "0:v:0",
            "-vf",
            f"scale={width}:{height}:flags=area",
            "-fps_mode",
            "passthrough",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "rgb24",
            "-",
        ]
    )
    bytes_per_frame = width * height * 3
    if not raw or len(raw) % bytes_per_frame:
        raise MultimodalClockError("decoded video is not frame-aligned")
    frames = np.frombuffer(raw, dtype=np.uint8).reshape(-1, height, width, 3)
    rgb = frames.astype(np.float64) / 255.0
    saturated = (np.max(rgb, axis=3) - np.min(rgb, axis=3) > 0.2) & (
        np.max(rgb, axis=3) > 0.2
    )
    union = np.any(saturated, axis=0)
    labels, component_count = ndimage.label(union)
    minimum_pixels = max(16, int(round(width * height * 0.005)))
    activity = []
    for component_id in range(1, component_count + 1):
        component = labels == component_id
        pixel_count = int(np.sum(component))
        if pixel_count < minimum_pixels:
            continue
        activity.append(np.sum(saturated[:, component], axis=1) / pixel_count)
    if not activity:
        raise MultimodalClockError("no sustained video activity components were found")
    return np.asarray(activity, dtype=float)


def _decode_audio_rms(
    path: Path,
    *,
    sample_rate: int,
    channels: int,
    frame_rate_hz: float,
    frame_count: int,
) -> np.ndarray:
    raw = _run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-i",
            str(path),
            "-map",
            "0:a:0",
            "-f",
            "f32le",
            "-acodec",
            "pcm_f32le",
            "-ac",
            str(channels),
            "-ar",
            str(sample_rate),
            "-",
        ]
    )
    audio = np.frombuffer(raw, dtype=np.float32)
    if audio.size % channels:
        raise MultimodalClockError("decoded audio is not sample-aligned")
    audio = audio.reshape(-1, channels)
    rms = np.empty((frame_count, channels), dtype=float)
    for frame in range(frame_count):
        start = int(round(frame * sample_rate / frame_rate_hz))
        end = int(round((frame + 1) * sample_rate / frame_rate_hz))
        if start >= audio.shape[0]:
            raise MultimodalClockError("audio ends before the video analysis timeline")
        window = audio[start : min(end, audio.shape[0])]
        rms[frame] = np.sqrt(np.mean(np.square(window, dtype=np.float64), axis=0))
    return rms


def _lagged_correlation(first: np.ndarray, second: np.ndarray, lag: int) -> float:
    if lag < 0:
        left, right = first[-lag:], second[:lag]
    elif lag > 0:
        left, right = first[:-lag], second[lag:]
    else:
        left, right = first, second
    if left.size < 4 or np.std(left) <= 1e-12 or np.std(right) <= 1e-12:
        return 0.0
    return float(np.corrcoef(left, right)[0, 1])


def compare_clock_series(
    video_activity: np.ndarray,
    audio_rms: np.ndarray,
    *,
    frame_rate_hz: float,
    max_lag_frames: int = 30,
    minimum_correlation: float = 0.95,
    maximum_aligned_lag_frames: int = 1,
) -> dict[str, Any]:
    video = np.asarray(video_activity, dtype=float)
    audio = np.asarray(audio_rms, dtype=float)
    if video.ndim != 2 or audio.ndim != 2 or video.shape[1] != audio.shape[0]:
        raise MultimodalClockError("clock series must share one frame timeline")
    correlations = []
    for component in video:
        best = None
        for channel in range(audio.shape[1]):
            for lag in range(-max_lag_frames, max_lag_frames + 1):
                correlation = _lagged_correlation(component, audio[:, channel], lag)
                candidate = (correlation, -abs(lag), -channel, lag, channel)
                if best is None or candidate > best:
                    best = candidate
        assert best is not None
        correlations.append(
            {
                "video_component": len(correlations) + 1,
                "audio_channel_index": int(best[4]),
                "lag_frames": int(best[3]),
                "lag_seconds": round(float(best[3] / frame_rate_hz), 9),
                "correlation": round(float(best[0]), 9),
            }
        )
    aligned = all(
        abs(item["lag_frames"]) <= maximum_aligned_lag_frames
        and item["correlation"] >= minimum_correlation
        for item in correlations
    )
    return {
        "clock_alignment": aligned,
        "component_correlations": correlations,
        "minimum_component_correlation": round(
            min(item["correlation"] for item in correlations), 9
        ),
        "maximum_absolute_lag_frames": max(
            abs(item["lag_frames"]) for item in correlations
        ),
        "maximum_absolute_lag_seconds": round(
            max(abs(item["lag_seconds"]) for item in correlations), 9
        ),
    }


def analyze_multimodal_clock(
    path: Path,
    *,
    analysis_width: int = 160,
    analysis_height: int = 90,
    max_lag_frames: int = 30,
    minimum_correlation: float = 0.95,
    maximum_aligned_lag_frames: int = 1,
) -> dict[str, Any]:
    streams = probe_multimodal(path)
    video_activity = _decode_video_activity(
        path, width=analysis_width, height=analysis_height
    )
    audio_rms = _decode_audio_rms(
        path,
        sample_rate=streams["audio"]["sample_rate_hz"],
        channels=streams["audio"]["channels"],
        frame_rate_hz=streams["video"]["frame_rate_hz"],
        frame_count=video_activity.shape[1],
    )
    comparison = compare_clock_series(
        video_activity,
        audio_rms,
        frame_rate_hz=streams["video"]["frame_rate_hz"],
        max_lag_frames=max_lag_frames,
        minimum_correlation=minimum_correlation,
        maximum_aligned_lag_frames=maximum_aligned_lag_frames,
    )
    frame_seconds = 1.0 / streams["video"]["frame_rate_hz"]
    start_difference = abs(
        streams["video"]["start_seconds"] - streams["audio"]["start_seconds"]
    )
    duration_difference = abs(
        streams["video"]["duration_seconds"]
        - streams["audio"]["duration_seconds"]
    )
    comparison["clock_alignment"] = bool(
        comparison["clock_alignment"]
        and start_difference <= frame_seconds
        and duration_difference <= frame_seconds
    )
    return {
        **comparison,
        "streams": streams,
        "video_component_count": int(video_activity.shape[0]),
        "analyzed_frame_count": int(video_activity.shape[1]),
        "stream_start_difference_seconds": round(start_difference, 9),
        "stream_duration_difference_seconds": round(duration_difference, 9),
        "configuration": {
            "analysis_width": analysis_width,
            "analysis_height": analysis_height,
            "max_lag_frames": max_lag_frames,
            "minimum_correlation": minimum_correlation,
            "maximum_aligned_lag_frames": maximum_aligned_lag_frames,
        },
        "limitations": [
            "Alignment describes encoded audio and video streams, not physical display or acoustic latency.",
            "Video activity components are inferred from saturated-pixel occupancy without construction labels.",
            "AAC decoding and video frame quantization bound temporal precision to the encoded artifact.",
            "Clock agreement does not establish neurological entrainment, efficacy, or exposure safety.",
        ],
    }
