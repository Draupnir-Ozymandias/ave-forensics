import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from analysis.vibrant_video import observe_vibrant


def test_rgb_observer_recovers_matched_gates_and_clockwise_emphasis(monkeypatch):
    bounds=[(slice(1,14),slice(1,14)),(slice(1,14),slice(18,31)),
            (slice(18,31),slice(1,14)),(slice(18,31),slice(18,31))]
    palette=np.array([[160,0,0],[0,160,0],[0,0,160],[160,0,160]])
    clockwise=[0,1,3,2]
    sequence=[]
    for frame in range(96):
        image=np.zeros((32,32,3),dtype=np.uint8)
        if frame%12<3:
            pulse=frame//12
            for j,(rows,cols) in enumerate(bounds):
                image[rows,cols]=palette[j] if j!=clockwise[pulse%4] else palette[j]*1.5
        sequence.append(image)
    monkeypatch.setattr('analysis.vibrant_video.frames',lambda path,size:iter(sequence))
    monkeypatch.setattr('analysis.vibrant_video.probe_video',lambda path:{'refresh_rate_hz':120.0})
    monkeypatch.setattr('analysis.vibrant_video.subprocess.run',lambda *a,**kw:
        SimpleNamespace(stdout=json.dumps({'frames':[
            {'best_effort_timestamp_time':str(i/120)} for i in range(96)]}).encode()))
    o,rgb,pts=observe_vibrant(Path('unused.mp4'),size=32)
    assert o['region_count']==4
    assert o['all_region_gates_matched']
    assert [p['emphasized_region'] for p in o['observed_pulse_emphasis'][:4]]==[
        'top_left','top_right','bottom_right','bottom_left']
    assert o['pts_audit']['cadence_outlier_count']==0
    assert rgb.shape==(96,4,3)
