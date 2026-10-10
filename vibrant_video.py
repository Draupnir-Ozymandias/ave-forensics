"""Persist blind RGB observations before validating a vibrant render declaration."""
import argparse
import json
from pathlib import Path

import numpy as np

from analysis.vibrant_video import observe_vibrant
from core.hashing import sha256_file
from provenance.run import build_run_provenance


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('video',type=Path)
    parser.add_argument('--output-dir',required=True,type=Path)
    args=parser.parse_args()
    path=args.video.resolve()
    input_hash=sha256_file(path)
    provenance=build_run_provenance(input_path=path,project_root=Path(__file__).resolve().parent,
        analysis_configuration={'configuration_schema_version':'vibrant-video-0.1.0',
            'analysis_size':128,'geometry_peak_fraction':0.3,'gate_thresholds':[.01,.02,.05],
            'emphasis_method':'RGB_energy_normalized_by_active_25th_percentile',
            'emphasis_separation_ratio':1.05})
    observation,rgb,pts=observe_vibrant(path)
    if sha256_file(path)!=input_hash:
        raise ValueError('artifact changed during analysis')
    args.output_dir.mkdir(parents=True,exist_ok=True)
    traces=args.output_dir/'rgb-traces.npz'
    np.savez_compressed(traces,rgb=rgb,timestamps=pts)
    observation.update(artifact={'path':str(path),'sha256':input_hash},
        run_provenance=provenance,trace_sha256=sha256_file(traces))
    (args.output_dir/'observation.json').write_text(json.dumps(observation,indent=2)+'\n')
    print(f"Persisted {observation['decoded_frame_count']} frames and four RGB traces")


if __name__=='__main__':
    main()
