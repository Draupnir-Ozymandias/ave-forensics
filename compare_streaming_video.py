"""Compare persisted pixel observations with a subsequently loaded recipe."""
import argparse
import json
import math
from fractions import Fraction
from pathlib import Path

import numpy as np

from core.hashing import sha256_file


def endpoints(curve):
    if curve["kind"] == "constant":
        return Fraction(str(curve["value"])), Fraction(str(curve["value"]))
    if curve["kind"] != "linear":
        raise ValueError("unsupported declaration curve")
    return Fraction(str(curve["start"])), Fraction(str(curve["end"]))


def compare(observation_path, recipe_path, output_path):
    root = observation_path.parent
    observation = json.loads(observation_path.read_text())
    if sha256_file(Path(observation["artifact"]["path"])) != observation["artifact"]["sha256"]:
        raise ValueError("video changed since observation")
    trace_path = root / "pixel-traces.npz"
    if sha256_file(trace_path) != observation["trace_sha256"]:
        raise ValueError("persisted traces changed")
    recipe = json.loads(recipe_path.read_text())
    traces = np.load(trace_path)["traces"]
    fps = Fraction(str(observation["stream"]["refresh_rate_hz"]))
    comparisons = []
    for region in recipe["regions"]:
        index = next(i for i, r in enumerate(observation["regions"])
                     if r["region_id"] == region["name"])
        threshold = observation["regions"][index]["threshold_measurements"][1]["threshold"]
        active = traces[:, index] > threshold
        phase_origin = Fraction(0)
        previous_off = True
        for interval in region["intervals"]:
            start = Fraction(interval["start_us"], 1_000_000)
            end = Fraction(interval["end_us"], 1_000_000)
            duration = end-start
            indices = range(math.ceil(start*fps), math.ceil(end*fps))
            if interval["kind"] == "off":
                expected = np.zeros(len(indices), dtype=bool)
                phase_origin = Fraction(0)
                previous_off = True
                expected_duty = 0.0
                cycles = None
            else:
                if previous_off or interval["phase_policy"] == "reset":
                    phase_origin = Fraction(str(interval["phase_origin_cycles"]))
                f0, f1 = endpoints(interval["frequency_hz"])
                d0, d1 = endpoints(interval["duty_cycle"])
                expected_values, phases = [], []
                for frame in indices:
                    t = Fraction(frame, fps) - start
                    phase = phase_origin + f0*t + (f1-f0)*t*t/(2*duration)
                    duty = d0+(d1-d0)*t/duration
                    expected_values.append(phase % 1 < duty)
                    phases.append(math.floor(phase))
                expected = np.asarray(expected_values, dtype=bool)
                represented = set(np.asarray(phases)[expected].tolist())
                end_phase = phase_origin+(f0+f1)*duration/2
                rising_cycles = set(range(math.ceil(phase_origin), math.ceil(end_phase)))
                cycles = {"analytic_cycle_starts_in_interval": len(rising_cycles),
                          "cycle_starts_without_on_frame_in_interval": len(rising_cycles-represented)}
                expected_duty = float((d0+d1)/2)
                phase_origin = end_phase
                previous_off = False
            actual = active[indices.start:indices.stop]
            mismatches = int(np.sum(actual != expected))
            edges = np.flatnonzero(np.diff(active.astype(np.int8), prepend=0)==1)
            edges = edges[(edges >= indices.start) & (edges < indices.stop)]
            rate = float((len(edges)-1)*fps/(edges[-1]-edges[0])) if len(edges)>1 else None
            comparisons.append({
                "region_id": region["name"], "interval_id": interval["interval_id"],
                "start_seconds": float(start), "end_seconds": float(end),
                "kind": interval["kind"], "comparison_state": "agree" if mismatches==0 else "disagree",
                "frame_mismatch_count": mismatches,
                "observed_encoded_duty": float(np.mean(actual)),
                "predicted_encoded_duty": float(np.mean(expected)),
                "declared_mean_continuous_duty": expected_duty,
                "observed_edge_rate_hz": rate,
                "observed_rising_edges": len(edges),
                "quantization": cycles,
            })
    results = {
        "report_version": "0.1.0", "report_kind": "post_observation_pixel_schedule_comparison",
        "observation_sha256": sha256_file(observation_path),
        "recipe_sha256": sha256_file(recipe_path),
        "artifact_sha256": observation["artifact"]["sha256"],
        "recipe_loaded_after_observation_persisted": True,
        "interval_results": comparisons,
        "total_frame_mismatch_count": sum(r["frame_mismatch_count"] for r in comparisons),
        "limitations": [
            "Agreement refers to declared frame-sampled gates; continuous duty and frequency can be undersampled.",
            "Cycle coverage at an interval boundary can exclude a pulse represented in the next interval.",
            "Physical phase, optical intensity/duty, and Nova equivalence remain unsupported.",
        ],
    }
    output_path.write_text(json.dumps(results, indent=2)+"\n")
    print(f"Compared {len(comparisons)} region intervals; "
          f"{results['total_frame_mismatch_count']} frame mismatches")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("observation", type=Path)
    parser.add_argument("recipe", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    compare(args.observation, args.recipe, args.output)


if __name__ == "__main__":
    main()
