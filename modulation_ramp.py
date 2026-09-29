"""Command-line entry point for blind carrier-band modulation-ramp analysis."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from analysis.modulation_ramp import analyze_modulation_ramp
from analysis.config import ANALYSIS_CONFIGURATION
from core.audio_loader import load_audio
from evidence.adapters import modulation_ramp_to_evidence
from provenance.run import build_run_provenance
from reports.evidence_export import export_evidence_json


def _select_channel(audio: np.ndarray, channel: str) -> np.ndarray:
    array = np.asarray(audio)
    if array.ndim == 1:
        if channel not in {"mono", "mean"}:
            raise ValueError("left/right channel requested for mono input")
        return array
    if array.ndim != 2 or array.shape[0] < 2:
        raise ValueError("expected mono audio or channels-first stereo audio")
    if channel == "left":
        return array[0]
    if channel == "right":
        return array[1]
    if channel in {"mono", "mean"}:
        return np.mean(array[:2], axis=0)
    raise ValueError(f"unsupported channel: {channel}")


def main() -> None:
    defaults = ANALYSIS_CONFIGURATION["modulation_ramp"]
    parser = argparse.ArgumentParser(
        description="Observe a continuous modulation ridge without expected-value hints."
    )
    parser.add_argument("audio_path")
    parser.add_argument("--carrier-hz", type=float, required=True)
    parser.add_argument("--carrier-bandwidth-hz", type=float, required=True)
    parser.add_argument(
        "--channel", choices=("left", "right", "mean", "mono"), default="mean"
    )
    parser.add_argument(
        "--envelope-sample-rate", type=int, default=defaults["envelope_sample_rate"]
    )
    parser.add_argument("--min-rate-hz", type=float, default=defaults["min_rate_hz"])
    parser.add_argument("--max-rate-hz", type=float, default=defaults["max_rate_hz"])
    parser.add_argument(
        "--window-seconds", type=float, default=defaults["window_seconds"]
    )
    parser.add_argument("--hop-seconds", type=float, default=defaults["hop_seconds"])
    parser.add_argument(
        "--minimum-spectral-snr-db",
        type=float,
        default=defaults["minimum_spectral_snr_db"],
    )
    parser.add_argument(
        "--minimum-peak-concentration",
        type=float,
        default=defaults["minimum_peak_concentration"],
    )
    parser.add_argument(
        "--minimum-relative-variation",
        type=float,
        default=defaults["minimum_relative_variation"],
    )
    parser.add_argument(
        "--minimum-coverage", type=float, default=defaults["minimum_coverage"]
    )
    parser.add_argument(
        "--minimum-contiguous-coverage",
        type=float,
        default=defaults["minimum_contiguous_coverage"],
    )
    parser.add_argument(
        "--minimum-fit-r-squared",
        type=float,
        default=defaults["minimum_fit_r_squared"],
    )
    parser.add_argument(
        "--minimum-ramp-slope-hz-per-second",
        type=float,
        default=defaults["minimum_ramp_slope_hz_per_second"],
    )
    parser.add_argument("--start-seconds", type=float, default=0.0)
    parser.add_argument("--end-seconds", type=float)
    parser.add_argument("--output-dir", default=".")
    arguments = parser.parse_args()

    project_root = Path(__file__).resolve().parent
    input_path = Path(arguments.audio_path).resolve()
    output_dir = Path(arguments.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    audio, sample_rate = load_audio(str(input_path))
    selected = _select_channel(audio, arguments.channel)
    if arguments.start_seconds < 0:
        parser.error("--start-seconds must be non-negative")
    if arguments.end_seconds is not None and arguments.end_seconds <= arguments.start_seconds:
        parser.error("--end-seconds must be greater than --start-seconds")
    start_sample = int(round(arguments.start_seconds * sample_rate))
    end_sample = (
        int(round(arguments.end_seconds * sample_rate))
        if arguments.end_seconds is not None
        else selected.size
    )
    if start_sample >= selected.size or end_sample > selected.size:
        parser.error("requested time range falls outside the audio input")
    selected = selected[start_sample:end_sample]
    configuration = {
        "configuration_schema_version": "modulation-ramp-cli-1.0.0",
        "modulation_ramp": {
            "carrier_center_hz": arguments.carrier_hz,
            "carrier_bandwidth_hz": arguments.carrier_bandwidth_hz,
            "channel": arguments.channel,
            "envelope_sample_rate": arguments.envelope_sample_rate,
            "min_rate_hz": arguments.min_rate_hz,
            "max_rate_hz": arguments.max_rate_hz,
            "window_seconds": arguments.window_seconds,
            "hop_seconds": arguments.hop_seconds,
            "minimum_spectral_snr_db": arguments.minimum_spectral_snr_db,
            "minimum_peak_concentration": arguments.minimum_peak_concentration,
            "minimum_relative_variation": arguments.minimum_relative_variation,
            "minimum_coverage": arguments.minimum_coverage,
            "minimum_contiguous_coverage": arguments.minimum_contiguous_coverage,
            "minimum_fit_r_squared": arguments.minimum_fit_r_squared,
            "minimum_ramp_slope_hz_per_second": (
                arguments.minimum_ramp_slope_hz_per_second
            ),
            "source_time_range_seconds": {
                "start": arguments.start_seconds,
                "end": arguments.end_seconds,
            },
        },
    }
    provenance = build_run_provenance(
        input_path=input_path,
        project_root=project_root,
        analysis_configuration=configuration,
    )
    result = analyze_modulation_ramp(
        selected,
        sample_rate,
        carrier_center_hz=arguments.carrier_hz,
        carrier_bandwidth_hz=arguments.carrier_bandwidth_hz,
        envelope_sample_rate=arguments.envelope_sample_rate,
        min_rate_hz=arguments.min_rate_hz,
        max_rate_hz=arguments.max_rate_hz,
        window_seconds=arguments.window_seconds,
        hop_seconds=arguments.hop_seconds,
        minimum_spectral_snr_db=arguments.minimum_spectral_snr_db,
        minimum_peak_concentration=arguments.minimum_peak_concentration,
        minimum_relative_variation=arguments.minimum_relative_variation,
        minimum_coverage=arguments.minimum_coverage,
        minimum_contiguous_coverage=arguments.minimum_contiguous_coverage,
        minimum_fit_r_squared=arguments.minimum_fit_r_squared,
        minimum_ramp_slope_hz_per_second=(
            arguments.minimum_ramp_slope_hz_per_second
        ),
        time_offset_seconds=arguments.start_seconds,
    )
    result["channel"] = arguments.channel
    result_path = output_dir / "ave_modulation_ramp.json"
    result_path.write_text(
        json.dumps({"run_provenance": provenance, "analysis": result}, indent=2, sort_keys=True)
        + "\n"
    )

    evidence_provenance = {
        "run_id": provenance["run_id"],
        "input_sha256": provenance["input"]["sha256"],
        "recording_id": (
            provenance["recording_manifest"]["recording_id"]
            if provenance["recording_manifest"]
            else None
        ),
        "analysis_configuration_version": configuration[
            "configuration_schema_version"
        ],
    }
    evidence = modulation_ramp_to_evidence(
        result, evidence_provenance, channel=arguments.channel
    )
    export_evidence_json(
        [evidence],
        str(output_dir / "ave_modulation_ramp_evidence.json"),
        run_metadata={
            "input_path": provenance["input"]["relative_path"],
            "sample_rate": sample_rate,
            "duration_seconds": result["duration_seconds"],
            "source_time_range_seconds": result["source_time_range_seconds"],
        },
        run_provenance=provenance,
    )
    print(
        f"{result['classification']}: coverage={result['coverage']:.3f}, "
        f"confidence={result['confidence']:.3f}"
    )
    if result["fit"]:
        fit = result["fit"]
        print(
            f"{fit['fitted_start_rate_hz']:.3f} -> {fit['fitted_end_rate_hz']:.3f} Hz, "
            f"slope={fit['slope_hz_per_second']:.6f} Hz/s, "
            f"RMSE={fit['residual_rmse_hz']:.3f} Hz"
        )
    print(f"Detailed analysis written to {result_path}")


if __name__ == "__main__":
    main()
