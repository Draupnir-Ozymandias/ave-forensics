import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from analysis.single_square_video import observe_single_square


def test_single_square_color_states_recover_gate_without_black_off_frames(monkeypatch):
    sequence=[]
    for i in range(24):
        frame=np.zeros((32,32,3),dtype=np.uint8)
        if 2<=i<22:
            frame[1:31,1:31]=[0,255,0] if i%4==2 else [255,0,255]
        sequence.append(frame)
    monkeypatch.setattr('analysis.single_square_video.frames',lambda path,size:iter(sequence))
    monkeypatch.setattr('analysis.single_square_video.probe_video',lambda path:{'refresh_rate_hz':120.0})
    monkeypatch.setattr('analysis.single_square_video.subprocess.run',lambda *a,**kw:
        SimpleNamespace(stdout=json.dumps({'frames':[
            {'best_effort_timestamp_time':str(i/120)} for i in range(24)]}).encode()))
    o,rgb,state,pts=observe_single_square(Path('unused.mp4'),size=32)
    assert o['spatial_component_count']==1
    assert o['aspect_ratio_at_analysis_resolution']==1
    assert o['quadrant_median_max_rgb_difference']==0
    assert o['color_state_counts']=={'black':4,'green':5,'magenta':15}
    assert o['green_state_measurements']['total_rising_edges']==5
    assert np.all(state[2:22]>0)
    assert o['observed_color_centers']['green_dominant']==[0,255,0]


def test_monochrome_square_recovers_white_black_gates(monkeypatch):
    sequence=[]
    for i in range(24):
        frame=np.zeros((32,32,3),dtype=np.uint8)
        if i%4==1:
            frame[:]=255
        sequence.append(frame)
    monkeypatch.setattr('analysis.single_square_video.frames',lambda path,size:iter(sequence))
    monkeypatch.setattr('analysis.single_square_video.probe_video',lambda path:{'refresh_rate_hz':120.0})
    monkeypatch.setattr('analysis.single_square_video.subprocess.run',lambda *a,**kw:
        SimpleNamespace(stdout=json.dumps({'frames':[
            {'best_effort_timestamp_time':str(i/120)} for i in range(24)]}).encode()))
    o,rgb,state,pts=observe_single_square(Path('unused.mp4'),size=32,monochrome=True)
    assert o['color_state_counts']=={'black':18,'nonblack':6}
    assert o['observed_color_centers']['nonblack']==[255,255,255]
    assert o['maximum_median_channel_spread']==0
    assert o['quadrant_median_max_rgb_difference']==0
    assert o['nonblack_state_measurements']['total_rising_edges']==6
