"""Streaming spatial and color-state observation without render declarations."""
import json
import subprocess
from pathlib import Path

import numpy as np
from scipy import ndimage

from analysis.streaming_video import frames, trace_measurements, active_runs
from analysis.video_regions import probe_video


def observe_single_square(path: Path, size=128, monochrome=False):
    metadata=probe_video(path)
    maximum=np.zeros((size,size))
    count=0
    for frame in frames(path,size):
        maximum=np.maximum(maximum,frame.max(axis=2)/255.0)
        count+=1
    labels,number=ndimage.label(maximum>max(.02,maximum.max()*.3))
    components=[labels==i for i in range(1,number+1)
                if (labels==i).sum()>=size*size*.02]
    if len(components)!=1:
        raise ValueError(f'observed {len(components)} spatial components; single-square audit unresolved')
    mask=components[0]
    y,x=np.nonzero(mask)
    bbox=[int(x.min()),int(y.min()),int(x.max()+1),int(y.max()+1)]
    quadrants=[]
    for bottom in (False,True):
        for right in (False,True):
            yy,xx=np.indices(mask.shape)
            q=mask & ((yy>=(y.min()+y.max()+1)/2)==bottom) & ((xx>=(x.min()+x.max()+1)/2)==right)
            quadrants.append(q)
    rgb=np.empty((count,3),dtype=np.float32)
    quadrant_rgb=np.empty((count,4,3),dtype=np.float32)
    decoded=0
    for i,frame in enumerate(frames(path,size)):
        rgb[i]=np.median(frame[mask],axis=0)
        for j,q in enumerate(quadrants):
            quadrant_rgb[i,j]=np.median(frame[q],axis=0)
        decoded+=1
    if decoded!=count:
        raise ValueError('decode passes disagree')
    black=rgb.max(axis=1)<5
    colors,frequencies=np.unique(rgb[~black],axis=0,return_counts=True)
    if len(colors)<2 and not monochrome:
        raise ValueError('fewer than two observed nonblack colors')
    if monochrome:
        state=(~black).astype(np.uint8)
        observed_centers={'nonblack':np.median(rgb[~black],axis=0).tolist()}
        state_names=['black','nonblack']
        trace_name='nonblack_state_measurements'
    else:
        first=colors[frequencies.argmax()]
        second=colors[np.linalg.norm(colors-first,axis=1).argmax()]
        centers=np.array([first,second])
        for _ in range(5):
            assignments=np.linalg.norm(rgb[~black,None,:]-centers[None,:,:],axis=2).argmin(axis=1)
            centers=np.array([np.median(rgb[~black][assignments==j],axis=0) for j in range(2)])
        green_index=int(np.argmax(centers[:,1]-(centers[:,0]+centers[:,2])/2))
        assignment=np.linalg.norm(rgb[:,None,:]-centers[None,:,:],axis=2).argmin(axis=1)
        # 0=black, 1=observed green-dominant state, 2=other/magenta state.
        state=np.where(black,0,np.where(assignment==green_index,1,2)).astype(np.uint8)
        observed_centers={'green_dominant':centers[green_index].tolist(),
                          'magenta_dominant':centers[1-green_index].tolist()}
        state_names=['black','green','magenta']
        trace_name='green_state_measurements'
    stream=subprocess.run(['ffprobe','-v','error','-select_streams','v:0',
        '-show_frames','-show_entries','frame=best_effort_timestamp_time','-of','json',str(path)],
        capture_output=True,check=True)
    pts=np.array([float(f['best_effort_timestamp_time']) for f in json.loads(stream.stdout)['frames']])
    if len(pts)!=count:
        raise ValueError('timestamp and frame counts disagree')
    fps=metadata['refresh_rate_hz']
    delta=np.diff(pts)
    qerror=np.abs(quadrant_rgb-rgb[:,None,:])
    return {
        'observation_version':'0.1.0','stream':metadata,'decoded_frame_count':count,
        'duration_seconds':count/fps,'spatial_component_count':1,'bounding_box':bbox,
        'aspect_ratio_at_analysis_resolution':(bbox[2]-bbox[0])/(bbox[3]-bbox[1]),
        'quadrant_median_max_rgb_difference':float(qerror.max()),
        'quadrant_frames_with_difference_over_3':int(np.sum(np.any(qerror>3,axis=(1,2)))),
        'observed_color_centers':observed_centers,
        'color_state_counts':{name:int(np.sum(state==n)) for n,name in enumerate(state_names)},
        trace_name:trace_measurements((state==1).astype(float),fps,.5),
        'black_intervals':[{'start_seconds':float(a/fps),'end_seconds':float(b/fps)}
                           for a,b in active_runs(state==0)],
        'color_peak_rgb':{name:rgb[state==n].max(axis=0).tolist()
                          for n,name in enumerate(state_names) if np.any(state==n)},
        'maximum_median_channel_spread':float(np.ptp(rgb,axis=1).max()),
        'pts_audit':{'count':len(pts),'start_seconds':float(pts[0]),
            'last_frame_start_seconds':float(pts[-1]),
            'non_increasing_count':int(np.sum(delta<=0)),
            'cadence_outlier_count':int(np.sum(np.abs(delta-1/fps)>.000002)),
            'maximum_cadence_error_seconds':float(np.max(np.abs(delta-1/fps)))},
        'ordering_attestation':{'declaration_loaded_during_detection':False,'targets_loaded_during_detection':False},
        'limitations':['Spatial uniformity is measured from quadrant medians at reduced resolution.',
                       'State occupancy measures encoded pixels, not calibrated optical duty or luminance.',
                       'Subframe gates and physical display timing remain unresolved.']
    },rgb,state,pts
