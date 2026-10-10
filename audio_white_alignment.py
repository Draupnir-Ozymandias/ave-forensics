"""Independent bounded music spectrum/envelope analysis and pulse comparison."""
import argparse
import json
import subprocess
from pathlib import Path

import numpy as np
from scipy.ndimage import uniform_filter1d
from scipy.signal import butter, sosfiltfilt, welch, find_peaks

from analysis.pulse import analyze_pulse_patterns, _rms_envelope
from core.hashing import sha256_file
from provenance.run import build_run_provenance


def spectrum_peaks(signal, rate, low, high, window_seconds):
    frequency,power=welch(signal,fs=rate,nperseg=min(len(signal),round(window_seconds*rate)))
    mask=(frequency>=low)&(frequency<=high)
    selected=np.flatnonzero(mask)
    peaks,_=find_peaks(power[mask],distance=max(1,round(.1/(rate/min(len(signal),round(window_seconds*rate))))))
    indices=selected[peaks]
    indices=sorted(indices,key=lambda i:power[i],reverse=True)[:12]
    maximum=power[mask].max()
    return {'frequency_resolution_hz':float(frequency[1]-frequency[0]),
            'peaks':[{'frequency_hz':float(frequency[i]),'relative_power':float(power[i]/maximum)} for i in indices],
            'band_power':float(np.sum(power[mask])*(frequency[1]-frequency[0]))}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('audio',type=Path)
    parser.add_argument('white_observation',type=Path)
    parser.add_argument('--output-dir',type=Path,required=True)
    args=parser.parse_args()
    path=args.audio.resolve()
    # Decode exactly the bounded excerpt; never load the full 15-minute track.
    decoded=subprocess.run(['ffmpeg','-v','error','-i',str(path),'-t','300',
        '-ar','22050','-ac','2','-f','f32le','-'],capture_output=True,check=True).stdout
    audio=np.frombuffer(decoded,dtype=np.float32).reshape(-1,2).T
    rate=22050
    if audio.shape[1]!=300*rate:
        raise ValueError('source does not supply exactly 300 seconds')
    source_hash=sha256_file(path)
    provenance=build_run_provenance(input_path=path,project_root=Path(__file__).resolve().parent,
        analysis_configuration={'configuration_schema_version':'audio-white-alignment-0.1.0',
            'source_interval_seconds':[0,300],'decoded_rate_hz':rate,
            'carrier_welch_window_seconds':16,'envelope_target_rate_hz':200,
            'envelope_welch_window_seconds':20,'detector_targets_loaded':False})
    mean=np.mean(audio,axis=0)
    spectra={channel:spectrum_peaks(signal,rate,40,5000,16)
             for channel,signal in [('left',audio[0]),('right',audio[1]),('mean',mean)]}
    envelopes={}
    reduced={}
    for name,signal in [('broadband_left',audio[0]),('broadband_right',audio[1]),('broadband_mean',mean)]:
        envelope,erate=_rms_envelope(signal,rate,200)
        reduced[name]=envelope
        detrended=envelope-uniform_filter1d(envelope,size=round(5*erate),mode='nearest')
        envelopes[name]={'rate_hz':erate,'modulation_spectrum':spectrum_peaks(detrended,erate,.5,40,20)}
    for low,high in [(40,100),(100,250),(250,1000),(1000,5000)]:
        band=sosfiltfilt(butter(4,[low,high],btype='bandpass',fs=rate,output='sos'),mean)
        envelope,erate=_rms_envelope(band,rate,200)
        detrended=envelope-uniform_filter1d(envelope,size=round(5*erate),mode='nearest')
        windows=[]
        for start in range(0,len(detrended)-round(20*erate)+1,round(10*erate)):
            selected=detrended[start:start+round(20*erate)]
            windows.append({'start_seconds':float(start/erate),
                'end_seconds':float((start+len(selected))/erate),
                'peaks':spectrum_peaks(selected,erate,.5,40,20)['peaks'][:3]})
        envelopes[f'band_{low}_{high}']={'rate_hz':erate,
            'modulation_spectrum':spectrum_peaks(detrended,erate,.5,40,20),
            'windowed_modulation_peaks':windows}
    pulse=analyze_pulse_patterns(audio,rate,envelope_sample_rate=200)
    args.output_dir.mkdir(parents=True,exist_ok=True)
    observation={'analysis_version':'0.1.0','source_audio_sha256':source_hash,
        'source_time_range_seconds':{'start':0,'end':300},'decoded_sample_rate_hz':rate,
        'decoded_sample_count_per_channel':audio.shape[1],
        'decoded_peak':float(np.max(np.abs(audio))),'decoded_rms':float(np.sqrt(np.mean(audio**2))),
        'stereo_correlation':float(np.corrcoef(audio)[0,1]),
        'audible_spectrum':spectra,'envelope_modulation':envelopes,
        'pulse_classification':pulse['classification'],'pulse_channels':pulse['channels'],
        'pulse_timeline':pulse['timeline'],'run_provenance':provenance,
        'limitations':['Spectral peaks in music are not confirmed entrainment carriers.',
                       'Envelope peaks and interchannel differences do not establish beat intent or physiological effects.',
                       'Measurements apply only to the first 300 seconds and bounded decoder/resampling settings.']}
    observation_path=args.output_dir/'audio-observation.json'
    observation_path.write_text(json.dumps(observation,indent=2)+'\n')
    # Comparison starts only after the source audio observation is persisted.
    white=json.loads(args.white_observation.read_text())
    trace_path=args.white_observation.parent/'traces.npz'
    if sha256_file(trace_path)!=white['trace_sha256']:
        raise ValueError('white traces changed')
    if sha256_file(Path(white['artifact']['path']))!=white['artifact']['sha256']:
        raise ValueError('white video changed')
    trace=np.load(trace_path)
    gate=trace['state'].astype(float)
    fps=white['stream']['refresh_rate_hz']
    rms=np.empty((len(gate),2))
    for frame in range(len(gate)):
        start=round(frame*rate/fps);end=round((frame+1)*rate/fps)
        rms[frame]=np.sqrt(np.mean(np.square(audio[:,start:end],dtype=float),axis=1))
    active=(np.arange(len(gate))/fps>=1.5)&(np.arange(len(gate))/fps<298)
    comparisons={}
    for index,name in enumerate(['left','right']):
        signal=rms[:,index]
        residual=signal-uniform_filter1d(signal,round(5*fps),mode='nearest')
        comparisons[name]={
            'raw_RMS_gate_pearson':float(np.corrcoef(signal[active],gate[active])[0,1]),
            'detrended_RMS_gate_pearson':float(np.corrcoef(residual[active],gate[active])[0,1]),
            'mean_RMS_white_on':float(np.mean(signal[active&(gate==1)])),
            'mean_RMS_white_off':float(np.mean(signal[active&(gate==0)]))}
    handoff_path=args.output_dir/'alignment-traces.npz'
    np.savez_compressed(handoff_path,white_gate=gate.astype(np.uint8),
                        video_timestamps=trace['timestamps'],source_audio_RMS_per_video_frame=rms)
    comparison={'comparison_version':'0.1.0','audio_observation_sha256':sha256_file(observation_path),
        'white_observation_sha256':sha256_file(args.white_observation),
        'white_video_sha256':white['artifact']['sha256'],'frame_rate_hz':fps,
        'frame_count':len(gate),'source_audio_sha256':source_hash,
        'comparison_scope_seconds':[1.5,298],'channels':comparisons,
        'alignment_traces_sha256':sha256_file(handoff_path),
        'recommendation':'Preserve pitch/stereo; introduce explicitly synthetic amplitude modulation driven by the saved exact white frame gate.',
        'limitations':['Correlation measures natural association, not therapeutic benefit.',
                       'Hard zero gain can click and interrupt music; smoothing/floor gain changes the acoustic envelope and must be declared.',
                       'Audio-side synchronization should target the actual encoded white gate, including missed narrow pulses.']}
    (args.output_dir/'alignment-comparison.json').write_text(json.dumps(comparison,indent=2)+'\n')
    print('Audio peaks:',spectra['mean']['peaks'][:5])
    print('Envelope peaks:',envelopes['broadband_mean']['modulation_spectrum']['peaks'][:5])
    print('Pulse:',pulse['classification'],'gate correlations:',comparisons)


if __name__=='__main__':
    main()
