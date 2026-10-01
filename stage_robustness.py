"""Analyze stage-classification robustness, then compare a threshold separately."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from analysis.stage_robustness import (
    analyze_stage_robustness,
    compare_confidence_threshold,
)
from core.audio_loader import load_audio
from core.hashing import sha256_file
from provenance.run import build_run_provenance


def analyze(arguments: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    project_root = Path(__file__).resolve().parent
    input_path = Path(arguments.audio_path).resolve()
    audio, sample_rate = load_audio(str(input_path))
    array = np.asarray(audio, dtype=float)
    start = int(round(arguments.start_seconds * sample_rate))
    end_seconds = (
        arguments.end_seconds
        if arguments.end_seconds is not None
        else array.shape[-1] / sample_rate
    )
    end = int(round(end_seconds * sample_rate))
    if arguments.start_seconds < 0 or end_seconds <= arguments.start_seconds:
        parser.error("analysis time range must be positive and ordered")
    if start >= array.shape[-1] or end > array.shape[-1]:
        parser.error("analysis time range falls outside the input")
    segment = array[..., start:end]
    configuration = {
        "configuration_schema_version": "stage-robustness-cli-0.1.0",
        "source_time_range_seconds": {
            "start": arguments.start_seconds,
            "end": end_seconds,
        },
        "threshold_loaded_during_analysis": False,
        "method": "fixed_label_preserving_perturbation_suite",
    }
    provenance = build_run_provenance(
        input_path=input_path,
        project_root=project_root,
        analysis_configuration=configuration,
    )
    result = analyze_stage_robustness(segment, sample_rate)
    payload = {
        "input_sha256": provenance["input"]["sha256"],
        "source_time_range_seconds": configuration["source_time_range_seconds"],
        "run_provenance": provenance,
        "analysis": result,
    }
    output = Path(arguments.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    confidence = result["summary"]["confidence"]
    print(
        f"{result['baseline']['construction_class']}: "
        f"baseline={result['baseline']['confidence']:.6f}, "
        f"range={confidence['minimum']:.6f}..{confidence['maximum']:.6f}, "
        f"span={confidence['span']:.6f}"
    )


def compare(arguments: argparse.Namespace) -> None:
    analysis_path = Path(arguments.analysis).resolve()
    payload = json.loads(analysis_path.read_text())
    comparison = compare_confidence_threshold(payload["analysis"], arguments.threshold)
    output = Path(arguments.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(
            {
                "analysis_path": str(analysis_path),
                "analysis_sha256": sha256_file(analysis_path),
                "threshold_source": arguments.threshold_source,
                "comparison": comparison,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )
    print(
        f"{comparison['interpretation']}: "
        f"distance={comparison['baseline_distance_from_threshold']:.6f}, "
        f"radius={comparison['observed_robustness_radius']:.6f}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    analyze_parser = subparsers.add_parser("analyze")
    analyze_parser.add_argument("audio_path")
    analyze_parser.add_argument("--start-seconds", type=float, default=0.0)
    analyze_parser.add_argument("--end-seconds", type=float)
    analyze_parser.add_argument("--output", required=True)
    analyze_parser.set_defaults(handler=lambda args: analyze(args, parser))
    compare_parser = subparsers.add_parser("compare")
    compare_parser.add_argument("analysis")
    compare_parser.add_argument("--threshold", type=float, required=True)
    compare_parser.add_argument(
        "--threshold-source", default="external_post_observation_threshold"
    )
    compare_parser.add_argument("--output", required=True)
    compare_parser.set_defaults(handler=compare)
    arguments = parser.parse_args()
    arguments.handler(arguments)


if __name__ == "__main__":
    main()
