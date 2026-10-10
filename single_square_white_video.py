"""Observe a monochrome square, then compare saved samples with a declaration."""
import argparse
import json
import math
from pathlib import Path

import numpy as np

from analysis.declared_video_schedule import declared_samples
from analysis.single_square_video import observe_single_square
from core.hashing import sha256_file
from provenance.run import build_run_provenance


def observe(args):
    path=args.video.resolve()
    identity=sha256_file(path)
    provenance=build_run_provenance(input_path=path,project_root=Path(__file__).resolve().parent,
        analysis_configuration={'configuration_schema_version':'single-square-monochrome-0.1.0',
            'analysis_size':128,'geometry_peak_fraction':.3,'black_rgb_threshold':5,
            'mode':'black_versus_nonblack','color_values_loaded':False})
    o,rgb,state,pts=observe_single_square(path,monochrome=True)
    if sha256_file(path)!=identity:
        raise ValueError('media changed during decoding')
    args.output_dir.mkdir(parents=True,exist_ok=True)
    traces=args.output_dir/'traces.npz'
    np.savez_compressed(traces,rgb=rgb,state=state,timestamps=pts)
    o.update(artifact={'path':str(path),'sha256':identity},run_provenance=provenance,
             trace_sha256=sha256_file(traces))
    (args.output_dir/'observation.json').write_text(json.dumps(o,indent=2)+'\n')
    print('Persisted frames:',o['decoded_frame_count'],'states:',o['color_state_counts'])


def compare(args):
    o=json.loads(args.observation.read_text())
    trace_path=args.observation.parent/'traces.npz'
    if sha256_file(trace_path)!=o['trace_sha256']:
        raise ValueError('saved traces changed')
    if sha256_file(Path(o['artifact']['path']))!=o['artifact']['sha256']:
        raise ValueError('media changed since observation')
    data=np.load(trace_path)
    rgb,state=data['rgb'],data['state']
    recipe=json.loads(args.base_recipe.read_text())
    gate,cycles=declared_samples(recipe['regions'][0],o['stream']['refresh_rate_hz'],len(state))
    active=np.zeros(len(state),dtype=bool)
    fps=o['stream']['refresh_rate_hz']
    for interval in recipe['regions'][0]['intervals']:
        if interval['kind']=='pulse':
            active[math.ceil(interval['start_us']*fps/1e6):math.ceil(interval['end_us']*fps/1e6)]=True
    expected=gate[:,None]*255.0
    error=np.abs(rgb-expected)
    represented=set(cycles[gate].tolist())
    analytic=set(cycles[active].tolist())
    result={'report_version':'0.1.0','report_kind':'post_observation_monochrome_square_comparison',
        'artifact_sha256':o['artifact']['sha256'],'observation_sha256':sha256_file(args.observation),
        'base_recipe_sha256':sha256_file(args.base_recipe),
        'declaration_loaded_after_observation':True,
        'state_mismatch_count':int(np.sum((state==1)!=gate)),
        'maximum_rgb_code_error':float(error.max()),'mean_rgb_code_error':float(error.mean()),
        'frames_with_rgb_error_over_3':int(np.sum(np.any(error>3,axis=1))),
        'represented_nonblack_cycle_count':len(represented),
        'analytic_cycle_ids_in_active_samples':len(analytic),
        'cycle_ids_without_white_sample':sorted(analytic-represented),
        'limitations':['White 255/black 0 are the requested comparison values; pixels remain uncalibrated.',
                       'Agreement concerns sampled gates; narrow analytic pulses may be absent.']}
    args.output.write_text(json.dumps(result,indent=2)+'\n')
    print('Gate mismatches:',result['state_mismatch_count'],'maximum RGB error:',result['maximum_rgb_code_error'])


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    commands=parser.add_subparsers(dest='command',required=True)
    p=commands.add_parser('observe')
    p.add_argument('video',type=Path)
    p.add_argument('--output-dir',type=Path,required=True)
    p.set_defaults(handler=observe)
    p=commands.add_parser('compare')
    p.add_argument('observation',type=Path)
    p.add_argument('base_recipe',type=Path)
    p.add_argument('--output',type=Path,required=True)
    p.set_defaults(handler=compare)
    args=parser.parse_args()
    args.handler(args)


if __name__=='__main__':
    main()
