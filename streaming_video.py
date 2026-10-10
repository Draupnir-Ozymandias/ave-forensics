"""Persist independent long-video observations before schedule comparison."""
import argparse
import json
from pathlib import Path

import numpy as np

from analysis.streaming_video import observe_streaming_video
from core.hashing import sha256_file
from provenance.run import build_run_provenance


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("video")
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    path = Path(args.video).resolve()
    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    input_hash = sha256_file(path)
    provenance = build_run_provenance(
        input_path=path, project_root=Path(__file__).resolve().parent,
        analysis_configuration={"configuration_schema_version": "streaming-video-0.1.0",
                                "analysis_size": 128, "geometry_threshold_peak_fraction": 0.5,
                                "geometry_threshold_floor": 0.02,
                                "trace_threshold_peak_fractions": [0.1, 0.25, 0.5]},
    )
    observation, traces, pts = observe_streaming_video(path)
    if sha256_file(path) != input_hash:
        raise ValueError("input changed during analysis")
    np.savez_compressed(output / "pixel-traces.npz", traces=traces, timestamps=pts)
    observation.update(artifact={"path": str(path), "sha256": input_hash},
                       run_provenance=provenance,
                       trace_sha256=sha256_file(output / "pixel-traces.npz"))
    (output / "observation.json").write_text(json.dumps(observation, indent=2) + "\n")
    print(f"Persisted {observation['decoded_frame_count']} frames, "
          f"{observation['region_count']} regions; matched="
          f"{observation['all_regions_matched_framewise']}")


if __name__ == "__main__":
    main()
