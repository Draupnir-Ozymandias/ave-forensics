"""Persist independent single-square color observations before comparison."""
import argparse
import json
from pathlib import Path

import numpy as np

from analysis.single_square_video import observe_single_square
from core.hashing import sha256_file
from provenance.run import build_run_provenance


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('video',type=Path)
    parser.add_argument('--output-dir',type=Path,required=True)
    args=parser.parse_args()
    path=args.video.resolve()
    input_hash=sha256_file(path)
    provenance=build_run_provenance(input_path=path,project_root=Path(__file__).resolve().parent,
        analysis_configuration={'configuration_schema_version':'single-square-video-0.1.0',
            'analysis_size':128,'geometry_peak_fraction':.3,'black_rgb_threshold':5,
            'color_method':'two_observed_RGB_median_clusters','quadrant_rgb_error_diagnostic':3})
    o,rgb,state,pts=observe_single_square(path)
    if sha256_file(path)!=input_hash:
        raise ValueError('media changed during decoding')
    args.output_dir.mkdir(parents=True,exist_ok=True)
    trace=args.output_dir/'color-traces.npz'
    np.savez_compressed(trace,rgb=rgb,state=state,timestamps=pts)
    o.update(artifact={'path':str(path),'sha256':input_hash},run_provenance=provenance,
             trace_sha256=sha256_file(trace))
    (args.output_dir/'observation.json').write_text(json.dumps(o,indent=2)+'\n')
    print('Persisted frames:',o['decoded_frame_count'],'colors:',o['color_state_counts'])


if __name__=='__main__':
    main()
