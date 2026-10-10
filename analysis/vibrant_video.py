"""Independent RGB and pulse-highlight observation for long four-region media."""
import json
import subprocess
from pathlib import Path

import numpy as np
from scipy import ndimage

from analysis.streaming_video import frames, trace_measurements
from analysis.video_regions import probe_video


def observe_vibrant(path: Path, size=128):
    stream = probe_video(path)
    maximum = np.zeros((size, size), dtype=float)
    count = 0
    for frame in frames(path, size):
        maximum = np.maximum(maximum, frame.max(axis=2)/255.0)
        count += 1
    labels, number = ndimage.label(maximum > max(0.02, maximum.max()*0.3))
    components = []
    for label in range(1, number+1):
        mask = labels == label
        if mask.sum() < size*size*0.02:
            continue
        y, x = np.nonzero(mask)
        components.append({
            "mask": mask, "region_id": ("top" if y.mean()<size/2 else "bottom")
            + "_" + ("left" if x.mean()<size/2 else "right"),
            "bounding_box": [int(x.min()), int(y.min()), int(x.max()+1), int(y.max()+1)],
        })
    components.sort(key=lambda c: (c["bounding_box"][1],c["bounding_box"][0]))
    if len(components) != 4:
        raise ValueError(f"observed {len(components)} regions; four-region color audit unavailable")
    rgb = np.empty((count, 4, 3), dtype=np.float32)
    decoded = 0
    for index, frame in enumerate(frames(path, size)):
        for j, c in enumerate(components):
            rgb[index,j] = np.median(frame[c["mask"]],axis=0)
        decoded += 1
    if decoded != count:
        raise ValueError("decode passes differ in frame count")
    p = subprocess.run(["ffprobe","-v","error","-select_streams","v:0",
        "-show_frames","-show_entries","frame=best_effort_timestamp_time",
        "-of","json",str(path)],capture_output=True,check=True)
    pts=np.array([float(f["best_effort_timestamp_time"]) for f in json.loads(p.stdout)["frames"]])
    if len(pts) != count:
        raise ValueError("timestamp and decoded frame counts differ")
    fps=stream["refresh_rate_hz"]
    strength=rgb.max(axis=2)/255.0
    active=strength>0.02
    regions=[]
    for j,c in enumerate(components):
        color_samples=rgb[active[:,j],j]
        regions.append({**{k:v for k,v in c.items() if k!='mask'},
            "peak_rgb":rgb[:,j].max(axis=0).tolist(),
            "active_rgb_percentiles":{
                str(q):np.percentile(color_samples,q,axis=0).tolist() for q in (10,25,50,75,90)
            },
            "gate_measurements":[trace_measurements(strength[:,j],fps,t) for t in (.01,.02,.05)]})
    edges=np.flatnonzero(np.diff(active[:,0].astype(np.int8),prepend=0)==1)
    pulse_colors=[]
    # Normalize each region by its own typical active RGB energy to compare
    # emphasis across differently colored quadrants without using a palette.
    energy=np.linalg.norm(rgb,axis=2)
    baseline=np.array([np.percentile(energy[active[:,j],j],25) for j in range(4)])
    for edge in edges:
        score=energy[edge]/np.maximum(baseline,1e-6)
        order=np.argsort(score)
        winner=int(order[-1])
        clear=score[winner]>score[order[-2]]*1.05
        pulse_colors.append({"rising_frame":int(edge),"time_seconds":float(edge/fps),
            "normalized_color_energy":score.tolist(),
            "emphasized_region":components[winner]['region_id'] if clear else None})
    delta=np.diff(pts)
    observation={
        "observation_version":"0.1.0","stream":stream,"decoded_frame_count":count,
        "duration_seconds":count/fps,"analysis_size":size,"regions":regions,
        "region_count":len(regions),"observed_pulse_emphasis":pulse_colors,
        "all_region_gates_matched":bool(np.all(active==active[:,:1])),
        "region_disagreement_frame_count":int(np.sum(np.any(active!=active[:,:1],axis=1))),
        "pts_audit":{"count":len(pts),"start":float(pts[0]),"last_frame_start":float(pts[-1]),
            "non_increasing_count":int(np.sum(delta<=0)),
            "cadence_outlier_count":int(np.sum(np.abs(delta-1/fps)>0.000002)),
            "maximum_cadence_error_seconds":float(np.max(np.abs(delta-1/fps)))},
        "ordering_attestation":{"declaration_loaded_during_detection":False,
                                 "targets_loaded_during_detection":False},
        "limitations":["RGB measures encoded pixel values, not calibrated brightness or saturation.",
                       "Pulse emphasis is inferred by normalized RGB energy and can be ambiguous.",
                       "Subframe pulses and physical output remain unresolved."]}
    return observation,rgb,pts
