"""Post-observation comparison of vibrant colors, pulse gates, and sweep."""
import argparse
import json
from pathlib import Path

import numpy as np

from analysis.declared_video_schedule import declared_samples
from core.hashing import sha256_file


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('observation',type=Path)
    parser.add_argument('recipe',type=Path)
    parser.add_argument('treatment',type=Path)
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args()
    o=json.loads(args.observation.read_text())
    traces=args.observation.parent/'rgb-traces.npz'
    if sha256_file(traces)!=o['trace_sha256']:
        raise ValueError('saved RGB traces changed')
    if sha256_file(Path(o['artifact']['path']))!=o['artifact']['sha256']:
        raise ValueError('media changed')
    recipe=json.loads(args.recipe.read_text())
    treatment=json.loads(args.treatment.read_text())
    rgb=np.load(traces)['rgb']
    fps=o['stream']['refresh_rate_hz']
    order=treatment['clockwise_order']
    mix=treatment['highlight_white_mix']
    palettes={name:np.array(color,dtype=float) for name,color in zip(order,treatment['palette_rgb'])}
    gates={}
    cycles={}
    gate_results=[]
    expected=np.zeros_like(rgb)
    for j,region in enumerate(o['regions']):
        name=region['region_id']
        r=next(r for r in recipe['regions'] if r['name']==name)
        gate,cycle=declared_samples(r,fps,len(rgb))
        gates[name]=gate
        cycles[name]=cycle
        actual=rgb[:,j].max(axis=1)/255>.02
        gate_results.append({'region_id':name,'frame_mismatch_count':int(np.sum(actual!=gate))})
        expected[gate,j]=palettes[name]*treatment['intensity']
        highlighted=gate & (cycle%4==order.index(name))
        expected[highlighted,j]=np.round((palettes[name]*(1-mix)+255*mix)*treatment['intensity'])
    errors=np.abs(rgb-expected)
    emphasis_results=[]
    for pulse in o['observed_pulse_emphasis']:
        frame=pulse['rising_frame']
        target=order[int(cycles[order[0]][frame])%4]
        emphasis_results.append({'rising_frame':frame,'analytic_cycle_id':int(cycles[order[0]][frame]),
            'expected_region':target,'observed_region':pulse['emphasized_region'],
            'state':'agree' if target==pulse['emphasized_region'] else 'unsupported'
            if pulse['emphasized_region'] is None else 'disagree'})
    observed_ids=[p['analytic_cycle_id'] for p in emphasis_results]
    jumps=np.diff(observed_ids)
    report={'report_version':'0.1.0','report_kind':'post_observation_vibrant_comparison',
        'artifact_sha256':o['artifact']['sha256'],
        'observation_sha256':sha256_file(args.observation),
        'recipe_sha256':sha256_file(args.recipe),
        'treatment_sha256':sha256_file(args.treatment),
        'declaration_loaded_after_observation':True,'gate_results':gate_results,
        'maximum_rgb_code_error':float(errors.max()),
        'mean_rgb_code_error':float(errors.mean()),
        'frames_with_rgb_error_over_3':int(np.sum(np.any(errors>3,axis=(1,2)))),
        'emphasis_results':emphasis_results,
        'emphasis_agree_count':sum(p['state']=='agree' for p in emphasis_results),
        'observed_pulse_count':len(emphasis_results),
        'analytic_cycle_jump_count':int(np.sum(jumps>1)),
        'unseen_cycles_between_visible_pulses':int(np.sum(np.maximum(jumps-1,0))),
        'first_visible_cycle':min(observed_ids),'last_visible_cycle':max(observed_ids),
        'limitations':['RGB code differences reflect lossy video encoding; 3-code threshold is an engineering diagnostic, not an exposure criterion.',
                      'Skipped analytic gates can skip visible highlight quadrants.',
                      'Continuous-waveform and physical Nova replication remain unsupported.']}
    args.output.write_text(json.dumps(report,indent=2)+'\n')
    print('gate mismatches:',sum(r['frame_mismatch_count'] for r in gate_results))
    print('maximum RGB error:',report['maximum_rgb_code_error'])
    print('emphasis agreement:',report['emphasis_agree_count'],'/',report['observed_pulse_count'])
    print('unseen cycles between visible pulses:',report['unseen_cycles_between_visible_pulses'])


if __name__=='__main__':
    main()
