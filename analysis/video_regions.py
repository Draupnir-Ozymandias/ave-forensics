"""Blind spatial-region and on/off schedule analysis for rendered video.

The detector consumes decoded pixels and stream metadata only. It does not read
Generator recipes, resolved schedules, declaration targets, or tolerances.
"""

from __future__ import annotations

import json
import subprocess
from fractions import Fraction
from pathlib import Path
from typing import Any

import numpy as np
from scipy import ndimage


class VideoRegionAnalysisError(ValueError):
    """Raised when a video cannot be decoded into a supported observation."""


def _run(command: list[str]) -> bytes:
    try:
        completed = subprocess.run(command, capture_output=True, check=False)
    except OSError as error:
        raise VideoRegionAnalysisError(f"video tool unavailable: {command[0]}") from error
    if completed.returncode != 0:
        detail = completed.stderr.decode("utf-8", errors="replace").strip()
        raise VideoRegionAnalysisError(detail or f"{command[0]} failed")
    return completed.stdout


def _frame_rate(value: str) -> float:
    try:
        rate = float(Fraction(value))
    except (ValueError, ZeroDivisionError) as error:
        raise VideoRegionAnalysisError(f"invalid video frame rate: {value}") from error
    if rate <= 0:
        raise VideoRegionAnalysisError("video frame rate must be positive")
    return rate


def probe_video(path: Path) -> dict[str, Any]:
    payload = json.loads(
        _run(
            [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=codec_name,width,height,pix_fmt,r_frame_rate,avg_frame_rate,nb_frames,duration",
                "-show_entries",
                "format=duration,size",
                "-of",
                "json",
                str(path),
            ]
        ).decode("utf-8")
    )
    streams = payload.get("streams", [])
    if len(streams) != 1:
        raise VideoRegionAnalysisError("exactly one primary video stream is required")
    stream = streams[0]
    width, height = int(stream["width"]), int(stream["height"])
    if width <= 0 or height <= 0:
        raise VideoRegionAnalysisError("video dimensions must be positive")
    fps = _frame_rate(stream.get("avg_frame_rate") or stream["r_frame_rate"])
    duration = float(stream.get("duration") or payload["format"]["duration"])
    reported_frames = stream.get("nb_frames")
    return {
        "codec": stream.get("codec_name"),
        "pixel_format": stream.get("pix_fmt"),
        "width": width,
        "height": height,
        "refresh_rate_hz": fps,
        "duration_seconds": duration,
        "reported_frame_count": int(reported_frames) if reported_frames else None,
        "size_bytes": int(payload["format"]["size"]),
    }


def decode_video_rgb(path: Path, *, analysis_size: int = 64) -> tuple[np.ndarray, dict[str, Any]]:
    if analysis_size < 16:
        raise VideoRegionAnalysisError("analysis_size must be at least 16 pixels")
    metadata = probe_video(path)
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
            f"scale={analysis_size}:{analysis_size}:flags=area",
            "-fps_mode",
            "passthrough",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "rgb24",
            "-",
        ]
    )
    bytes_per_frame = analysis_size * analysis_size * 3
    if not raw or len(raw) % bytes_per_frame:
        raise VideoRegionAnalysisError("decoded video byte count is not frame-aligned")
    frames = np.frombuffer(raw, dtype=np.uint8).reshape(
        -1, analysis_size, analysis_size, 3
    )
    return frames, metadata


def _position_name(centroid_x: float, centroid_y: float, width: int, height: int) -> str:
    horizontal = "left" if centroid_x < width / 2 else "right"
    vertical = "top" if centroid_y < height / 2 else "bottom"
    return f"{vertical}_{horizontal}"


def _off_intervals(active: np.ndarray, fps: float) -> list[dict[str, float]]:
    padded = np.pad((~active).astype(np.int8), (1, 1))
    changes = np.flatnonzero(np.diff(padded))
    return [
        {
            "start": round(float(start / fps), 9),
            "end": round(float(min(end, active.size) / fps), 9),
        }
        for start, end in changes.reshape(-1, 2)
        if end > start
    ]


