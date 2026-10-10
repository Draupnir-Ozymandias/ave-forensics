"""Compare persisted color states with independently integrated timing curves."""
import argparse
import json
import math
from pathlib import Path

import numpy as np

from analysis.declared_video_schedule import declared_samples
from core.hashing import sha256_file


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('observation',type=Path)
    parser.add_argument('base_recipe',type=Path)
    parser.add_argument('treatment',type=Path)
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args()
    o=json.loads(args.observation.read_text())
    trace_path=args.observation.parent/'color-traces.npz'
    if sha256_file(trace_path)!=o['trace_sha256']:
        raise ValueError('color traces changed')
    if sha256_file(Path(o['artifact']['path']))!=o['artifact']['sha256']:
        raise ValueError('video changed')
    data=np.load(trace_path)
    rgb,state=data['rgb'],data['state']
    recipe=json.loads(args.base_recipe.read_text())
    treatment=json.loads(args.treatment.read_text())
    count=len(state)
    fps=o['stream']['refresh_rate_hz']
    region=recipe['regions'][0]
    gate,cycles=declared_samples(region,fps,count)
    active=np.zeros(count,dtype=bool)
    for interval in region['intervals']:
        if interval['kind']=='pulse':
            start=math.ceil(interval['start_us']*fps/1e6)
            end=math.ceil(interval['end_us']*fps/1e6)
            active[start:end]=True
    expected_state=np.where(active,np.where(gate,1,2),0)
    expected_rgb=np.asarray([treatment['source_off_rgb'],treatment['on_rgb'],treatment['off_rgb']])[expected_state]
    error=np.abs(rgb-expected_rgb)
    represented=set(cycles[gate].tolist())
    analytic=set(cycles[active].tolist())
    report={
        'report_version':'0.1.0','report_kind':'post_observation_single_square_comparison',
        'observation_sha256':sha256_file(args.observation),'artifact_sha256':o['artifact']['sha256'],
        'base_recipe_sha256':sha256_file(args.base_recipe),'treatment_sha256':sha256_file(args.treatment),
        'declaration_loaded_after_observation':True,
        'state_mismatch_count':int(np.sum(state!=expected_state)),
        'black_frames_inside_active_interval':int(np.sum((state==0)&active)),
        'expected_counts':{name:int(np.sum(expected_state==n)) for n,name in enumerate(['black','green','magenta'])},
        'maximum_rgb_code_error':float(error.max()),'mean_rgb_code_error':float(error.mean()),
        'frames_with_rgb_error_over_3':int(np.sum(np.any(error>3,axis=1))),
        'analytic_cycle_ids_in_active_sample_times':len(analytic),
        'represented_green_cycle_count':len(represented),
        'cycle_ids_without_green_sample':sorted(analytic-represented),
        'limitations':['Duty measures green color occupancy, not an optical blackout interval.',
                       'Narrow source gate windows can have no green frame at 120 fps.',
                       'Color and spatial medians are reduced-resolution encoded-pixel measurements.']}
    args.output.write_text(json.dumps(report,indent=2)+'\n')
    print('state mismatches:',report['state_mismatch_count'])
    print('black frames during active:',report['black_frames_inside_active_interval'])
    print('max RGB error:',report['maximum_rgb_code_error'])
    print('cycles without green sample:',len(report['cycle_ids_without_green_sample']))


if __name__=='__main__':
    main()