def analyze_region_frames(
    frames: np.ndarray,
    *,
    refresh_rate_hz: float,
    absolute_on_threshold: float = 0.02,
    relative_on_threshold: float = 0.05,
    minimum_region_fraction: float = 0.02,
) -> dict[str, Any]:
    array = np.asarray(frames)
    if array.ndim != 4 or array.shape[-1] != 3 or array.shape[0] < 2:
        raise VideoRegionAnalysisError("RGB video frames must have shape (time, height, width, 3)")
    if refresh_rate_hz <= 0:
        raise VideoRegionAnalysisError("refresh_rate_hz must be positive")
    rgb = array.astype(np.float64) / 255.0
    luminance = (
        0.2126 * rgb[..., 0] + 0.7152 * rgb[..., 1] + 0.0722 * rgb[..., 2]
    )
    threshold = max(
        float(absolute_on_threshold),
        float(np.max(luminance)) * float(relative_on_threshold),
    )
    active_pixels = luminance > threshold
    height, width = array.shape[1:3]
    minimum_pixels = max(1, int(round(height * width * minimum_region_fraction)))

    signature_masks: dict[bytes, np.ndarray] = {}
    for y in range(height):
        for x in range(width):
            signature = active_pixels[:, y, x]
            if not np.any(signature):
                continue
            key = np.packbits(signature).tobytes()
            if key not in signature_masks:
                signature_masks[key] = np.zeros((height, width), dtype=bool)
            signature_masks[key][y, x] = True

    detected = []
    for signature_key, mask in signature_masks.items():
        labels, component_count = ndimage.label(mask)
        signature = np.unpackbits(
            np.frombuffer(signature_key, dtype=np.uint8)
        )[: array.shape[0]].astype(bool)
        for component_id in range(1, component_count + 1):
            component = labels == component_id
            pixel_count = int(np.sum(component))
            if pixel_count < minimum_pixels:
                continue
            y_values, x_values = np.nonzero(component)
            region_luminance = np.median(luminance[:, component], axis=1)
            active = region_luminance > threshold
            transitions = np.flatnonzero(active[1:] != active[:-1]) + 1
            detected.append(
                {
                    "pixel_count": pixel_count,
                    "coverage_fraction": round(pixel_count / (height * width), 6),
                    "centroid_x_fraction": round(float(np.mean(x_values) / width), 6),
                    "centroid_y_fraction": round(float(np.mean(y_values) / height), 6),
                    "bounding_box": {
                        "x_min": int(np.min(x_values)),
                        "y_min": int(np.min(y_values)),
                        "x_max_exclusive": int(np.max(x_values) + 1),
                        "y_max_exclusive": int(np.max(y_values) + 1),
                    },
                    "active_fraction": round(float(np.mean(active)), 6),
                    "initially_active": bool(active[0]),
                    "transition_frames": [int(item) for item in transitions],
                    "transition_times_seconds": [
                        round(float(item / refresh_rate_hz), 9) for item in transitions
                    ],
                    "explicit_off_intervals": _off_intervals(active, refresh_rate_hz),
                    "signature": signature,
                }
            )

    detected.sort(key=lambda item: (item["centroid_y_fraction"], item["centroid_x_fraction"]))
    position_names = [
        _position_name(
            item["centroid_x_fraction"] * width,
            item["centroid_y_fraction"] * height,
            width,
            height,
        )
        for item in detected
    ]
    unique_positions = len(position_names) == len(set(position_names))
    for index, item in enumerate(detected, start=1):
        item["region_id"] = position_names[index - 1] if unique_positions else f"region_{index}"
        item.pop("signature")

    schedules = [
        (item["initially_active"], *item["transition_frames"]) for item in detected
    ]
    independent = len(detected) > 1 and len(set(schedules)) == len(schedules)
    covered_fraction = sum(item["coverage_fraction"] for item in detected)
    confidence = min(1.0, covered_fraction) if detected else 0.0
    return {
        "classification": "independent_region_schedules" if independent else "shared_or_unresolved_region_schedule",
        "region_count": len(detected),
        "independent_region_schedules": independent,
        "regions": detected,
        "frame_count": int(array.shape[0]),
        "refresh_rate_hz": float(refresh_rate_hz),
        "duration_seconds": float(array.shape[0] / refresh_rate_hz),
        "analysis_resolution": {"width": width, "height": height},
        "on_threshold": round(threshold, 9),
        "minimum_region_pixels": minimum_pixels,
        "spatial_coverage_fraction": round(covered_fraction, 6),
        "confidence": round(confidence, 6),
        "limitations": [
            "Region boundaries are reconstructed from thresholded pixel timing signatures.",
            "Decoded frame timing describes the rendered file, not physical display refresh or optical output.",
            "Video pixels do not establish calibrated luminance, exposure safety, efficacy, or neurological response.",
        ],
    }


def analyze_video_regions(path: Path, *, analysis_size: int = 64) -> dict[str, Any]:
    frames, metadata = decode_video_rgb(path, analysis_size=analysis_size)
    result = analyze_region_frames(
        frames,
        refresh_rate_hz=metadata["refresh_rate_hz"],
    )
    result["stream"] = metadata
    if metadata["reported_frame_count"] not in (None, result["frame_count"]):
        result["limitations"].append(
            "Container-reported and independently decoded frame counts differ."
        )
    return result
